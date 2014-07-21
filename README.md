Reproducible
============

Reproducible is a script to assist scientists and others working on very
data-oriented projects. 

Motivation
----------

Frequently, we run a script to transform some input data into some output data,
but the output isn't quite to our liking. We run the script again with some
different parameters, possibly erasing the existing data. Now it looks a bit
better, so we try some more changes, each time squashing our old output. Now we
realize that a previous version was better, so we would like to go back, so we
must re-tweak our script's parameters again and again, hopefully getting
something that looks like what we had originally.

Now we're smarter: we decide to store each run in its own directory, named with
the date and time of the experiment. It's easy for us to go back and view past
iterations of the output, but suppose we find some past output that we really
like, but we wish that we could slightly tweak the parameters that generated
it. It's very difficult or tedious for us to recover those parameters,
especially if we just invoke the script on the command line. It's a little bit
easier if the invokation occurred in a script that is under version control,
but it's not impossible that we ran the script from a dirty reposity, i.e. one
in which we had uncommitted changes. Even if we're guaranteed that all our runs
come from clean repositories, then it is still quite tedious to search through
our git log to find the exact commit that generated a given output.

Reproducible solves all the above, getting rid of many of the headaches
associated with data-oriented programming. By ensuring that the scripts are not
dirty and by saving to the output folder the hash of the commit that generated
that output, it becomes trivial to recover the exact commit that generated that
output.

How it works
------------

Reproducible effectively creates a one-to-one mapping between commit hashes and
experimental output data. This guarantees that it is straightforward to roll
back to the exact working directory that generated a given set of output.

The user maintains a list of files under _reproducibility control_, and rather
than run the data processing scripts directly, we instead wrap the invokation
of the script in a call to <code>run_reproducible.py</code>. This wrapper
script will verify that the files listed under reproducibility control
have no uncommitted changes. If there are uncommitted changes, then the user is
simply invited to commit the work that has been done. It is possible to bypass
this check, but doing so severely limits reproducibility, as explained below. 

The wrapper script will then record in a file named <code>rev.txt</code> placed
in the experimental output folder the hash of the commit that generated this
experiment. This means that reverting to the code that generated this
experiment is as simple as opening <code>rev.txt</code> and running <code>git
checkout</code> on the hash contained there. From there it is possible to
create a new branch with changes effectively based on a past instance of the
experiment.

Setup
-----

Setup is very bad for now. Simply clone the repository somewhere, and copy
<code>run_reproducible.py</code> into your project folder. Due to the way
Python handles imports, this is necessary for relative imports to succeed. If
the inner script that is being wrapped does not perform any relative imports,
then there shouldn't be a problem, and the location of the wrapper shouldn't
matter much. 

The next step is to create a list of files to watch. Simply create a file named
<code>.reproducible</code> and list the files to watch, one path per line.

    dm_run.py
    dm_optimizer.py
    sa_tester.sh
    etc.

<code>run_reproducible.py</code> will fail if any of the following conditions
are not met:

* The directory in which <code>run_reproducible.py</code> is run must be
  (part of) a git repository.
* <code>.reproducible</code> must exist and all the files listed in it must
  exist.

Once the above has been carried out, you're ready to use Reproducible!

Usage
-----

<code>run_reproducible.py</code> is a generalized wrapper script. It's
invocation syntax is as follows:

    run_reproducible.py [OPTIONS...] <script> [ARGS...]

The possible options are the following:

* <code>-f | --force</code>: force the running of the script, even if one or
  more files from .reproducible are not committed.
* <code>-r | --reproducible</code>: (takes one argument) specify an alternate
  list of files to consider under reproducibility control. This setting can be
  used in scenarios where there are two or more subprojects in the same
  directory, and each should have its own separate list of
  reproducibility-controlled files. This setting will cause .reproducible to be
  ignore (in fact it can even be absent if -r is used instead.) It is allowed
  to specify '-' (dash) as the reproducible file list, in which case the files
  are read from standard input.
* <code>-o | --output</code>: (takes one argument) set the directory where the
  reproducibility information should be stored. If this option is set, then the
  standard behaviour of using the last line of the inner script's standard
  output as the path to the output directory will be suppressed.

The script passed to <code>run_reproducible.py</code> can be any executable. 
Whatever ARGS are specified on the command line are simply forwarded to the
inner script as-is. 

