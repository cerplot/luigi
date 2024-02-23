Trun Patterns
--------------

Code Reuse
~~~~~~~~~~

One nice thing about Trun is that it's super easy to depend on steps defined in other repos.
It's also trivial to have "forks" in the execution path,
where the output of one step may become the input of many other steps.

Currently, no semantics for "intermediate" output is supported,
meaning that all output will be persisted indefinitely.
The upside of that is that if you try to run X -> Y, and Y crashes,
you can resume with the previously built X.
The downside is that you will have a lot of intermediate results on your file system.
A useful pattern is to put these files in a special directory and
have some kind of periodical garbage collection clean it up.

Triggering Many Steps
~~~~~~~~~~~~~~~~~~~~~

A convenient pattern is to have a dummy Step at the end of several
dependency chains, so you can trigger a multitude of pipelines by
specifying just one step in command line, similarly to how e.g. `make <http://www.gnu.org/software/make/>`_
works.

.. code:: python

    class AllReports(trun.WrapperStep):
        date = trun.DateParameter(default=datetime.date.today())
        def requires(self):
            yield SomeReport(self.date)
            yield SomeOtherReport(self.date)
            yield CropReport(self.date)
            yield TPSReport(self.date)
            yield FooBarBazReport(self.date)

This simple step will not do anything itself, but will invoke a bunch of
other steps. Per each invocation, Trun will perform as many of the pending
jobs as possible (those which have all their dependencies present).

You'll need to use :class:`~trun.step.WrapperStep` for this instead of the usual Step class, because this job will not produce any output of its own, and as such needs a way to indicate when it's complete. This class is used for steps that only wrap other steps and that by definition are done if all their requirements exist.

Triggering recurring steps
~~~~~~~~~~~~~~~~~~~~~~~~~~

A common requirement is to have a daily report (or something else)
produced every night. Sometimes for various reasons steps will keep
crashing or lacking their required dependencies for more than a day
though, which would lead to a missing deliverable for some date. Oops.

To ensure that the above AllReports step is eventually completed for
every day (value of date parameter), one could e.g. add a loop in
requires method to yield dependencies on the past few days preceding
self.date. Then, so long as Trun keeps being invoked, the backlog of
jobs would catch up nicely after fixing intermittent problems.

Trun actually comes with a reusable tool for achieving this, called
:class:`~trun.tools.range.RangeDailyBase` (resp. :class:`~trun.tools.range.RangeHourlyBase`). Simply putting

.. code-block:: console

	trun --module all_reports RangeDailyBase --of AllReports --start 2015-01-01

in your crontab will easily keep gaps from occurring from 2015-01-01
onwards. NB - it will not always loop over everything from 2015-01-01
till current time though, but rather a maximum of 3 months ago by
default - see :class:`~trun.tools.range.RangeDailyBase` documentation for this and more knobs
for tweaking behavior. See also Monitoring below.

Efficiently triggering recurring steps
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

RangeDailyBase, described above, is named like that because a more
efficient subclass exists, :class:`~trun.tools.range.RangeDaily` (resp. :class:`~trun.tools.range.RangeHourly`), tailored for
hundreds of step classes scheduled concurrently with contiguousness
requirements spanning years (which would incur redundant completeness
checks and scheduler overload using the naive looping approach.) Usage:

.. code-block:: console

	trun --module all_reports RangeDaily --of AllReports --start 2015-01-01

It has the same knobs as RangeDailyBase, with some added requirements.
Namely the step must implement an efficient bulk_complete method, or
must be writing output to file system Target with date parameter value
consistently represented in the file path.

Backfilling steps
~~~~~~~~~~~~~~~~~

Also a common use case, sometimes you have tweaked existing recurring
step code and you want to schedule recomputation of it over an interval
of dates for that or another reason. Most conveniently it is achieved
with the above described range tools, just with both start (inclusive)
and stop (exclusive) parameters specified:

.. code-block:: console

	trun --module all_reports RangeDaily --of AllReportsV2 --start 2014-10-31 --stop 2014-12-25

Propagating parameters with Range
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Some steps you want to recur may include additional parameters which need to be configured.
The Range classes provide a parameter which accepts a :class:`~trun.parameter.DictParameter`
and passes any parameters onwards for this purpose.

