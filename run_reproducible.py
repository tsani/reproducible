#!/usr/bin/env python2

from __future__ import print_function

import dm_tests as dmt
import subprocess

from sys import argv as args
from sys import exit
import sys
from os import path
from itertools import islice

errprint = lambda *args, **kwargs: print(*args, file=sys.stderr, **kwargs)
equals_any = lambda v, l: any(map(lambda x: v == x, l))

# A list of the names of functions in the inner script that we consider runnable to produce the experiment
runnable_names = ["run_all"] # TODO move this to a reproducible_config.py that we load here

try:
    import reproducible # just a file of files we need to watch
except ImportError:
    errprint("fatal: cannot load reproducible.py.")
    errprint("Please ensure that this file is present, and defines variable ``files'' listing the files to watch.")
    exit(1)

try:
    if not reproducible.files:
        errprint("fatal: no files are listed as reproducible in reproducible.py.")
        errprint("A variable named ``files'' should consist of list of files to watch.")
        exit(1)
except NameError:
    errprint("fatal: the variable ``files'' is not defined in reproducible.py.")
    errprint("Please ensure that such a variable is defined and lists the files to watch.")
    exit(1)

def english_list(words, connective="and"):
    return ", ".join(words[:-1]) + ", " + connective + " " + words[-1]

if __name__ == "__main__":
    force = False
    script_name = None
    script_args = []

    try:
        for (i, arg) in enumerate(islice(args, 1, None)):
            any_of = lambda l: equals_any(arg, l)
            if not script_name: # if the script is undefined, then args are to this script.
                if any_of(["-f", "--force"]): # so we try to parse the args
                    force = True # this would entail that we skip any reproducibility checks
                else: # if we fail to parse the args, then the script name has appeared on the command line
                    script_name = arg # so we set the script name, which causes all subsequent args to be stored and passed to the inner script
            else: # if the script is defined, then all subsequent args are passed as args to the script
                script_args.append(arg)
    except: # index exception only, i.e. the arg is not present. This shouldn't ever happen since we don't have arguments to switches now.
        errprint("fatal: invalid command line.")
        exit(1)

    if not all(map(path.exists, reproducible.files)): # we check that the files exist.
        errprint("fatal: some of the required files do not exist.", file=sys.stderr)
        exit(1)

    if not script_name:
        map(errprint, ["fatal: no script given to run internally.", "Please specify a script (with no .py extension) to run."])
        exit(1)

    try: # we try to load the script given on the command line
        script = __import__(script_name)
    except ImportError:
        map(errprint, ["fatal: unable to load the specified script.",
                       "(Did you remember to remove the .py extension ?)"])
        exit(1)

    runnables = [x for x in dir(script) if x in runnable_names] # we get the functions
    if not runnables:
        map(errprint, ["The given script does not define a run or conduct_all_experiments function.",
                       "Please define such a method. It will be invoked with any trailing command line",
                       "arguments to this script."])
        exit(1)

    # get the status of the files we're watching.
    git_status = subprocess.Popen(["git", "status", "--short"] + reproducible.files, stdout=subprocess.PIPE)
    status_out, status_err = git_status.communicate()
    git_status.wait()
    if git_status.returncode != 0: # (maybe the script is not running in the git repo?)
        print("fatal: checking project git repository status failed.", file=sys.stderr)
        exit(1)

    clean = len(status_out) == 0 # if there's no output, then we're all good! The files are clean.
    if (not clean) and (not force):
        map(errprint, ["fatal: the repository is not clean!", "Running this experiment does not guarantee reproducibility.",
                       "Please commit your changes to the files listed in reproducible.py, or force the test with the -f switch."])
        exit(1)

    # we load the function from the first string stored in runnables, and execute it, passing the script_args we accumulated from the commandline
    edir = getattr(script, runnables[0])(*tuple(script_args)) # returns the experiment directory's path
    if not isinstance(edir, basestring): # if the output is not as string
        map(errprint, ["fatal: the value returned by the inner script is not a string.",
                       "The hash of the commit that generated this experiment cannot be stored, and",
                       "the experiment that produced this output should not be considered reproducible."])
        exit(1) # we can't store the hash... :(

    # fetch the hash
    git_rev_parse = subprocess.Popen(["git", "rev-parse", "HEAD"], stdout=subprocess.PIPE)
    rev_out, rev_err = git_rev_parse.communicate()
    git_rev_parse.wait()

    if git_rev_parse.returncode != 0: # maybe there was a race condition (e.g. the user deleting everything while the experiment was running.)
        failure_message = ["fatal: unable to get SHA for this commit.", "Refusing to run the experiment unless forced with the -f switch."]
        map(errprint, failure_message)
        errprint("This message will be written to the experiment folder.", file=sys.stderr)
        try:
            with open(edir + "/sha-error.txt", 'w') as f:
                print(failure_message[0], file=f)
        except IOError as e:
            errprint("very fatal: unable to write the error message to the experiment directory.")
            exit(1)

    try:
        with open(edir + "/rev.txt", 'w') as f:
            print(out, file=f)
            if not clean:
                print("NOT CLEAN", file=f)
    except IOError as e:
        map(errprint, ["fatal: unable to write the commit hash.",
                       ("Inner exception:", e)])
        exit(1)

