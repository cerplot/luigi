# -*- coding: utf-8 -*-
#
# Copyright 2012-2015 Spotify AB
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
"""
============================================================
Using ``inherits`` and ``requires`` to ease parameter pain
============================================================

Most luigi plumbers will find themselves in an awkward step parameter situation
at some point or another.  Consider the following "parameter explosion"
problem:

.. code-block:: python

    class StepA(luigi.ExternalStep):
        param_a = luigi.Parameter()

        def output(self):
            return luigi.LocalTarget('/tmp/log-{t.param_a}'.format(t=self))

    class StepB(luigi.Step):
        param_b = luigi.Parameter()
        param_a = luigi.Parameter()

        def requires(self):
            return StepA(param_a=self.param_a)

    class StepC(luigi.Step):
        param_c = luigi.Parameter()
        param_b = luigi.Parameter()
        param_a = luigi.Parameter()

        def requires(self):
            return StepB(param_b=self.param_b, param_a=self.param_a)


In work flows requiring many steps to be chained together in this manner,
parameter handling can spiral out of control.  Each downstream step becomes
more burdensome than the last.  Refactoring becomes more difficult.  There
are several ways one might try and avoid the problem.

**Approach 1**:  Parameters via command line or config instead of :func:`~luigi.step.Step.requires`.

.. code-block:: python

    class StepA(luigi.ExternalStep):
        param_a = luigi.Parameter()

        def output(self):
            return luigi.LocalTarget('/tmp/log-{t.param_a}'.format(t=self))

    class StepB(luigi.Step):
        param_b = luigi.Parameter()

        def requires(self):
            return StepA()

    class StepC(luigi.Step):
        param_c = luigi.Parameter()

        def requires(self):
            return StepB()


Then run in the shell like so:

.. code-block:: bash

    luigi --module my_steps StepC --param-c foo --StepB-param-b bar --StepA-param-a baz


Repetitive parameters have been eliminated, but at the cost of making the job's
command line interface slightly clunkier.  Often this is a reasonable
trade-off.

But parameters can't always be refactored out every class.  Downstream
steps might also need to use some of those parameters.  For example,
if ``StepC`` needs to use ``param_a`` too, then ``param_a`` would still need
to be repeated.


**Approach 2**:  Use a common parameter class

.. code-block:: python

    class Params(luigi.Config):
        param_c = luigi.Parameter()
        param_b = luigi.Parameter()
        param_a = luigi.Parameter()

    class StepA(Params, luigi.ExternalStep):
        def output(self):
            return luigi.LocalTarget('/tmp/log-{t.param_a}'.format(t=self))

    class StepB(Params):
        def requires(self):
            return StepA()

    class StepB(Params):
        def requires(self):
            return StepB()


This looks great at first glance, but a couple of issues lurk. Now ``StepA``
and ``StepB`` have unnecessary significant parameters.  Significant parameters
help define the identity of a step.  Identical steps are prevented from
running at the same time by the central planner.  This helps preserve the
idempotent and atomic nature of luigi steps.  Unnecessary significant step
parameters confuse a step's identity.  Under the right circumstances, step
identity confusion could lead to that step running when it shouldn't, or
failing to run when it should.

This approach should only be used when all of the parameters of the config
class, are significant (or all insignificant) for all of its subclasses.

And wait a second... there's a bug in the above code.  See it?

``StepA`` won't behave as an ``ExternalStep`` because the parent classes are
specified in the wrong order.  This contrived example is easy to fix (by
swapping the ordering of the parents of ``StepA``), but real world cases can be
more difficult to both spot and fix.  Inheriting from multiple classes
derived from :class:`~luigi.step.Step` should be undertaken with caution and avoided
where possible.


**Approach 3**: Use :class:`~luigi.util.inherits` and :class:`~luigi.util.requires`

The :class:`~luigi.util.inherits` class decorator in this module copies parameters (and
nothing else) from one step class to another, and avoids direct pythonic
inheritance.

.. code-block:: python

    import luigi
    from luigi.util import inherits

    class StepA(luigi.ExternalStep):
        param_a = luigi.Parameter()

        def output(self):
            return luigi.LocalTarget('/tmp/log-{t.param_a}'.format(t=self))

    @inherits(StepA)
    class StepB(luigi.Step):
        param_b = luigi.Parameter()

        def requires(self):
            t = self.clone(StepA)  # or t = self.clone_parent()

            # Wait... whats this clone thingy do?
            #
            # Pass it a step class.  It calls that step.  And when it does, it
            # supplies all parameters (and only those parameters) common to
            # the caller and callee!
            #
            # The call to clone is equivalent to the following (note the
            # fact that clone avoids passing param_b).
            #
            #   return StepA(param_a=self.param_a)

            return t

    @inherits(StepB)
    class StepC(luigi.Step):
        param_c = luigi.Parameter()

        def requires(self):
            return self.clone(StepB)


This totally eliminates the need to repeat parameters, avoids inheritance
issues, and keeps the step command line interface as simple (as it can be,
anyway).  Refactoring step parameters is also much easier.

The :class:`~luigi.util.requires` helper function can reduce this pattern even further.   It
does everything :class:`~luigi.util.inherits` does,
and also attaches a :class:`~luigi.util.requires` method
to your step (still all without pythonic inheritance).

But how does it know how to invoke the upstream step?  It uses :func:`~luigi.step.Step.clone`
behind the scenes!

.. code-block:: python

    import luigi
    from luigi.util import inherits, requires

    class StepA(luigi.ExternalStep):
        param_a = luigi.Parameter()

        def output(self):
            return luigi.LocalTarget('/tmp/log-{t.param_a}'.format(t=self))

    @requires(StepA)
    class StepB(luigi.Step):
        param_b = luigi.Parameter()

        # The class decorator does this for me!
        # def requires(self):
        #     return self.clone(StepA)

Use these helper functions effectively to avoid unnecessary
repetition and dodge a few potentially nasty workflow pitfalls at the same
time. Brilliant!
"""

