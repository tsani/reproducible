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
invokation syntax is as follows:

    run_reproducible.py [-f|--force] <script> [ARGS...]

The script passed to <code>run_reproducible.py</code> must be written in Python
(sorry!) and it must define a global function named <code>run_all</code>.
Whatever ARGS are specified on the command line are simply forwarded to
<code>run_all</code> as-is. The string passed as the script name must also not
include the .py extension. Furthermore, for <code>run_reproducible.py</code>
to know where to record the SHA of the current commit, <code>run_all</code>
must return the path to the experiment directory, where the output of the
experiment is recorded.

The <code>-f</code> switch will make <code>run_reproducible.py</code> skip the
repository cleanliness check. This is not advisable, as it means that whatever
the inner script outputs cannot reliably be reproduced. Still, this is better
than just running the inner script directly, without wrapping it, since
<code>run_reproducible.py</code> will still record the SHA and will add to the
generated rev.txt the message "NOT CLEAN", to indicate that the repository's
watched files had local changes when the experiment was conducted.

Since <code>run_reproducible.py</code> can take arguments from the command line
and forward them to <code>run_all</code>, it can be difficult to recover the
command-line that produced the experiment if the output of the experiment
hinges on what arguments were forwarded. To prevent such a situation from
arising, it is advisable to write such <code>run_all</code> functions that take
no arguments, and try to self-contain the experiment to the fullest extent
possible. An alternative is to create a (shell or Python) script whose purpose
is to invoke <code>run_reproducible.py</code> with the correct arguments. Such
a script should immediately be placed under reproducibilit control, by listing
it in the <code>files</code> variable of <code>reproducible.py</code>. For
example:

    #!/bin/bash
    run_reproducible.py dm_tests test1
    run_reproducible.py dm_tests test2

where each of <code>test1</code> and <code>test2</code> generate their own
separate experiment output folders.

Although such a setup is practicable, it is advisable to simply extend the
<code>run_all</code> function to generate a single folder per experiment, and
to run within that folder several sub-experiments, rather than to create
several separate experiments and invoke <code>run_reproducible.py</code> for
each one.