For <code>run_reproducible.py</code> to know where to store reproducibility
information, it must know what the experiment directory is. (It is expected that
the inner script create the experiment directory, generally based on the time
of the experiment, although this is not enforced.) The inner script's standard
output is captured, and its last line of standard output is taken to be the
directory where the reproducibility information should be stored. (This only
applies when not using the -r switch.) If this directory does not exist, then
<code>run_reproducible.py</code> will fail with exit code 1. The standard
output of the inner script is regardless forwarded to the terminal.

The <code>-f</code> switch will make <code>run_reproducible.py</code> skip the
repository cleanliness check. This is not advisable, as it means that whatever
the inner script outputs cannot reliably be reproduced. Still, this is better
than just running the inner script directly, without wrapping it, since
<code>run_reproducible.py</code> will still record the SHA and will add to the
generated rev.txt the message "NOT CLEAN", to indicate that the repository's
watched files had local changes when the experiment was conducted. Furthermore,
<code>run_reproducible.py</code> will save the command-line used to invoke the
inner script to a file called <code>invocation.txt</code>. This information can
be useful when trying to reconstruct the data at a later time.

Since <code>run_reproducible.py</code> can take arguments from the command line
and forward them to <code>run_all</code>, it can be difficult to recover the
command-line that produced the experiment if the output of the experiment
hinges on what arguments were forwarded. Rather than force the user to write
additional wrapper scripts with the desired command-line arguments built-in,
Reproducible will simply save the command-line used to invoke it to a file name
<code>invocation.txt</code> in the same directory as <code>rev.txt</code>.

Pipelines
---------

Reproducible provides <code>run_reproducible.py</code> as its primary way of
creating easily reproducible data with minimal effort. For larger projects, in
which a more sophisticated (read: time-consuming) _pipeline_ is being used to
process data, rerunning the entire pipeline for every tweak is not feasible. 

To facilitate large data-processing pipelines, Reproducible provides a few
convenience functions in <code>run_reproducible.py</code> so that individual
portions of the pipeline may be tracked separately for reproducibility control.

A basic pipeline script called <code>run_reproducible_pipeline.py</code> is
provided for simple pipelines. A simple pipeline is one in which the output of
step n&gt;1 can depend only on the output(s) of step(s) m&lt;n and on
(unchanging) external files.

Naturally, as pipelines are more complex, the usage of
<code>run_reproducible_pipeline.py</code> is as well. Here is the
summary of its command line interface, and below, there is a concrete example
using it and its various switches.

    run_reproducible_pipeline.py [(-o|--output) <output directory>]
        [(-R|--results) <results directory>]  
        [-r <reproducible file>] [-p <.pipeline file>]
        ([--from <step>] [--to <step>] | [--only <step>])
        [--with <run>] [--ignore-missing-output]
        [(--continue | --everything)] [--force]

* <code>-o | --output</code>: specify the exact folder name where this run's
  output should be stored. 
  Default: generate the folder name with the current date and time.
* <code>-R | --results</code>: specify the path (relative to the current
  working directory) where the results directory is located.
  Default: <code>results</code> 
  If the directory does not exist, Reproducible will fail with an error
  message.
* <code>-r <reproducible file></code>: specify the file that lists the files
  under reproducibility control (the commit-enforcing policy).
  Default: <code>.reproducible</code>
* <code>-p <pipeline file></code>: specify the file that lists the steps in the
  pipeline and the names of the steps
  Default: <code>.pipeline</code>
* <code>--from N</code> <code>--to N</code> <code>--only N</code>: specify a
  range of steps to run.
  Default: all the steps listed in the pipeline file.
* <code>--with <run></code>: specify the run from which to draw the output of
  previous steps. This switch has no effect if the entire pipeline is being
  run.
* <code>--ignore-missing-output</code>: when running from a step n>1, do not
  fail if output for steps m&lt;n does not exist.
* <code>--continue</code>: enforce that the next run should be a continuation
  of the previous one (or the one specified with <code>--with</code>). If
  proceeding as a continuation is not possible (e.g. for each step in the
  specified range, its output already exists in the previous run), fail with an
  error message.
* <code>--everything</code>: ignore previous runs, and run the entire pipeline
  from the start.
* <code>--force</code>: skip repository sanity check. This can result in
  irreproducible results.


### An example

Let's suppose we have the following directory structure:

    project/
    \   .gitignore  
        bin/
        \   run_all.sh
            step1.sh
            step2.sh
            step3.sh
        data/
        \   input_file.dat

