Steps
-----

Steps are where the execution takes place.
Steps depend on each other and output targets.

An outline of how a step can look like:

    .. figure:: step_breakdown.png
       :alt: Step breakdown

.. _Step.requires:

Step.requires
~~~~~~~~~~~~~

The :func:`~luigi.step.Step.requires` method is used to specify dependencies on other Step object,
which might even be of the same class.
For instance, an example implementation could be

.. code:: python

    def requires(self):
        return OtherStep(self.date), DailyReport(self.date - datetime.timedelta(1))

In this case, the DailyReport step depends on two inputs created earlier,
one of which is the same class.
requires can return other Steps in any way wrapped up within dicts/lists/tuples/etc.

Requiring another Step
~~~~~~~~~~~~~~~~~~~~~~

Note that :func:`~luigi.step.Step.requires` can *not* return a :class:`~luigi.target.Target` object.
If you have a simple Target object that is created externally
you can wrap it in a Step class like this:

.. code:: python

    class LogFiles(luigi.ExternalStep):
        def output(self):
            return luigi.contrib.hdfs.HdfsTarget('/log')

This also makes it easier to add parameters:

.. code:: python

    class LogFiles(luigi.ExternalStep):
        date = luigi.DateParameter()
        def output(self):
            return luigi.contrib.hdfs.HdfsTarget(self.date.strftime('/log/%Y-%m-%d'))

.. _Step.output:

Step.output
~~~~~~~~~~~

The :func:`~luigi.step.Step.output` method returns one or more :class:`~luigi.target.Target` objects.
Similarly to requires, you can return them wrapped up in any way that's convenient for you.
However we recommend that any :class:`~luigi.step.Step` only return one single :class:`~luigi.target.Target` in output.
If multiple outputs are returned,
atomicity will be lost unless the :class:`~luigi.step.Step` itself can ensure that each :class:`~luigi.target.Target` is atomically created.
(If atomicity is not of concern, then it is safe to return multiple :class:`~luigi.target.Target` objects.)

.. code:: python

    class DailyReport(luigi.Step):
        date = luigi.DateParameter()
        def output(self):
            return luigi.contrib.hdfs.HdfsTarget(self.date.strftime('/reports/%Y-%m-%d'))
        # ...

.. _Step.run:

Step.run
~~~~~~~~

The :func:`~luigi.step.Step.run` method now contains the actual code that is run.
When you are using Step.requires_ and Step.run_ Luigi breaks down everything into two stages.
First it figures out all dependencies between steps,
then it runs everything.
The :func:`~luigi.step.Step.input` method is an internal helper method that just replaces all Step objects in requires
with their corresponding output.
An example:

.. code:: python

    class GenerateWords(luigi.Step):

        def output(self):
            return luigi.LocalTarget('words.txt')

        def run(self):

            # write a dummy list of words to output file
            words = [
                    'apple',
                    'banana',
                    'grapefruit'
                    ]

            with self.output().open('w') as f:
                for word in words:
                    f.write('{word}\n'.format(word=word))


    class CountLetters(luigi.Step):

        def requires(self):
            return GenerateWords()

        def output(self):
            return luigi.LocalTarget('letter_counts.txt')

        def run(self):

            # read in file as list
            with self.input().open('r') as infile:
                words = infile.read().splitlines()

            # write each word to output file with its corresponding letter count
            with self.output().open('w') as outfile:
                for word in words:
                    outfile.write(
                            '{word} | {letter_count}\n'.format(
                                word=word,
                                letter_count=len(word)
                                )
                            )

It's useful to note that if you're writing to a binary file, Luigi automatically
strips the ``'b'`` flag due to how atomic writes/reads work. In order to write a binary
file, such as a pickle file, you should instead use ``format=Nop`` when calling
LocalTarget. Following the above example:

.. code:: python

    from luigi.format import Nop

    class GenerateWords(luigi.Step):

        def output(self):
            return luigi.LocalTarget('words.pckl', format=Nop)

        def run(self):
            import pickle

            # write a dummy list of words to output file
            words = [
                    'apple',
                    'banana',
                    'grapefruit'
                    ]

            with self.output().open('w') as f:
                pickle.dump(words, f)


It is your responsibility to ensure that after running :func:`~luigi.step.Step.run`, the step is
complete, i.e. :func:`~luigi.step.Step.complete` returns ``True``. Unless you have overridden
:func:`~luigi.step.Step.complete`, :func:`~luigi.step.Step.run` should generate all the targets
defined as outputs. Luigi verifies that you adhere to the contract before running downstream
dependencies, and reports ``Unfulfilled dependencies at run time`` if a violation is detected.

.. _Step.input:

Step.input
~~~~~~~~~~

As seen in the example above, :func:`~luigi.step.Step.input` is a wrapper around Step.requires_ that
returns the corresponding Target objects instead of Step objects.
Anything returned by Step.requires_ will be transformed, including lists,
nested dicts, etc.
This can be useful if you have many dependencies:

.. code:: python

    class StepWithManyInputs(luigi.Step):
        def requires(self):
            return {'a': StepA(), 'b': [StepB(i) for i in xrange(100)]}

        def run(self):
            f = self.input()['a'].open('r')
            g = [y.open('r') for y in self.input()['b']]


Dynamic dependencies
~~~~~~~~~~~~~~~~~~~~

Sometimes you might not know exactly what other steps to depend on until runtime.
In that case, Luigi provides a mechanism to specify dynamic dependencies.
If you yield another :class:`~luigi.step.Step` in the Step.run_ method,
the current step will be suspended and the other step will be run.
You can also yield a list of steps.

.. code:: python

    class MyStep(luigi.Step):
        def run(self):
            other_target = yield OtherStep()

            # dynamic dependencies resolve into targets
            f = other_target.open('r')