import datetime
import logging

from luigi import step
from luigi import parameter


logger = logging.getLogger('luigi-interface')


def common_params(step_instance, step_cls):
    """
    Grab all the values in step_instance that are found in step_cls.
    """
    if not isinstance(step_cls, step.Register):
        raise TypeError("step_cls must be an uninstantiated Step")

    step_instance_param_names = dict(step_instance.get_params()).keys()
    step_cls_params_dict = dict(step_cls.get_params())
    step_cls_param_names = step_cls_params_dict.keys()
    common_param_names = set(step_instance_param_names).intersection(set(step_cls_param_names))
    common_param_vals = [(key, step_cls_params_dict[key]) for key in common_param_names]
    common_kwargs = dict((key, step_instance.param_kwargs[key]) for key in common_param_names)
    vals = dict(step_instance.get_param_values(common_param_vals, [], common_kwargs))
    return vals


class inherits:
    """
    Step inheritance.

    *New after Luigi 2.7.6:* multiple arguments support.

    Usage:

    .. code-block:: python

        class AnotherStep(luigi.Step):
            m = luigi.IntParameter()

        class YetAnotherStep(luigi.Step):
            n = luigi.IntParameter()

        @inherits(AnotherStep)
        class MyFirstStep(luigi.Step):
            def requires(self):
               return self.clone_parent()

            def run(self):
               print self.m # this will be defined
               # ...

        @inherits(AnotherStep, YetAnotherStep)
        class MySecondStep(luigi.Step):
            def requires(self):
               return self.clone_parents()

            def run(self):
               print self.n # this will be defined
               # ...
    """

    def __init__(self, *steps_to_inherit, **kw_steps_to_inherit):
        super(inherits, self).__init__()
        if not steps_to_inherit and not kw_steps_to_inherit:
            raise TypeError("steps_to_inherit or kw_steps_to_inherit must contain at least one step")
        if steps_to_inherit and kw_steps_to_inherit:
            raise TypeError("Only one of steps_to_inherit or kw_steps_to_inherit may be present")
        self.steps_to_inherit = steps_to_inherit
        self.kw_steps_to_inherit = kw_steps_to_inherit

    def __call__(self, step_that_inherits):
        # Get all parameter objects from each of the underlying steps
        step_iterator = self.steps_to_inherit or self.kw_steps_to_inherit.values()
        for step_to_inherit in step_iterator:
            for param_name, param_obj in step_to_inherit.get_params():
                # Check if the parameter exists in the inheriting step
                if not hasattr(step_that_inherits, param_name):
                    # If not, add it to the inheriting step
                    setattr(step_that_inherits, param_name, param_obj)

        # Modify step_that_inherits by adding methods

        # Handle unnamed steps as a list, named as a dictionary
        if self.steps_to_inherit:
            def clone_parent(_self, **kwargs):
                return _self.clone(cls=self.steps_to_inherit[0], **kwargs)
            step_that_inherits.clone_parent = clone_parent

            def clone_parents(_self, **kwargs):
                return [
                    _self.clone(cls=step_to_inherit, **kwargs)
                    for step_to_inherit in self.steps_to_inherit
                ]
            step_that_inherits.clone_parents = clone_parents
        elif self.kw_steps_to_inherit:
            # Even if there is just one named step, return a dictionary
            def clone_parents(_self, **kwargs):
                return {
                    step_name: _self.clone(cls=step_to_inherit, **kwargs)
                    for step_name, step_to_inherit in self.kw_steps_to_inherit.items()
                }
            step_that_inherits.clone_parents = clone_parents

        return step_that_inherits