Executing <code>run_all.sh</code> will create the following subdirectory of
<code>project</code>:

    results/
    \   step1/
        \   output
        step2/
        \   output
        step3/
        \   output

This would be the _normal_ way of doing things, with no reproducibility
control.

To use <code>run_reproducible_pipeline.py</code> we first need to write a
<code>.reproducible</code> file as described earlier, in order to enable to
commit-enforcing policy.  We also need to write a description of our pipeline,
which explains how each step should be performed.  We write this description in
a file named <code>.pipeline</code>:

    step1.sh step1
    step2.sh step2
    step3.sh step3

<code>run_reproducible_pipeline.py</code> will effectively run
<code>run_reproducible.py</code> on what's in the first column of each line
each entry, but will enforce a certain amount of organization in the
<code>results</code> directory, and allow for a straightforward way of
recovering the hash of the commit that generated the output of any step in the
pipeline.

The second column is reserved for the name of the step. This name is used as
the name of the directory in which the step's script is to write its output.
It is necessary for Reproducible to know the directory names for it to perform
previous step resolution as described below. These names are not allowed to
change, and they must be unique to a given project.

Each of the component scripts must accept as its first command-line argument
the folder where it should save its output to. By default,
<code>run_reproducible_pipeline.py</code> will make a folder named with the
current date and time. This directory's path is conveyed to each of the
component scripts, plus the name given in <code>.pipeline</code>. For example,
if I run a reproducible pipeline on 17 July 2014 at 3:32 PM, the first argument
given to step1.sh will be <code>2014:07:17 15:32:47/step1</code>, and that
is where <code>step1.sh</code> should write its output.

It is possible to provide an explicit folder to create with the <code>-o</code> 
(long form: <code>--output</code>) switch:

    run_reproducible_pipeline.py -o crazy_test

The command-line arguments of <code>run_reproducible_pipeline.py</code> are
saved to <code>invocation.txt</code> in the output directory, so it is possible
to recover this information (in case the folder gets renamed later, for
instance.)

The preferred way for a script to access the output of a previous step is to
simply use the same of that step, and a relative path:
<code>../step1/output</code> could be used from within step 2 to
access the output of step 1, which in turn should be step 2's input.
Furthermore, this means that it is straightforward to make a step that requires
the output of two or more previous steps, simply by referring to those steps by
name.

(Planned feature: simultaneous steps. Placing a <code>&</code> at the end of a
line in <code>.pipeline</code> would indicate to Reproducible that the
subsequent step may be performed at the same time as the current step. This
allows for a nice speedup in some cases, and allows for rudimentary branching 
pipelines.)

The component scripts in the pipeline do not have the requirement to have as
their last line of standard output the path to where the <code>rev.txt</code>
file should be saved. Reproducible already knows where it should go: it created
the experiment directory. 

(That's the main difference with non-pipelined execution: the callee is
expected to create the experiment directory and then inform Reproducible,
whereas in pipelined execution, Reproducible informs the callee of where it
should store its output.)

With <code>run_reproducible_pipeline.py</code>, our directory structure now
looks like this:

    project/
    \   .reproducible       (lists the scripts in bin/)
        .pipeline           (lists the scripts and output folder names)
        .gitignore
        bin/
            step1.sh
            step2.sh
            step3.sh
        data/
        \   input_file.dat
        results/
        \   2014:07:18 16:22:32
            \   step1/
                \   output
                step2/
                \   output
                step3/
                \   output
                rev.txt
                invocation.txt

N.B. In a real project, the output filenames will generally be more descriptive
than "output", i.e. we do so here only for the sake of example.

Let's suppose that the output of step1 is perfect: no more tweaking is required
for it. Step 2, however, still needs work, as we determine by looking at the
its output. We make some tweaks to step2.sh, (we commit our tweaks!) and then
want to rerun the pipeline. If we simply run
<code>run_reproducible_pipeline.py</code> again, then *everything* will be 
reconstructed, and that's no good. We need to specify that we would only
want to rebuild the chain of outputs from a given step. For this purpose, we
have the <code>--from</code> switch.

    run_reproducible_pipeline.py --from 2

The default behaviour for determining which step 1 output should be chosen is
to pick the step 1 that is the most recent (by file creation time stamp), since
the most recent version of the output is most likely the best one, but it's
possible to set a specific one by providing a path:

    run_reproducible_pipeline.py --from 2 --with "../2014:07:18 16:22:32"

