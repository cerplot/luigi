Parameters
----------

Parameters is the Trun equivalent of creating a constructor for each Step.
Trun requires you to declare these parameters by instantiating
:class:`~trun.parameter.Parameter` objects on the class scope:

.. code:: python

    class DailyReport(trun.contrib.hadoop.JobStep):
        date = trun.DateParameter(default=datetime.date.today())
        # ...

By doing this, Trun can take care of all the boilerplate code that
would normally be needed in the constructor.
Internally, the DailyReport object can now be constructed by running
``DailyReport(datetime.date(2012, 5, 10))`` or just ``DailyReport()``.
Trun also creates a command line parser that automatically handles the
conversion from strings to Python types.
This way you can invoke the job on the command line eg. by passing ``--date 2012-05-10``.

The parameters are all set to their values on the Step object instance,
i.e.

.. code:: python

    d = DailyReport(datetime.date(2012, 5, 10))
    print(d.date)

will return the same date that the object was constructed with.
Same goes if you invoke Trun on the command line.

.. _Parameter-instance-caching:

Instance caching
^^^^^^^^^^^^^^^^

Steps are uniquely identified by their class name and values of their
parameters.
In fact, within the same worker, two steps of the same class with
parameters of the same values are not just equal, but the same instance:

.. code:: python

    >>> import trun
    >>> import datetime
    >>> class DateStep(trun.Step):
    ...   date = trun.DateParameter()
    ...
    >>> a = datetime.date(2014, 1, 21)
    >>> b = datetime.date(2014, 1, 21)
    >>> a is b
    False
    >>> c = DateStep(date=a)
    >>> d = DateStep(date=b)
    >>> c
    DateStep(date=2014-01-21)
    >>> d
    DateStep(date=2014-01-21)
    >>> c is d
    True

Insignificant parameters
^^^^^^^^^^^^^^^^^^^^^^^^

If a parameter is created with ``significant=False``,
it is ignored as far as the Step signature is concerned.
Steps created with only insignificant parameters differing have the same signature but
are not the same instance:

.. code:: python

    >>> class DateStep2(DateStep):
    ...   other = trun.Parameter(significant=False)
    ...
    >>> c = DateStep2(date=a, other="foo")
    >>> d = DateStep2(date=b, other="bar")
    >>> c
    DateStep2(date=2014-01-21)
    >>> d
    DateStep2(date=2014-01-21)
    >>> c.other
    'foo'
    >>> d.other
    'bar'
    >>> c is d
    False
    >>> hash(c) == hash(d)
    True

Parameter visibility
^^^^^^^^^^^^^^^^^^^^

Using :class:`~trun.parameter.ParameterVisibility` you can configure parameter visibility. By default, all
parameters are public, but you can also set them hidden or private.

.. code:: python

    >>> import trun
    >>> from trun.parameter import ParameterVisibility
    
    >>> trun.Parameter(visibility=ParameterVisibility.PRIVATE)

``ParameterVisibility.PUBLIC`` (default) - visible everywhere

``ParameterVisibility.HIDDEN`` - ignored in WEB-view, but saved into database if save db_history is true

``ParameterVisibility.PRIVATE`` - visible only inside step.

Parameter types
^^^^^^^^^^^^^^^

In the examples above, the *type* of the parameter is determined by using different
subclasses of :class:`~trun.parameter.Parameter`. There are a few of them, like
:class:`~trun.parameter.DateParameter`,
:class:`~trun.parameter.DateIntervalParameter`,
:class:`~trun.parameter.IntParameter`,
:class:`~trun.parameter.FloatParameter`, etc.

Python is not a statically typed language and you don't have to specify the types
of any of your parameters.
You can simply use the base class :class:`~trun.parameter.Parameter` if you don't care.

The reason you would use a subclass like :class:`~trun.parameter.DateParameter`
is that Trun needs to know its type for the command line interaction.
That's how it knows how to convert a string provided on the command line to
the corresponding type (i.e. datetime.date instead of a string).

.. _Parameter-class-level-parameters:

Setting parameter value for other classes
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

All parameters are also exposed on a class level on the command line interface.
For instance, say you have classes StepA and StepB:

.. code:: python

    class StepA(trun.Step):
        x = trun.Parameter()

    class StepB(trun.Step):
        y = trun.Parameter()


You can run ``StepB`` on the command line: ``trun StepB --y 42``.
But you can also set the class value of ``StepA`` by running
``trun StepB --y 42 --StepA-x 43``.
This sets the value of ``StepA.x`` to 43 on a *class* level.
It is still possible to override it inside Python if you instantiate ``StepA(x=44)``.

All parameters can also be set from the configuration file.
For instance, you can put this in the config:

.. code:: ini

    [StepA]
    x: 45


Just as in the previous case, this will set the value of ``StepA.x`` to 45 on the *class* level.
And likewise, it is still possible to override it inside Python if you instantiate ``StepA(x=44)``.

Parameter resolution order
^^^^^^^^^^^^^^^^^^^^^^^^^^

Parameters are resolved in the following order of decreasing priority:

1. Any value passed to the constructor, or step level value set on the command line (applies on an instance level)
2. Any value set on the command line (applies on a class level)
3. Any configuration option (applies on a class level)
4. Any default value provided to the parameter (applies on a class level)

See the :class:`~trun.parameter.Parameter` class for more information.