This mechanism is an alternative to Step.requires_ in case
you are not able to build up the full dependency graph before running the step.
It does come with some constraints:
the Step.run_ method will resume from scratch each time a new step is yielded.
In other words, you should make sure your Step.run_ method is idempotent.
(This is good practice for all Steps in Luigi, but especially so for steps with dynamic dependencies).
As this might entail redundant calls to steps' :func:`~luigi.step.Step.complete` methods,
you should consider setting the "cache_step_completion" option in the :ref:`worker-config`.
To further control how dynamic step requirements are handled internally by worker nodes,
there is also the option to wrap dependent steps by :class:`~luigi.step.DynamicRequirements`.

For an example of a workflow using dynamic dependencies, see
`examples/dynamic_requirements.py <https://github.com/spotify/luigi/blob/master/examples/dynamic_requirements.py>`_.


Step status tracking
~~~~~~~~~~~~~~~~~~~~

For long-running or remote steps it is convenient to see extended status information not only on
the command line or in your logs but also in the GUI of the central scheduler. Luigi implements
dynamic status messages, progress bar and tracking urls which may point to an external monitoring system.
You can set this information using callbacks within Step.run_:

.. code:: python

    class MyStep(luigi.Step):
        def run(self):
            # set a tracking url
            self.set_tracking_url("http://...")

            # set status messages during the workload
            for i in range(100):
                # do some hard work here
                if i % 10 == 0:
                    self.set_status_message("Progress: %d / 100" % i)
                    # displays a progress bar in the scheduler UI
                    self.set_progress_percentage(i)


.. _Events:

Events and callbacks
~~~~~~~~~~~~~~~~~~~~

Luigi has a built-in event system that
allows you to register callbacks to events and trigger them from your own steps.
You can both hook into some pre-defined events and create your own.
Each event handle is tied to a Step class and
will be triggered only from that class or
a subclass of it.
This allows you to effortlessly subscribe to events only from a specific class (e.g. for hadoop jobs).

.. code:: python

    @luigi.Step.event_handler(luigi.Event.SUCCESS)
    def celebrate_success(step):
        """Will be called directly after a successful execution
           of `run` on any Step subclass (i.e. all luigi Steps)
        """
        ...

    @luigi.contrib.hadoop.JobStep.event_handler(luigi.Event.FAILURE)
    def mourn_failure(step, exception):
        """Will be called directly after a failed execution
           of `run` on any JobStep subclass
        """
        ...

    luigi.run()


But I just want to run a Hadoop job?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The Hadoop code is integrated in the rest of the Luigi code because
we really believe almost all Hadoop jobs benefit from being part of some sort of workflow.
However, in theory, nothing stops you from using the :class:`~luigi.contrib.hadoop.JobStep` class (and also :class:`~luigi.contrib.hdfs.target.HdfsTarget`)
without using the rest of Luigi.
You can simply run it manually using

.. code:: python

    MyJobStep('abc', 123).run()

You can use the hdfs.target.HdfsTarget class anywhere by just instantiating it:

.. code:: python

    t = luigi.contrib.hdfs.target.HdfsTarget('/tmp/test.gz', format=format.Gzip)
    f = t.open('w')
    # ...
    f.close() # needed

.. _Step.priority:

Step priority
~~~~~~~~~~~~~

The scheduler decides which step to run next from
the set of all steps that have all their dependencies met.
By default, this choice is pretty arbitrary,
which is fine for most workflows and situations.

If you want to have some control on the order of execution of available steps,
you can set the ``priority`` property of a step,
for example as follows:

.. code:: python

    # A static priority value as a class constant:
    class MyStep(luigi.Step):
        priority = 100
        # ...

    # A dynamic priority value with a "@property" decorated method:
    class OtherStep(luigi.Step):
        @property
        def priority(self):
            if self.date > some_threshold:
                return 80
            else:
                return 40
        # ...

Steps with a higher priority value will be picked before steps with a lower priority value.
There is no predefined range of priorities,
you can choose whatever (int or float) values you want to use.
The default value is 0.

Warning: step execution order in Luigi is influenced by both dependencies and priorities, but
in Luigi dependencies come first.
For example:
if there is a step A with priority 1000 but still with unmet dependencies and
a step B with priority 1 without any pending dependencies,
step B will be picked first.

.. _Step.namespaces_famlies_and_ids:

Namespaces, families and ids
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

In order to avoid name clashes and to be able to have an identifier for steps,
Luigi introduces the concepts *step_namespace*, *step_family* and
*step_id*. The namespace and family operate on class level meanwhile the step
id only exists on instance level. The concepts are best illustrated using code.

.. code:: python

    import luigi
    class MyStep(luigi.Step):
        my_param = luigi.Parameter()
        step_namespace = 'my_namespace'

    my_step = MyStep(my_param='hello')
    print(my_step)                      # --> my_namespace.MyStep(my_param=hello)

    print(my_step.get_step_namespace()) # --> my_namespace
    print(my_step.get_step_family())    # --> my_namespace.MyStep
    print(my_step.step_id)              # --> my_namespace.MyStep_hello_890907e7ce

    print(MyStep.get_step_namespace())  # --> my_namespace
    print(MyStep.get_step_family())     # --> my_namespace.MyStep
    print(MyStep.step_id)               # --> Error!

The full documentation for this machinery exists in the :py:mod:`~luigi.step` module.

Instance caching
~~~~~~~~~~~~~~~~

In addition to the stuff mentioned above,
Luigi also does some metaclass logic so that
if e.g. ``DailyReport(datetime.date(2012, 5, 10))`` is instantiated twice in the code,
it will in fact result in the same object.
See :ref:`Parameter-instance-caching` for more info
