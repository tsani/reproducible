#!/usr/bin/env python

from __future__ import print_function

from datetime import datetime

import subprocess as sp
from subprocess import PIPE

import sys
from sys import argv as args
from sys import exit

import os
from os import path

from itertools import islice, imap, ifilter

from shutil import rmtree

compose = lambda f, g: lambda *args, **kwargs: f(g(*args, **kwargs))
mkfprint = lambda f: lambda *args, **kwargs: print(*args, file=f, **kwargs)
errprint = mkfprint(sys.stderr)
equals_any = lambda v: lambda l: compose(any, imap)(lambda x: v == x, l)
equals_any_c = lambda v, l: equals_any(v)(l)
flip = lambda f: lambda x, y: f(y, x)
any_do = compose(any, imap)

def ireversed(seq):
    for i in xrange(len(seq) - 1, -1, -1):
        yield seq[i]

class CLIError(Exception):
    pass

class PipelineRunnerError(Exception):
    pass
class PipelineRunnerInitializationError(PipelineRunnerError):
    pass
class PipelineRunnerRepositoryError(PipelineRunnerInitializationError):
    pass
class PipelineRunnerRuntimeError(PipelineRunnerError):
    pass

class PipelineStepError(Exception):
    pass
class PipelineStepInitializationError(Exception):
    pass
class PipelineStepRuntimeError(Exception):
    pass

class PipelineStep:
    def __init__(self, name, script_path, results_dir):
        self.name        = name
        self.script_path = script_path
        self.results_dir = results_dir
        self.output_dir  = None

        if not path.exists(self.script_path):
            raise PipelineStepInitializationError("File not found: %s" % self.script_path)
        # we don't need to check results_dir since it is already guaranteed to exist at this point.
        # TODO perhaps check results_dir for robustness

    def make_output_directory(self, run_name):
        self.output_dir = path.join(self.results_dir, run_name, self.name)
        os.makedirs(self.output_dir)

    def run(self):
        """ Run this step of the pipeline. The output directory and the previous step symlinks must be
            created prior to calling this method.
            """
        if not self.output_dir:
            raise PipelineStepRuntimeError("Pipeline step ``%s'' has not created its output directory."
                    % self.name)
        # output_dir is the path (relative to CWD !) where this step should store its output.
        # it is passed as the first argument to this step's inner script.
        try:
            returncode = sp.call([self.script_path, self.output_dir])
            if returncode != 0:
                raise PipelineStepRuntimeError("The inner script failed.")
        except:
            self.exc_info = sys.exc_info()
            rmtree(self.output_dir)
            raise