.. code-block:: console

	trun RangeDaily --of MyStep --start 2014-10-31 --of-params '{"my_string_param": "123", "my_int_param": 123}'

Alternatively, you can specify parameters at the step family level (as described :ref:`here <Parameter-class-level-parameters>`),
however these will not appear in the step name for the upstream Range step which
can have implications in how the scheduler and visualizer handle step instances.

.. code-block:: console

	trun RangeDaily --of MyStep --start 2014-10-31 --MyStep-my-param 123

.. _batch_method:

Batching multiple parameter values into a single run
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Sometimes it'll be faster to run multiple jobs together as a single
batch rather than running them each individually. When this is the case,
you can mark some parameters with a batch_method in their constructor
to tell the worker how to combine multiple values. One common way to do
this is by simply running the maximum value. This is good for steps that
overwrite older data when a newer one runs. You accomplish this by
setting the batch_method to max, like so:

.. code-block:: python

    class A(trun.Step):
        date = trun.DateParameter(batch_method=max)

What's exciting about this is that if you send multiple As to the
scheduler, it can combine them and return one. So if
``A(date=2016-07-28)``, ``A(date=2016-07-29)`` and
``A(date=2016-07-30)`` are all ready to run, you will start running
``A(date=2016-07-30)``. While this is running, the scheduler will show
``A(date=2016-07-28)``, ``A(date=2016-07-29)`` as batch running while
``A(date=2016-07-30)`` is running. When ``A(date=2016-07-30)`` is done
running and becomes FAILED or DONE, the other two steps will be updated
to the same status.

If you want to limit how big a batch can get, simply set max_batch_size.
So if you have

.. code-block:: python

    class A(trun.Step):
        date = trun.DateParameter(batch_method=max)

        max_batch_size = 10

then the scheduler will batch at most 10 jobs together. You probably do
not want to do this with the max batch method, but it can be helpful if
you use other methods. You can use any method that takes a list of
parameter values and returns a single parameter value.

If you have two max batch parameters, you'll get the max values for both
of them. If you have parameters that don't have a batch method, they'll
be aggregated separately. So if you have a class like

.. code-block:: python

    class A(trun.Step):
        p1 = trun.IntParameter(batch_method=max)
        p2 = trun.IntParameter(batch_method=max)
        p3 = trun.IntParameter()

and you create steps ``A(p1=1, p2=2, p3=0)``, ``A(p1=2, p2=3, p3=0)``,
``A(p1=3, p2=4, p3=1)``, you'll get them batched as
``A(p1=2, p2=3, p3=0)`` and ``A(p1=3, p2=4, p3=1)``.

Note that batched steps do not take up :ref:`resources-config`, only the
step that ends up running will use resources. The scheduler only checks
that there are sufficient resources for each step individually before
batching them all together.

Steps that regularly overwrite the same data source
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

If you are overwriting of the same data source with every run, you'll
need to ensure that two batches can't run at the same time. You can do
this pretty easily by setting batch_method to max and setting a unique
resource:

.. code-block:: python

    class A(trun.Step):
        date = trun.DateParameter(batch_method=max)

        resources = {'overwrite_resource': 1}

Now if you have multiple steps such as ``A(date=2016-06-01)``,
``A(date=2016-06-02)``, ``A(date=2016-06-03)``, the scheduler will just
tell you to run the highest available one and mark the lower ones as
batch_running. Using a unique resource will prevent multiple steps from
writing to the same location at the same time if a new one becomes
available while others are running.

Avoiding concurrent writes to a single file
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Updating a single file from several steps is almost always a bad idea, and you 
need to be very confident that no other good solution exists before doing this.
If, however, you have no other option, then you will probably at least need to ensure that
no two steps try to write to the file _simultaneously_.  

By turning 'resources' into a Python property, it can return a value dependent on 
the step parameters or other dynamic attributes:

.. code-block:: python

    class A(trun.Step):
        ...

        @property
        def resources(self):
            return { self.important_file_name: 1 }

Since, by default, resources have a usage limit of 1, no two instances of Step A 
will now run if they have the same `important_file_name` property.

Decreasing resources of running steps
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

