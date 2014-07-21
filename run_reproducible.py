#!/usr/bin/env python2

from __future__ import print_function

import subprocess
from subprocess import PIPE

from sys import argv as args
from sys import exit
import sys
from os import path
from itertools import islice, imap

### Helper functions
# Make a function that prints to to the given file.
mkfprint = lambda f: lambda *args, **kwargs: print(*args, file=f, **kwargs)
# A function to print to standard error.
errprint = mkfprint(sys.stderr)
# A function to check if a value is equal to any of the elements in a list.
equals_any = lambda v, l: any(imap(lambda x: v == x, l))

default_reproducible_path = ".reproducible"

def run_reproducible(script_command, force=False, rev_folder=None,
        reproducible_path=default_reproducible_path):
    if reproducible_path == None:
        reproducible_path = default_reproducible_path

    files = []

    if not path.exists(reproducible_path):
        errprint("fatal: cannot load .reproducible")
        errprint("Please ensure that this file is present and that it lists the files to watch.")
        return 1
    else:
        with open(reproducible_path) as f:
            files = [line[:-1] for line in f]

        if not files:
            errprint("fatal: no files are listed as reproducible in .reproducible.")
            errprint("A variable named ``files'' should consist of list of files to watch.")
    # Verify everything
    if any(imap(lambda f: not path.exists(f), files)): # we check that the files exist.
        errprint("fatal: some of the required files do not exist.")
        return 1

    if not script_command:
        map(errprint, ["fatal: no script given to run internally.", "Please specify a script to run."])
        return 1

    if not path.exists(script_command[0]):
        map(errprint, ["fatal: the given script does not exist.", "Please specify a script that exists."])
        return 1

    if rev_folder != None and (not path.exists(rev_folder)):
        map(errprint, ["fatal: the given output directory does not exist.",
                       "Please specify an output directory that exists."])
        return 1

    # get the status of the files we're watching.
    git_status = subprocess.Popen(["git", "status", "--short"] + files, stdout=subprocess.PIPE)
    status_out, status_err = git_status.communicate()
    git_status.wait()
    if git_status.returncode != 0: # (maybe the script is not running in the git repo?)
        errprint("fatal: checking project git repository status failed.")
        return 1

    git_rev_parse = subprocess.Popen(["git", "rev-parse", "HEAD"], stdout=subprocess.PIPE)
    rev_out, rev_err = git_rev_parse.communicate()
    git_rev_parse.wait()

    if git_rev_parse.returncode != 0:
        map(errprint, ["fatal: could not get the hash of the current commit.", "Is the current working directory in a git repository?"])
        return 1

    clean = len(status_out) == 0 # if there's no output, then we're all good! The files are clean.
    if not clean:
        if not force:
            map(errprint, ["fatal: the repository is not clean.",
                           "Running this experiment would not guarantee reproducibility.",
                           "Please commit your changes to the files listed in .reproducible,",
                           "or force the test with the -f switch."])
            return 1
        else:
            map(errprint, ["warning: the repository is not clean."])

    # run the inner script, and we'll collect its stdout.
    script_proc = subprocess.Popen(script_command, stdout=PIPE)
    while True:
        line = script_proc.stdout.readline()
        if not line:
            break
        sys.stdout.write(line) # echo everything the internal script outputs.
        last_line = line # remember the last line emitted on stdout
    script_proc.wait() # the stdout is closed, but the process may still be running.

    if script_proc.returncode != 0:
        map(errprint, ["fatal: the inner script returned a nonzero exit code.",
                       "This means something wrong happened during the execution of the script."])
        return 1

    if not rev_folder:
        if not last_line:
            map(errprint, ["fatal: the inner script did not produce anything on stdout.",
                           "The last line written to stdout by the inner script must be a path",
                           "to the output directory, where reproducibility information will be saved."])
            return 1
        rev_folder = last_line[:-1] # we don't want that \n on the end.

    if not path.exists(rev_folder):
        map(errprint, ["fatal: the directory returned from the inner script does not exist.",
                       "The last line written to stdout by the inner script must be a path",
                       "to the output directory, where rev.txt will be written"])
        return 1

    # the last line emitted on stdout must be the path where to store rev.txt and other such
    # reproducibility control information.
    # *unless*, the user specified the directory on the command-line, in which case rev_folder is not None.

    # fetch the hash
    try:
        with open(rev_folder + "/rev.txt", 'w') as f:
            fprint = mkfprint(f)
            fprint(rev_out, end='') # out already has a \n at the end.
            if not clean:
                print("NOT CLEAN", file=f)
        with open(rev_folder + "/invocation.txt", 'w') as f:
            fprint = mkfprint(f)
            fprint(repr(script_command))
    except IOError as e:
        map(errprint, ["fatal: unable to write the commit hash.",
                       ("Inner exception:", e)])
        return 1
    return 0

if __name__ == "__main__":
    script_args         = []
    rev_folder          = None
    reproducible_path   = None
    force               = False

    try: # parse the command line arguments
        i = 1
        while i < len(args):
            arg      = args[i]
            any_of   = lambda l: equals_any(arg, l)
            next_arg = lambda: args[i+1] # hide this in a lambda, that way the exception will only be raised if we try to get the arg.

            if not script_args: # if the script is undefined, then args are to this script.
                if any_of(["-f", "--force"]): # so we try to parse the args
                    force = True # this would entail that we skip any reproducibility checks
                elif any_of(["-o", "--output"]):
                    rev_folder = next_arg()
                    i += 1
                elif any_of(["-r", "--reproducible"]):
                    reproducible_path = next_arg()
                    i += 1
                else: # if we fail to parse the args, then the script name has appeared on the command line
                    script_args.append(arg) # so we set the script name, which causes all subsequent args to be stored and passed to the inner script
            else: # if the script is defined, then all subsequent args are passed as args to the script
                script_args.append(arg)
            i += 1
    except: # this should only happen for index exceptions, like putting -o at the end of the command line.
        errprint("fatal: invalid command line.")
        exit(1)

    exit(run_reproducible(script_args, force, rev_folder, reproducible_path))