class PipelineRunner:
    def __init__(self, force=False, final=False, output_dir=None,
            results_dir="results", reproducible_list_file=".reproducible",
            pipeline_file=".pipeline", range_start=None, range_end=None,
            future=False, previous_run=None, ignore_missing_output=False,
            inference_behaviour=None):
        self.force                  = force
        self.output_dir             = output_dir
        self.results_dir            = results_dir
        self.reproducible_list_file = reproducible_list_file
        self.pipeline_file          = pipeline_file
        self.range_start            = range_start
        self.range_end              = range_end
        self.previous_run           = previous_run
        self.ignore_missing_output  = ignore_missing_output
        self.inference_behaviour    = inference_behaviour
        self.final                  = final
        self.future                 = future

        if not path.exists(self.results_dir):
            raise PipelineRunnerInitializationError("Results directory does not exist: %s"
                    % self.results_dir)
        if not self.force and not path.exists(self.reproducible_list_file): # we don't care if forcing
            raise PipelineRunnerInitializationError(
                    "List of files under reproducibility control not found: %s"
                    % self.reproducible_list_file)
        if not path.exists(self.pipeline_file):
            raise PipelineRunnerInitializationError(
                    "fatal: no pipeline specification file named ``%s'' present"
                    % self.pipeline_file)
        if self.previous_run and not path.exists(path.join(self.results_dir, self.previous_run)):
            raise PipelineRunnerInitializationError("Previous run directory not found: %s"
                    % path.join(self.results_dir, self.previous_run))

        if self.output_dir is None:
            t = datetime.now()
            self.output_dir = str(t)

        if path.exists(self.output_dir):
            raise PipelineRunnerInitializationError(
                    "fatal: the output directory for this run already exists.")

        if not self.force:
            self._parse_reproducible_file() # this will also guarantee that the files exist
            if not self._is_repo_clean():
                # the commit-enforcing policy:
                raise PipelineRunnerInitializationError(
                        "fatal: repository is not clean. \nPlease commit changes to any files "
                        + "listed in ``%s''." % self.reproducible_list_file)

        self._parse_pipeline_file() # also verifies that the scripts exist

        self._determine_range()

        git_rev_proc = sp.Popen(["git", "rev-parse", "HEAD"], stdout=PIPE)
        git_rev_out, git_rev_err = git_rev_proc.communicate()
        if git_rev_proc.returncode != 0:
            raise PipelineRunnerInitializationError("fatal: unable to get the commit hash.")
        self.rev = git_rev_out

    def run(self):
        """ Run the reproducible pipeline. If this run is a continuation (i.e. not starting at the
            beginning) then this this """

        os.makedirs(path.join(self.results_dir, self.output_dir))

        if self.range_start > 0:
            self._generate_previous_step_links()

        for step in islice(self.pipeline_steps, self.range_start, self.range_end + 1):
            step.make_output_directory(self.output_dir)
            step.run()

        odir = path.join(self.results_dir, self.output_dir)
        with open(path.join(odir, "rev.txt"), 'w') as f:
            mkfprint(f)(self.rev)
        if self.force or self.final:
            with open(path.join(odir, ".final"), 'w') as f:
                mkfprint(f)("final")

    def _generate_previous_step_links(self):
        """ For each step N from the previous run where N < self.range_start, generate a symlink
            to that step's output folder in this run's folder.
            """
        if self.range_start == 0:
            raise PipelineRunnerInitializationError("inconsistency: cannot generate symlinks to the "
                    + "previous run's prior steps if this run is meant to start at the beginning.")
            # TODO perhaps this^ exception is overkill.
        if not self.previous_run:
            raise PipelineRunnerInitializationError("fatal: cannot generate symlinks to previous " +
                    "steps in the previous run if the previous run is not determined.")

        link_range = lambda start=None, end=None: map(self._make_previous_link,
            [step.name for step in islice(self.pipeline_steps, start, end)])

        link_range(0, self.range_start)

        if self.future:
            if self.range_end + 1 >= len(self.pipeline_steps):
                raise PipelineRunnerInitializationError("inconsistency: cannot generate symlinks to " +
                        "future steps if the pipeline is to run until the last step.")

            link_range(self.range_end + 1)

    def _has_step(self, run_name, step_name):
        return path.exists(path.join(self.results_dir, self.run_name, self.step_name))

    def _determine_range(self):
        """ Perform black magic (read: lots of ifs) to infer the correct behaviour when given
            imprecise command lines. When given precise command lines, look for inconsistencies
            to prevent the user from accidentally doing something bad.
            This method guarantees that if it completes without throwing, then self.range_start
            is set correctly.
            This method should always be called during initialization, even if the user is
            supplying a starting point, as it checks for inconsistencies.
            This method also sets self.has_previous_run, self.had_previous_run (not a typo!),
            and it will call _determine_previous_run, if necessary, setting self.previous_run.
            """
        self.steps_num = len(self.pipeline_steps) # number of steps in this run

        self.range_start = self._parse_range(self.range_start)
        self.range_end = self._parse_range(self.range_end)
        # If any of the ranges are None, then parsing will simply do nothing.
        # None-ness is treated below.

        if self.range_end is None:
            self.range_end = len(self.pipeline_steps)
        elif self.range_end > self.steps_num:
            raise PipelineRunnerInitializationError(
                    "inconsistency: cannot run to step #%i as there are only %i steps in total."
                    % (self.range_end, self.steps_num))
        elif self.range_end < self.steps_num: # if the pipeline is to end prematurely
            self.steps_num = self.range_end # set the number of steps to that value
            # of course, the number of steps may be even less if the pipeline is to begin
            # later than the start.
        else: # the user set the end step # to the number of steps. Good guy user !
            pass

        self.had_previous_run = not not self.previous_run # 'had' as in prior to determination
        # _determine_previous_run returns true if a previous run was found
        # it also assigns what it found to self.previous_run
        has_previous_run = True if self.previous_run else self._determine_previous_run()
        if has_previous_run: # if there's a previous run
            # count the number of steps in that run
            prev_run_steps_num = self._count_steps_in_run(self.previous_run)
            print("Previous run:", self.previous_run)
        else:
            print("No previous run given / failed to determine previous run.")

        if self.range_start is None: # starting step unspecified
            if self.inference_behaviour == "continue": # force continuing
                if has_previous_run: # if there is a previous run
                    if self.steps_num > prev_run_steps_num: # there are more steps now
                        self.range_start = prev_run_steps_num + 1 # continue from end of previous run
                    elif self.steps_num < prev_run_steps_num: # there are less steps now
                        raise PipelineRunnerInitializationError(
                                "fatal: number of steps decreased since last run.")
                    else: # same number of steps
                        # in an inferred setting, we would set this to 1,
                        # but since we're forcing continuing, we raise an exception.
                        raise PipelineRunnerInitializationError(
                                "inconsistency: pipeline set to continue from previous run, "
                                + "but the number of steps since the last run is the same.")
                else: # no previous run
                    # if we were doing inference, we would assume to start at step 1
                    # but since we're forcing continuing, we raise an exception:
                    # can't continue from nowhere !
                    raise PipelineRunnerInitializationError(
                            "inconsistency: pipeline set to continue from previous run, "
                            + "but there are no (valid) previous runs.")
            elif self.inference_behaviour == "rebuild": # force rebuilding
                if self.had_previous_run: # if the *user* specified a previous run to use
                    # they are being silly since they also specified rebuilding !
                    raise PipelineRunnerInitializationError(
                            "inconsistency: pipeline set to rebuild, but a previous run "
                            + "was specified.")
                else:
                    self.range_start = 1 # set to beginning
            else: # true inference
                if has_previous_run: # if there is a previous run
                    if self.steps_num > prev_run_steps_num: # there are more steps now
                        self.range_start = self.steps_num # continue from end of previous run
                    elif self.steps_num < prev_run_steps_num: # there are less steps now
                        raise PipelineRunnerInitializationError(
                                "fatal: number of steps decreased since last run.")
                    else: # same number of steps
                        # infer rebuilding
                        self.range_start = 1
                else: # no previous run
                    # infer rebuilding
                    self.range_start = 1
        else: # range_start is specified by the user
            # that means we're continuing
            # first check that the user isn't trolling
            if self.range_start > self.range_end:
                raise PipelineRunnerInitializationError(("inconsistency: this run is meant to "
                        + "start at start at step #%i and end at step #%i.")
                        % (self.range_start, self.range_end))
            if has_previous_run: # if there is a previous run
                # if the previous run is missing some step output folders
                if self.range_start > prev_run_steps_num + 1:
                    # if need all the previous step outputs to exist
                    if not self.ignore_missing_output:
                        raise PipelineRunnerInitializationError(
                                ("inconsistency: this run is meant to continue at step #%i, "
                                + "but the previous run has only %i steps. \nPlease address "
                                + "this or use the --ignore-missing-output flag.")
                                % (self.range_start, prev_run_steps_num))
                    else:
                        pass # it doesn't matter, because we don't care about missing outputs
                else:
                    pass # good, we are not starting past the number of steps in the previous run
            else: # there is no previous run
                if self.range_start > 1: # starting past the beginning
                    # if we care about missing output from previous steps
                    if not self.ignore_missing_output:
                        raise PipelineRunnerInitializationError(
                                ("inconsistency: this run is meant to continue at step #%i, "
                                + "but there is no previous step. \nPlease address this or "
                                + "use the --ignore-missing-output flag.")
                                % (self.range_start))
                    else:
                        pass # we don't care about missing output, so no problem
                elif self.range_start < 1:
                    raise PipelineRunnerInitializationError("fatal: the starting step number must"
                            + "be positive.")
                else: # self.range_start == 1
                    pass # good.

        # until now, range_end and range_start have been ordinals. We need to switch to offsets
        # in order to use them as list indices in python.
        self.range_end -= 1
        self.range_start -= 1

    @staticmethod
    def _rebase_path(base_file, relative_file):
        """ Convert a path relative to the given file into a path relative to the CWD. """
        # to do so, we take the dirname of the pipeline file and join it to the script path. The pipeline
        # file is relative to the CWD.
        return path.join(path.dirname(base_file), relative_file)

    @staticmethod
    def _is_final(run_dir):
        """ Determine whether the run saved to the given directory is final, i.e. if it contains a file
            named ``.final''.
            """
        return ".final" in os.listdir(run_dir)

    @staticmethod
    def _is_reproducible(run_dir):
        """ Determine whether a given run is reproducible, i.e. check for the existence of a rev.txt. """
        return "rev.txt" in os.listdir(run_dir)

    def _count_steps_in_run(self, run_name):
        """ Determine how many steps there are in a run by counting the number of folders in that
            directory whose names are step names as listed in self.pipeline_file.
            """
        stepnames = map(lambda step: step.name, self.pipeline_steps)
        odir = path.join(self.results_dir, run_name)
        return len(filter(lambda p: path.isdir(p) and (path.basename(p) in stepnames),
                          map(lambda p: path.join(odir, p), os.listdir(odir))))

    def _determine_previous_run(self):
        """ Figure out what the previous run is by taking the most recent non-final and reproducible
            run directory's name. If there are no such runs, then False is returned. True is
            returned if self.previous_run was successfully set to the run name of an appropriate
            previous run. """
        # get the list of runs as an iterable, ignoring any files in the results directory that are not
        # folders, ignoring any runs that are final, and ignoring any runs which themselves are not
        # reproducible.
        runs = filter(lambda p: path.isdir(p) and not self._is_final(p) and self._is_reproducible(p),
                imap(lambda p: path.join(self.results_dir, p), os.listdir(self.results_dir)))
        if len(runs) == 0:
            return False
        # runs now contains a list of paths to run directories. We need to sort by last modification time
        sorted_runs = sorted(runs, key=path.getmtime) # the last entry is the most recent
        self.previous_run = path.basename(sorted_runs[-1]) # return the basename, since that is the run name.
        return True

    # TODO store all these previous runs that way when we want to query, we don't need to regenerate this list.
    def _find_previous_run_with(self, step_name):
        runs = filter(lambda p: path.isdir(p) and not self._is_final(p) and self._is_reproducible(p),
                imap(lambda p: path.join(self.results_dir, p), os.listdir(self.results_dir)))
        if len(runs) == 0:
            return None

        sorted_runs = sorted(runs, key=path.getmtime)
        for step_path in reversed(sorted_runs):
            if path.exists(path.join(step_path, step_name)):
                return path.basename(step_path)
        return None

    def _parse_pipeline_file(self): # :: ... -> IO () ;)
        """ Parse the pipeline file, whose path is stored in self.pipeline_file, into a list of
            PipelineStep objects stored in self.pipeline_steps. The ``make_output_directory'' method
            is not called yet, since ``_parse_pipeline_file'' has no knowledge of the run name, which
            is required to determine the path to the run folder.
            """
        lineno = 1
        self.pipeline_steps = []
        try:
            with open(self.pipeline_file) as f:
                for line in f:
                    words = line[:-1].split() # drop the last char since it's \n
                    script_rel_path = words[0]
                    step_name       = words[1]
                    script_abs_path = self._rebase_path(self.pipeline_file, script_rel_path)
                    if not path.exists(script_abs_path):
                        raise PipelineStepInitializationError(
                                "Cannot find pipeline component script ``%s''" % script_abs_path)
                    step = PipelineStep(step_name, script_abs_path, self.results_dir)
                    self.pipeline_steps.append(step)
                    lineno += 1
        except IndexError:
            errprint("Invalid format at ", self.pipeline_file, ":", lineno)
            raise PipelineRunnerInitializationError("Invalid pipeline specification.")
        except IOError as e:
            errprint("IO error:", e)
            raise PipelineRunnerInitializationError("IO error.")
        # allow other exceptions to percolate up

    def _parse_reproducible_file(self): # :: ... -> IO ()
        """ Parse self.reproducible_list_file, rebase all the paths to be relative to the CWD, and check
            that all the files exist. If any files are missing, an exception is thrown. The resulting
            list of paths is stored in self.reproducible_files.
            """
        lineno = 1
        self.reproducible_files = []
        try:
            with open(self.reproducible_list_file) as f:
                for line_ in f:
                    line = line_[:-1] # drop the last char since it's \n
                    p = self._rebase_path(self.reproducible_list_file, line)
                    if not path.exists(p):
                        raise PipelineRunnerInitializationError("A file under reproducibility control" +
                                " at %s:%i ``%s'' does not exist" %
                                (self.reproducible_list_file, lineno, line))
                    self.reproducible_files.append(p)
                    lineno += 1
        except IOError as e:
            errprint("IO error:", e)
            raise PipelineRunnerInitializationError("IO error.")

    def _is_repo_clean(self):
        """ Check the status of the repository. If any of the files listed in self.reproducible_files
            have uncommitted local changes, then the return value is False, otherwise it is True. If
            self.reproducible_files does not exist or the git command fails, then an exception is raised.
            """
        if not self.reproducible_files:
            raise PipelineRunnerInitializationError("fatal: no files listed for reproducibility control.")

        git_status_proc = sp.Popen(["git", "status", "--short"] + self.reproducible_files, stdout=PIPE)
        # wait until the process ends and collect its output
        git_status_out, git_status_err = git_status_proc.communicate()
        if git_status_proc.returncode != 0:
            raise PipelineRunnerInitializationError("fatal: unable to stat the git repository.")

        return not git_status_out # if empty, then good.

    def _is_single_step(self):
        return self.range_start == self.range_end

    def _resolve_id(self, step_name):
        for (i, step) in enumerate(self.pipeline_steps, 1):
            if step_name == step.name:
                return i
        raise ValueError("no such step named ``%s''." % step_name)

    def _make_previous_link(self, name):
        os.symlink(path.join("..", self.previous_run, name),
                   path.join(self.results_dir, self.output_dir, name))

    def _parse_range(self, value):
        if not isinstance(value, str):
            return value

        try:
            return int(value)
        except ValueError:
            return self._resolve_id(value)

