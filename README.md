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
<code>run_reproducible.py</code> will fail with exit code 1.

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
provided for simple pipelines. A simple pipeline is one in which there is a
base step (phase zero), and each step (phase n+1) depends only on the results
of the step immediately prior (phase n). Because of this dependency, each step
must not only keep track of what commit generated it, but it must also know
which commit generated the output that was fed into it. By following the
resulting chain of commits, it is possible to effectively get back the code
that produced any of the intermediate results. 

### An example

Let's suppose we have the following directory structure:

    project/
    \   bin/
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
        output -> step3/output   (a symlink)

This would be the _normal_ way of doing things, with no reproducibility
control.

To use <code>run_reproducible_pipeline.py</code> we first need to write a
<code>.reproducible</code> file as described earlier. We also need to write a
description of our pipeline, which explains how each step should be performed.
We write this description in a file named <code>.pipeline</code>:

    step1.sh step1
    step2.sh step2
    step3.sh step3

<code>run_reproducible_pipeline.py</code> will effectively run
<code>run_reproducible.py</code> on what's in the first column of each line
each entry, but will guarantee the propagation of <code>prev</code> symlinks
that refer to the output directory of the previous step.

The second column is reserved for the name of the directory in the experiment
folder that the script will write its output file to.

Each of the component scripts must accept as its first command-line argument
the folder where it should save its output to. By default,
<code>run_reproducible_pipeline.py</code> will make a folder named with the
current date and time. This directory's path is conveyed to each of the
component scripts, plus the name given in <code>.pipeline</code>. For example,
if I run a reproducible pipeline on 17 July 2014 at 3:32 PM, the first argument
given to step1.sh will be <code>2014:07:17 15:32:47/step1</code>, and that
is where <code>step1.sh</code> should write its output.

It is possible to provide an explicit folder to create with the <code>-o |
--output</code> switch:

    run_reproducible_pipeline.py -o crazy_test

The command-line arguments of <code>run_reproducible_pipline.py</code> are
saved to <code>invocation.txt</code> in the output directory, so it is possible
to recover this information (in case the folder gets renamed later, for
instance.)

<code>run_reproducible_pipeline.py</code> will create a symlink named
<code>prev</code> to the previous step's output folder in the current
step's output folder _prior to_ invoking the current step's script. Thus,
the current step can access the previous step's output simply by trying to
open the file <code>prev/output</code>. Since the scripts have access to
this information, it becomes easy to construct the path to the output of
the previous step: <code>"project/results/$1/step1/output</code>, for
example, would be used in <code>step2.sh</code> to set the input of the
underlying portion of the pipeline. 

The component scripts in the pipeline do not have the requirement to have as
their last line of standard output the path to where the <code>rev.txt</code>
file should be saved. Reproducible already knows where it should go: it created
the experiment directory. 

(That's the main difference between non-pipelined execution: the callee is
expected to create the experiment directory and then inform Reproducible,
whereas in pipelined execution, the Reproducible informs the callee of where it
should store its output.)

With <code>run_reproducible_pipeline.py</code>, our directory structure now
looks like this:

    project/
    \   bin/
            step1.sh
            step2.sh
            step3.sh
            .reproducible   (lists all the files in this directory)
            .pipeline       (lists the shell scripts and output folders)
        data/
        \   input_file.dat
        results/
        \   2014:07:18 16:22:32
            \   step1/
                \   output
                step2/
                \   output
                    prev -> ../step1
                step3/
                \   output
                    prev -> ../step2
                rev.txt
                invocation.txt

These <code>prev</code> symlinks essentially make it possible to walk backwards
indefinitely, until we reach step 1, for example by writing
<code>results/step3/prev/prev/output</code>.

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

    run_reproducible_pipeline.py --from 2 --with "results/2014:07:18 16:22:32"

A path specified with <code>--with</code> is assumed to be relative to the
working directory (which we assume here to be <code>project/</code>), whereas
paths listed in <code>.pipeline</code> are assumed relative to the new
directory that will be created by <code>run_reproducible_pipeline.py</code>
(the folder named with the current date and time).

The result of running the above line would be the creation of 

SOME NOTES FOR ME:
    Rather than make "prev" symlinks, we would instead make symlinks to all the
    steps from previous runs. That way each time-stamped run folder would have
    *all* the steps. This requires some symlink-chasing on the part of the
    user, but it guarantees reproducibility.

Using <code>run_reproducible_pipeline.py</code> sacrifices some of the
flexibility of running <code>run_reproducible.py</code>, but saves us some of
the headaches of having to work out our own system for each pipeline, provided
the pipeline we're using is _linear_.