A path specified with <code>--with</code> is assumed to be relative to the
directory that will be created (by default with the current date and time).
This is indeed somewhat confusing at first, but we can see how it makes sense
from the filesystem diagram below.

In this case, the result of running either of the above two commands would
produce the same result:

    2014:07:18 19:36:29/
    \   step1 -> ../2014:07:18 16:22:32/step1
        step2/
        \   output
        step3/
        \   output
        rev.txt
        invocation.txt

All steps prior to the one specified by the <code>--from</code> switch will be
generated as symlinks to the relevant run (either the most recent one or the
one specified with the <code>--with</code> switch). It it thus possible to
follow these symlinks to determine exactly which commit of the relevant driver
script(s) generated the output of the relevant step(s), by examining the
<code>rev.txt</code>.

As a counterpart to <code>--from</code>, we also provide <code>--to</code>.
Reproducible will run the pipeline up to and including the step identified by
the number given as an argument to the switch. The effect of <code>--from N
--to N</code> is therefore to run only step N. There is a shortcut switch to do
just that, namely <code>--only</code>.

Remarks:

 * if <code>--to</code> or <code>--only</code> are used such that the
   pipeline completes before running all its steps as listed in
   <code>.pipeline</code>, then symlinks to future steps will not be
   generated. Only symlinks to _previous_ steps are generated.
 * if <code>--from</code> and/or <code>--to</code> is used alongside
   <code>--only</code>, then Reproducible will fail with an error message.
   Reproducible will also fail if the indices given are out of range, or if the
   value of <code>--to</code> is less than the value of <code>--from</code>

### Building a pipeline, piece by piece

<code>run_reproducible_pipeline.py</code> provides a convenience switch for
building up a pipeline. Suppose we start out by just writing
<code>step1.sh</code>, and we see the output is looking good. Now we write
<code>step2.sh</code>, but we can't simply run
<code>run_reproducible_pipeline.py</code>, since that would run step 1 again!

Or would it?

In fact, the default behaviour is to check the entries in
<code>.pipeline</code> and compare with the contents of the most recent run's
directory: if Reproducible determines that more steps have been added to
<code>.pipeline</code>, then it will infer a <code>--from</code> switch with
the appropriate value. In our example just above, the inferred value would be
two. If the number of steps is the same, then the entire pipeline will be run
again.

Note that the use of the <code>--to</code> switch can influence the effect of
rebuilding/continuing inference. Suppose there are four steps in our pipeline
(we already have at least one run with the output of those four steps) and we
add three more steps, but use <code>--to 4</code>. The effect will be to run
all the four first steps over again, since it is the given _range_ of steps
that is checked for in the last run's output folder. Reproducible will see that
the specified steps exist, and therefore, the inferred behaviour will be to
rerun the pipeline entirely for those steps.

On the other hand, there is a case in which inference is not performed. Suppose
we have a pipeline with four steps, and we add three. There is at least one run
with the output of the first four, and we run with <code>--from 6</code>.
Reproducible will see that there is no output for step 5, and rather than infer
that it should run step five, it will fail with an error message. To
disambiguate, the user is required to either use <code>--from N</code> where
the output of step N-1 exists, or to use the
<code>--ignore-missing-output</code> switch. It is not advisable to use this
switch, however, since the resulting output directory will look rather strange
with missing steps in it.

### Explicit is better than implicit

Of course, relying on a program's ability to infer what the user wants can be
dangerous. As such, the following switches are provided to explicitly perform
the actions described in the previous section:

* <code>--everything</code>: run all the specified steps again.
* <code>--continue</code>: pick up where the pipeline left off, running the new
  steps based on the output of the previous steps.

Again, these command-line arguments will be saved to
<code>invocation.txt</code> in the run's folder.

Note that if <code>--continue</code> is used, but no new steps have been added,
Reproducible will simply fail with an error message.

Bugs and caveats
----------------

There are probably many more than those listed here. If you discover any, don't
hesitate to open an issue here or to submit a pull request.

 * Misbehaved buffers: the wrapper scripts effectively open a pipe to the inner
   scripts to collect their stdout. For the echoing of the inner script's
   stdout to stream correctly to the terminal, it might be necessary to disable
   output buffering in the inner script.