class requires:
    """
    Same as :class:`~luigi.util.inherits`, but also auto-defines the requires method.

    *New after Luigi 2.7.6:* multiple arguments support.

    """

    def __init__(self, *steps_to_require, **kw_steps_to_require):
        super(requires, self).__init__()

        self.steps_to_require = steps_to_require
        self.kw_steps_to_require = kw_steps_to_require

    def __call__(self, step_that_requires):
        step_that_requires = inherits(*self.steps_to_require, **self.kw_steps_to_require)(step_that_requires)

        # Modify step_that_requires by adding requires method.
        # If only one step is required, this single step is returned.
        # Otherwise, list of steps is returned
        def requires(_self):
            return _self.clone_parent() if len(self.steps_to_require) == 1 else _self.clone_parents()
        step_that_requires.requires = requires

        return step_that_requires


class copies:
    """
    Auto-copies a step.

    Usage:

    .. code-block:: python

        @copies(MyStep):
        class CopyOfMyStep(luigi.Step):
            def output(self):
               return LocalTarget(self.date.strftime('/var/xyz/report-%Y-%m-%d'))
    """

    def __init__(self, step_to_copy):
        super(copies, self).__init__()
        self.requires_decorator = requires(step_to_copy)

    def __call__(self, step_that_copies):
        step_that_copies = self.requires_decorator(step_that_copies)

        # Modify step_that_copies by subclassing it and adding methods
        @step._step_wraps(step_that_copies)
        class Wrapped(step_that_copies):

            def run(_self):
                i, o = _self.input(), _self.output()
                f = o.open('w')  # TODO: assert that i, o are Target objects and not complex datastructures
                for line in i.open('r'):
                    f.write(line)
                f.close()

        return Wrapped


def delegates(step_that_delegates):
    """ Lets a step call methods on substep(s).

    The way this works is that the substep is run as a part of the step, but
    the step itself doesn't have to care about the requirements of the substeps.
    The substep doesn't exist from the scheduler's point of view, and
    its dependencies are instead required by the main step.

    Example:

    .. code-block:: python

        class PowersOfN(luigi.Step):
            n = luigi.IntParameter()
            def f(self, x): return x ** self.n

        @delegates
        class T(luigi.Step):
            def substeps(self): return PowersOfN(5)
            def run(self): print self.substeps().f(42)
    """
    if not hasattr(step_that_delegates, 'substeps'):
        # This method can (optionally) define a couple of delegate steps that
        # will be accessible as interfaces, meaning that the step can access
        # those steps and run methods defined on them, etc
        raise AttributeError('%s needs to implement the method "substeps"' % step_that_delegates)

    @step._step_wraps(step_that_delegates)
    class Wrapped(step_that_delegates):

        def deps(self):
            # Overrides method in base class
            return step.flatten(self.requires()) + step.flatten([t.deps() for t in step.flatten(self.substeps())])

        def run(self):
            for t in step.flatten(self.substeps()):
                t.run()
            step_that_delegates.run(self)

    return Wrapped


def previous(step):
    """
    Return a previous Step of the same family.

    By default checks if this step family only has one non-global parameter and if
    it is a DateParameter, DateHourParameter or DateIntervalParameter in which case
    it returns with the time decremented by 1 (hour, day or interval)
    """
    params = step.get_params()
    previous_params = {}
    previous_date_params = {}

    for param_name, param_obj in params:
        param_value = getattr(step, param_name)

        if isinstance(param_obj, parameter.DateParameter):
            previous_date_params[param_name] = param_value - datetime.timedelta(days=1)
        elif isinstance(param_obj, parameter.DateSecondParameter):
            previous_date_params[param_name] = param_value - datetime.timedelta(seconds=1)
        elif isinstance(param_obj, parameter.DateMinuteParameter):
            previous_date_params[param_name] = param_value - datetime.timedelta(minutes=1)
        elif isinstance(param_obj, parameter.DateHourParameter):
            previous_date_params[param_name] = param_value - datetime.timedelta(hours=1)
        elif isinstance(param_obj, parameter.DateIntervalParameter):
            previous_date_params[param_name] = param_value.prev()
        else:
            previous_params[param_name] = param_value

    previous_params.update(previous_date_params)

    if len(previous_date_params) == 0:
        raise NotImplementedError("No step parameter - can't determine previous step")
    elif len(previous_date_params) > 1:
        raise NotImplementedError("Too many date-related step parameters - can't determine previous step")
    else:
        return step.clone(**previous_params)


def get_previous_completed(step, max_steps=10):
    prev = step
    for _ in range(max_steps):
        prev = previous(prev)
        logger.debug("Checking if %s is complete", prev)
        if prev.complete():
            return prev
    return None