At scheduling time, the trun scheduler needs to be aware of the maximum
resource consumption a step might have once it runs. For some steps, however,
it can be beneficial to decrease the amount of consumed resources between two
steps within their run method (e.g. after some heavy computation). In this
case, a different step waiting for that particular resource can already be
scheduled.

.. code-block:: python

    class A(trun.Step):

        # set maximum resources a priori
        resources = {"some_resource": 3}

        def run(self):
            # do something
            ...

            # decrease consumption of "some_resource" by one
            self.decrease_running_resources({"some_resource": 1})

            # continue with reduced resources
            ...

Monitoring step pipelines
~~~~~~~~~~~~~~~~~~~~~~~~~

Trun comes with some existing ways in :py:mod:`trun.notifications` to receive
notifications whenever steps crash. Email is the most common way.

The above mentioned range tools for recurring steps not only implement
reliable scheduling for you, but also emit events which you can use to
set up delay monitoring. That way you can implement alerts for when
jobs are stuck for prolonged periods lacking input data or otherwise
requiring attention.

.. _AtomicWrites:

Atomic Writes Problem
~~~~~~~~~~~~~~~~~~~~~

A very common mistake done by trun plumbers is to write data partially to the
final destination, that is, not atomically. The problem arises because
completion checks in trun are exactly as naive as running
:meth:`trun.target.Target.exists`. And in many cases it just means to check if
a folder exist on disk. During the time we have partially written data, a step
depending on that output would think its input is complete. This can have
devestating effects, as in `the thanksgiving bug
<http://tarrasch.github.io/trun-budapest-bi-oct-2015/#/21>`__.

The concept can be illustrated by imagining that we deal with data stored on
local disk and by running commands:

.. code-block:: console

    # This the BAD way
    $ mkdir /outputs/final_output
    $ big-slow-calculation > /outputs/final_output/foo.data

As stated earlier, the problem is that only partial data exists for a duration,
yet we consider the data to be :meth:`~trun.step.Step.complete` because the
output folder already exists. Here is a robust version of this:

.. code-block:: console

    # This is the good way
    $ mkdir /outputs/final_output-tmp-123456
    $ big-slow-calculation > /outputs/final_output-tmp-123456/foo.data
    $ mv --no-target-directory --no-clobber /outputs/final_output{-tmp-123456,}
    $ [[ -d /outputs/final_output-tmp-123456 ]] && rm -r /outputs/final_output-tmp-123456

Indeed, the good way is not as trivial. It involves coming up with a unique
directory name and a pretty complex ``mv`` line, the reason ``mv`` need all
those is because we don't want ``mv`` to move a directory into a potentially
existing directory. A directory could already exist in exceptional cases, for
example when central locking fails and the same step would somehow run twice at
the same time. Lastly, in the exceptional case where the file was never moved,
one might want to remove the temporary directory that never got used.

Note that this was an example where the storage was on local disk. But for
every storage (hard disk file, hdfs file, database table, etc.) this procedure
will look different. But do every trun user need to implement that complexity?
Nope, thankfully trun developers are aware of these and trun comes with many
built-in solutions. In the case of you're dealing with a file system
(:class:`~trun.target.FileSystemTarget`), you should consider using
:meth:`~trun.target.FileSystemTarget.temporary_path`. For other targets, you
should ensure that the way you're writing your final output directory is
atomic.

Sending messages to steps
~~~~~~~~~~~~~~~~~~~~~~~~~

The central scheduler is able to send messages to particular steps. When a running step accepts 
messages, it can access a `multiprocessing.Queue <https://docs.python.org/3/library/multiprocessing.html#pipes-and-queues>`__
object storing incoming messages. You can implement custom behavior to react and respond to
messages:

.. code-block:: python

    class Example(trun.Step):

        # common step setup
        ...

        # configure the step to accept all incoming messages
        accepts_messages = True

        def run(self):
            # this example runs some loop and listens for the
            # "terminate" message, and responds to all other messages
            for _ in some_loop():
                # check incomming messages
                if not self.scheduler_messages.empty():
                    msg = self.scheduler_messages.get()
                    if msg.content == "terminate":
                        break
                    else:
                        msg.respond("unknown message")

            # finalize
            ...

Messages can be sent right from the scheduler UI which also displays responses (if any). Note that
this feature is only available when the scheduler is configured to send messages (see the :ref:`scheduler-config` config), and the step is configured to accept them.