def run_reproducible_pipeline(*args, **kwargs):
    """ Construct a PipelineRunner, forwarding all arguments and keyword arguments to its constructor,
        and immediately call its ``run'' method, running the pipeline. The PipelineRunner is returned.
        """
    runner = PipelineRunner(*args, **kwargs)
    runner.run()
    return runner

switches = {"output_dir":("-o", "--output"), "results_dir":("-R", "--results"),
        "reproducible_file":("-r",), "pipeline_file":("-p",), "range_start":("--from",),
        "range_end":("--to",), "singleton_range":("--only",), "previous_run":("--with",),
        "ignore_missing_output":("--ignore-missing-output",), "final":("--final",),
        "force":("--force",), "future":("--link-future",)}

if __name__ == "__main__":
    results_dir             = "results"
    reproducible_file       = ".reproducible"
    pipeline_file           = ".pipeline"
    force                   = False
    future                  = False
    ignore_missing_output   = False
    final                   = False
    output_dir              = None
    range_start             = None
    range_end               = None
    previous_run            = None
    inference_behaviour     = None

    seen_args = set()
    saw = lambda name: name in seen_args # convenience for easy-reading

    i = 1
    while i < len(args):
        arg = args[i]
        def check_arg(name, checkf=saw, add=True):
            if equals_any(arg)(switches[name]):
                if checkf(name): # check if we've already processed this arg
                    raise CLIError("``%s'' appearing more than once on the command line" % arg)
                if add:
                    seen_args.add(name)
                return True
            else:
                return False

        nextarg = lambda: args[i+1]
        if check_arg("output_dir"):
            output_dir = nextarg()
            i += 1
        elif check_arg("results_dir"):
            results_dir = nextarg()
            i += 1
        elif check_arg("reproducible_file"):
            reproducible_file = nextarg()
            i += 1
        elif check_arg("pipeline_file"):
            pipeline_file = nextarg()
            i += 1
        elif check_arg("range_start"):
            if saw("singleton_range"):
                raise CLIError("``--only'' can only be used when ``--from'' and ``--to'' are not.")
            range_start = nextarg()
            i += 1
        elif check_arg("range_end"):
            if saw("singleton_range"):
                raise CLIError("``--only'' can only be used when ``--from'' and ``--to'' are not.")
            range_end = nextarg()
        elif check_arg("singleton_range"):
            if any_do(saw, ["range_start", "range_end"]):
                raise CLIError("``--only'' can only be used when ``--from'' and ``--to'' are not.")
            r = nextarg()
            range_start = r
            range_end   = r
            i += 1
        elif check_arg("ignore_missing_output"):
            ignore_missing_output = True
        elif arg == "--continue":
            if inference_behaviour:
                raise CLIError("Inference behaviour specified multiple times.")
            inference_behaviour = "continue"
        elif arg == "--everything":
            if inference_behaviour:
                raise CLIError("Inference behaviour specified multiple times.")
            inference_behaviour = "rebuild"
        elif check_arg("future"):
            future = True
        elif check_arg("final"):
            final = True
        elif check_arg("force"):
            force = True
        else:
            raise CLIError("Unrecognized command-line options ``%s''." % arg)
        i += 1

    try:
        runner = run_reproducible_pipeline(force, final, output_dir, results_dir,
                    reproducible_file, pipeline_file, range_start, range_end,
                    future, previous_run, ignore_missing_output,
                    inference_behaviour)
        with open(path.join(runner.results_dir, runner.output_dir, "invocation.txt"), 'w') as f:
            fprint = mkfprint(f)
            fprint("args =", args[1:])
    except PipelineRunnerInitializationError as e:
        errprint("The pipeline failed to start.")
        errprint(e)
    except PipelineRunnerRuntimeError as e:
        errprint("The execution of the pipeline could not complete successfully.")
        errprint("Please verify the integrity of this run's output folder.")
        errprint(e)
    except PipelineStepInitializationError as e:
        errprint("A step in the pipeline failed to start.")
        errprint(e)
    except PipelineStepRuntimeError as e:
        errprint("The execution of a step in the pipeline could not complete successfully.")
        errprint(e)
