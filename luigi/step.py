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
The abstract :py:class:`Step` class.
It is a central concept of Luigi and represents the state of the workflow.
See :doc:`/steps` for an overview.
"""
from collections import deque, OrderedDict
from contextlib import contextmanager
import logging
import traceback
import warnings
import json
import hashlib
import re
import copy
import functools

import luigi

from luigi import configuration
from luigi import parameter
from luigi.step_register import Register
from luigi.parameter import ParameterVisibility
from luigi.parameter import UnconsumedParameterWarning

Parameter = parameter.Parameter
logger = logging.getLogger('luigi-interface')


STEP_ID_INCLUDE_PARAMS = 3
STEP_ID_TRUNCATE_PARAMS = 16
STEP_ID_TRUNCATE_HASH = 10
STEP_ID_INVALID_CHAR_REGEX = re.compile(r'[^A-Za-z0-9_]')
_SAME_AS_PYTHON_MODULE = '_same_as_python_module'


def namespace(namespace=None, scope=''):
    """
    Call to set namespace of steps declared after the call.

    It is often desired to call this function with the keyword argument
    ``scope=__name__``.

    The ``scope`` keyword makes it so that this call is only effective for step
    classes with a matching [*]_ ``__module__``. The default value for
    ``scope`` is the empty string, which means all classes. Multiple calls with
    the same scope simply replace each other.

    The namespace of a :py:class:`Step` can also be changed by specifying the property
    ``step_namespace``.

    .. code-block:: python

        class Step2(luigi.Step):
            step_namespace = 'namespace2'

    This explicit setting takes priority over whatever is set in the
    ``namespace()`` method, and it's also inherited through normal python
    inheritence.

    There's no equivalent way to set the ``step_family``.

    *New since Luigi 2.6.0:* ``scope`` keyword argument.

    .. [*] When there are multiple levels of matching module scopes like
           ``a.b`` vs ``a.b.c``, the more specific one (``a.b.c``) wins.
    .. seealso:: The new and better scaling :py:func:`auto_namespace`
    """
    Register._default_namespace_dict[scope] = namespace or ''


def auto_namespace(scope=''):
    """
    Same as :py:func:`namespace`, but instead of a constant namespace, it will
    be set to the ``__module__`` of the step class. This is desirable for these
    reasons:

     * Two steps with the same name will not have conflicting step families
     * It's more pythonic, as modules are Python's recommended way to
       do namespacing.
     * It's traceable. When you see the full name of a step, you can immediately
       identify where it is defined.

    We recommend calling this function from your package's outermost
    ``__init__.py`` file. The file contents could look like this:

    .. code-block:: python

        import luigi

        luigi.auto_namespace(scope=__name__)

    To reset an ``auto_namespace()`` call, you can use
    ``namespace(scope='my_scope')``.  But this will not be
    needed (and is also discouraged) if you use the ``scope`` kwarg.

    *New since Luigi 2.6.0.*
    """
    namespace(namespace=_SAME_AS_PYTHON_MODULE, scope=scope)


def step_id_str(step_family, params):
    """
    Returns a canonical string used to identify a particular step

    :param step_family: The step family (class name) of the step
    :param params: a dict mapping parameter names to their serialized values
    :return: A unique, shortened identifier corresponding to the family and params
    """
    # step_id is a concatenation of step family, the first values of the first 3 parameters
    # sorted by parameter name and a md5hash of the family/parameters as a cananocalised json.
    param_str = json.dumps(params, separators=(',', ':'), sort_keys=True)
    param_hash = hashlib.new('md5', param_str.encode('utf-8'), usedforsecurity=False).hexdigest()

    param_summary = '_'.join(p[:STEP_ID_TRUNCATE_PARAMS]
                             for p in (params[p] for p in sorted(params)[:STEP_ID_INCLUDE_PARAMS]))
    param_summary = STEP_ID_INVALID_CHAR_REGEX.sub('_', param_summary)

    return '{}_{}_{}'.format(step_family, param_summary, param_hash[:STEP_ID_TRUNCATE_HASH])


class BulkCompleteNotImplementedError(NotImplementedError):
    """This is here to trick pylint.

    pylint thinks anything raising NotImplementedError needs to be implemented
    in any subclass. bulk_complete isn't like that. This tricks pylint into
    thinking that the default implementation is a valid implementation and not
    an abstract method."""
    pass


class Step(metaclass=Register):
    """
    This is the base class of all Luigi Steps, the base unit of work in Luigi.

    A Luigi Step describes a unit or work.

    The key methods of a Step, which must be implemented in a subclass are:

    * :py:meth:`run` - the computation done by this step.
    * :py:meth:`requires` - the list of Steps that this Step depends on.
    * :py:meth:`output` - the output :py:class:`Target` that this Step creates.

    Each :py:class:`~luigi.Parameter` of the Step should be declared as members:

    .. code:: python

        class MyStep(luigi.Step):
            count = luigi.IntParameter()
            second_param = luigi.Parameter()

    In addition to any declared properties and methods, there are a few
    non-declared properties, which are created by the :py:class:`Register`
    metaclass:

    """

    _event_callbacks = {}

    #: Priority of the step: the scheduler should favor available
    #: steps with higher priority values first.
    #: See :ref:`Step.priority`
    priority = 0
    disabled = False

    #: Resources used by the step. Should be formatted like {"scp": 1} to indicate that the
    #: step requires 1 unit of the scp resource.
    resources = {}

    #: Number of seconds after which to time out the run function.
    #: No timeout if set to 0.
    #: Defaults to 0 or worker-timeout value in config
    worker_timeout = None

    #: Maximum number of steps to run together as a batch. Infinite by default
    max_batch_size = float('inf')

    @property
    def batchable(self):
        """
        True if this instance can be run as part of a batch. By default, True
        if it has any batched parameters
        """
        return bool(self.batch_param_names())

    @property
    def retry_count(self):
        """
        Override this positive integer to have different ``retry_count`` at step level
        Check :ref:`scheduler-config`
        """
        return None

    @property
    def disable_hard_timeout(self):
        """
        Override this positive integer to have different ``disable_hard_timeout`` at step level.
        Check :ref:`scheduler-config`
        """
        return None

    @property
    def disable_window(self):
        """
        Override this positive integer to have different ``disable_window`` at step level.
        Check :ref:`scheduler-config`
        """
        return None

    @property
    def disable_window_seconds(self):
        warnings.warn("Use of `disable_window_seconds` has been deprecated, use `disable_window` instead", DeprecationWarning)
        return self.disable_window

    @property
    def owner_email(self):
        '''
        Override this to send out additional error emails to step owner, in addition to the one
        defined in the global configuration. This should return a string or a list of strings. e.g.
        'test@exmaple.com' or ['test1@example.com', 'test2@example.com']
        '''
        return None

    def _owner_list(self):
        """
        Turns the owner_email property into a list. This should not be overridden.
        """
        owner_email = self.owner_email
        if owner_email is None:
            return []
        elif isinstance(owner_email, str):
            return owner_email.split(',')
        else:
            return owner_email

    @property
    def use_cmdline_section(self):
        ''' Property used by core config such as `--workers` etc.
        These will be exposed without the class as prefix.'''
        return True

    @classmethod
    def event_handler(cls, event):
        """
        Decorator for adding event handlers.
        """
        def wrapped(callback):
            cls._event_callbacks.setdefault(cls, {}).setdefault(event, set()).add(callback)
            return callback
        return wrapped

    def trigger_event(self, event, *args, **kwargs):
        """
        Trigger that calls all of the specified events associated with this class.
        """
        for event_class, event_callbacks in self._event_callbacks.items():
            if not isinstance(self, event_class):
                continue
            for callback in event_callbacks.get(event, []):
                try:
                    # callbacks are protected
                    callback(*args, **kwargs)
                except KeyboardInterrupt:
                    return
                except BaseException:
                    logger.exception("Error in event callback for %r", event)

    @property
    def accepts_messages(self):
        """
        For configuring which scheduler messages can be received. When falsy, this steps does not
        accept any message. When True, all messages are accepted.
        """
        return False

    @property
    def step_module(self):
        ''' Returns what Python module to import to get access to this class. '''
        # TODO(erikbern): we should think about a language-agnostic mechanism
        return self.__class__.__module__

    _visible_in_registry = True  # TODO: Consider using in luigi.util as well

    __not_user_specified = '__not_user_specified'

    # This is here just to help pylint, the Register metaclass will always set
    # this value anyway.
    _namespace_at_class_time = None

    step_namespace = __not_user_specified
    """
    This value can be overridden to set the namespace that will be used.
    (See :ref:`Step.namespaces_famlies_and_ids`)
    If it's not specified and you try to read this value anyway, it will return
    garbage. Please use :py:meth:`get_step_namespace` to read the namespace.

    Note that setting this value with ``@property`` will not work, because this
    is a class level value.
    """

    @classmethod
    def get_step_namespace(cls):
        """
        The step family for the given class.

        Note: You normally don't want to override this.
        """
        if cls.step_namespace != cls.__not_user_specified:
            return cls.step_namespace
        elif cls._namespace_at_class_time == _SAME_AS_PYTHON_MODULE:
            return cls.__module__
        return cls._namespace_at_class_time

    @property
    def step_family(self):
        """
        DEPRECATED since after 2.4.0. See :py:meth:`get_step_family` instead.
        Hopefully there will be less meta magic in Luigi.

        Convenience method since a property on the metaclass isn't directly
        accessible through the class instances.
        """
        return self.__class__.step_family

    @classmethod
    def get_step_family(cls):
        """
        The step family for the given class.

        If ``step_namespace`` is not set, then it's simply the name of the
        class.  Otherwise, ``<step_namespace>.`` is prefixed to the class name.

        Note: You normally don't want to override this.
        """
        if not cls.get_step_namespace():
            return cls.__name__
        else:
            return "{}.{}".format(cls.get_step_namespace(), cls.__name__)

    @classmethod
    def get_params(cls):
        """
        Returns all of the Parameters for this Step.
        """
        # We want to do this here and not at class instantiation, or else there is no room to extend classes dynamically
        params = []
        for param_name in dir(cls):
            param_obj = getattr(cls, param_name)
            if not isinstance(param_obj, Parameter):
                continue

            params.append((param_name, param_obj))

        # The order the parameters are created matters. See Parameter class
        params.sort(key=lambda t: t[1]._counter)
        return params

    @classmethod
    def batch_param_names(cls):
        return [name for name, p in cls.get_params() if p._is_batchable()]

    @classmethod
    def get_param_names(cls, include_significant=False):
        return [name for name, p in cls.get_params() if include_significant or p.significant]

    @classmethod
    def get_param_values(cls, params, args, kwargs):
        """
        Get the values of the parameters from the args and kwargs.

        :param params: list of (param_name, Parameter).
        :param args: positional arguments
        :param kwargs: keyword arguments.
        :returns: list of `(name, value)` tuples, one for each parameter.
        """
        result = {}

        params_dict = dict(params)

        step_family = cls.get_step_family()

        # In case any exceptions are thrown, create a helpful description of how the Step was invoked
        # TODO: should we detect non-reprable arguments? These will lead to mysterious errors
        exc_desc = '%s[args=%s, kwargs=%s]' % (step_family, args, kwargs)

        # Fill in the positional arguments
        positional_params = [(n, p) for n, p in params if p.positional]
        for i, arg in enumerate(args):
            if i >= len(positional_params):
                raise parameter.UnknownParameterException('%s: takes at most %d parameters (%d given)' % (exc_desc, len(positional_params), len(args)))
            param_name, param_obj = positional_params[i]
            result[param_name] = param_obj.normalize(arg)

        # Then the keyword arguments
        for param_name, arg in kwargs.items():
            if param_name in result:
                raise parameter.DuplicateParameterException('%s: parameter %s was already set as a positional parameter' % (exc_desc, param_name))
            if param_name not in params_dict:
                raise parameter.UnknownParameterException('%s: unknown parameter %s' % (exc_desc, param_name))
            result[param_name] = params_dict[param_name].normalize(arg)

        # Then use the defaults for anything not filled in
        for param_name, param_obj in params:
            if param_name not in result:
                try:
                    has_step_value = param_obj.has_step_value(step_family, param_name)
                except Exception as exc:
                    raise ValueError("%s: Error when parsing the default value of '%s'" % (exc_desc, param_name)) from exc
                if not has_step_value:
                    raise parameter.MissingParameterException("%s: requires the '%s' parameter to be set" % (exc_desc, param_name))
                result[param_name] = param_obj.step_value(step_family, param_name)

        def list_to_tuple(x):
            """ Make tuples out of lists and sets to allow hashing """
            if isinstance(x, list) or isinstance(x, set):
                return tuple(x)
            else:
                return x

        # Check for unconsumed parameters
        conf = configuration.get_config()
        if not hasattr(cls, "_unconsumed_params"):
            cls._unconsumed_params = set()
        if step_family in conf.sections():
            ignore_unconsumed = getattr(cls, 'ignore_unconsumed', set())
            for key, value in conf[step_family].items():
                key = key.replace('-', '_')
                composite_key = f"{step_family}_{key}"
                if key not in result and key not in ignore_unconsumed and composite_key not in cls._unconsumed_params:
                    warnings.warn(
                        "The configuration contains the parameter "
                        f"'{key}' with value '{value}' that is not consumed by the step "
                        f"'{step_family}'.",
                        UnconsumedParameterWarning,
                    )
                    cls._unconsumed_params.add(composite_key)

        # Sort it by the correct order and make a list
        return [(param_name, list_to_tuple(result[param_name])) for param_name, param_obj in params]

    def __init__(self, *args, **kwargs):
        params = self.get_params()
        param_values = self.get_param_values(params, args, kwargs)

        # Set all values on class instance
        for key, value in param_values:
            setattr(self, key, value)

        # Register kwargs as an attribute on the class. Might be useful
        self.param_kwargs = dict(param_values)

        self._warn_on_wrong_param_types()
        self.step_id = step_id_str(self.get_step_family(), self.to_str_params(only_significant=True, only_public=True))
        self.__hash = hash(self.step_id)

        self.set_tracking_url = None
        self.set_status_message = None
        self.set_progress_percentage = None

    @property
    def param_args(self):
        warnings.warn("Use of param_args has been deprecated.", DeprecationWarning)
        return tuple(self.param_kwargs[k] for k, v in self.get_params())

    def initialized(self):
        """
        Returns ``True`` if the Step is initialized and ``False`` otherwise.
        """
        return hasattr(self, 'step_id')

    def _warn_on_wrong_param_types(self):
        params = dict(self.get_params())
        for param_name, param_value in self.param_kwargs.items():
            params[param_name]._warn_on_wrong_param_type(param_name, param_value)

    @classmethod
    def from_str_params(cls, params_str):
        """
        Creates an instance from a str->str hash.

        :param params_str: dict of param name -> value as string.
        """
        kwargs = {}
        for param_name, param in cls.get_params():
            if param_name in params_str:
                param_str = params_str[param_name]
                if isinstance(param_str, list):
                    kwargs[param_name] = param._parse_list(param_str)
                else:
                    kwargs[param_name] = param.parse(param_str)

        return cls(**kwargs)

    def to_str_params(self, only_significant=False, only_public=False):
        """
        Convert all parameters to a str->str hash.
        """
        params_str = {}
        params = dict(self.get_params())
        for param_name, param_value in self.param_kwargs.items():
            if (((not only_significant) or params[param_name].significant)
                    and ((not only_public) or params[param_name].visibility == ParameterVisibility.PUBLIC)
                    and params[param_name].visibility != ParameterVisibility.PRIVATE):
                params_str[param_name] = params[param_name].serialize(param_value)

        return params_str

    def _get_param_visibilities(self):
        param_visibilities = {}
        params = dict(self.get_params())
        for param_name, param_value in self.param_kwargs.items():
            if params[param_name].visibility != ParameterVisibility.PRIVATE:
                param_visibilities[param_name] = params[param_name].visibility.serialize()

        return param_visibilities

    def clone(self, cls=None, **kwargs):
        """
        Creates a new instance from an existing instance where some of the args have changed.

        There's at least two scenarios where this is useful (see test/clone_test.py):

        * remove a lot of boiler plate when you have recursive dependencies and lots of args
        * there's step inheritance and some logic is on the base class

        :param cls:
        :param kwargs:
        :return:
        """
        if cls is None:
            cls = self.__class__

        new_k = {}
        for param_name, param_class in cls.get_params():
            if param_name in kwargs:
                new_k[param_name] = kwargs[param_name]
            elif hasattr(self, param_name):
                new_k[param_name] = getattr(self, param_name)

        return cls(**new_k)

    def __hash__(self):
        return self.__hash

    def __repr__(self):
        """
        Build a step representation like `MyStep(param1=1.5, param2='5')`
        """
        params = self.get_params()
        param_values = self.get_param_values(params, [], self.param_kwargs)

        # Build up step id
        repr_parts = []
        param_objs = dict(params)
        for param_name, param_value in param_values:
            if param_objs[param_name].significant:
                repr_parts.append('%s=%s' % (param_name, param_objs[param_name].serialize(param_value)))

        step_str = '{}({})'.format(self.get_step_family(), ', '.join(repr_parts))

        return step_str

    def __eq__(self, other):
        return self.__class__ == other.__class__ and self.step_id == other.step_id

    def complete(self):
        """
        If the step has any outputs, return ``True`` if all outputs exist.
        Otherwise, return ``False``.

        However, you may freely override this method with custom logic.
        """
        outputs = flatten(self.output())
        if len(outputs) == 0:
            warnings.warn(
                "Step %r without outputs has no custom complete() method" % self,
                stacklevel=2
            )
            return False

        return all(map(lambda output: output.exists(), outputs))

    @classmethod
    def bulk_complete(cls, parameter_tuples):
        """
        Returns those of parameter_tuples for which this Step is complete.

        Override (with an efficient implementation) for efficient scheduling
        with range tools. Keep the logic consistent with that of complete().
        """
        raise BulkCompleteNotImplementedError()

    def output(self):
        """
        The output that this Step produces.

        The output of the Step determines if the Step needs to be run--the step
        is considered finished iff the outputs all exist. Subclasses should
        override this method to return a single :py:class:`Target` or a list of
        :py:class:`Target` instances.

        Implementation note
          If running multiple workers, the output must be a resource that is accessible
          by all workers, such as a DFS or database. Otherwise, workers might compute
          the same output since they don't see the work done by other workers.

        See :ref:`Step.output`
        """
        return []  # default impl

    def requires(self):
        """
        The Steps that this Step depends on.

        A Step will only run if all of the Steps that it requires are completed.
        If your Step does not require any other Steps, then you don't need to
        override this method. Otherwise, a subclass can override this method
        to return a single Step, a list of Step instances, or a dict whose
        values are Step instances.

        See :ref:`Step.requires`
        """
        return []  # default impl

    def _requires(self):
        """
        Override in "template" steps which themselves are supposed to be
        subclassed and thus have their requires() overridden (name preserved to
        provide consistent end-user experience), yet need to introduce
        (non-input) dependencies.

        Must return an iterable which among others contains the _requires() of
        the superclass.
        """
        return flatten(self.requires())  # base impl

    def process_resources(self):
        """
        Override in "template" steps which provide common resource functionality
        but allow subclasses to specify additional resources while preserving
        the name for consistent end-user experience.
        """
        return self.resources  # default impl

    def input(self):
        """
        Returns the outputs of the Steps returned by :py:meth:`requires`

        See :ref:`Step.input`

        :return: a list of :py:class:`Target` objects which are specified as
                 outputs of all required Steps.
        """
        return getpaths(self.requires())

    def deps(self):
        """
        Internal method used by the scheduler.

        Returns the flattened list of requires.
        """
        # used by scheduler
        return flatten(self._requires())

    def run(self):
        """
        The step run method, to be overridden in a subclass.

        See :ref:`Step.run`
        """
        pass  # default impl

    def on_failure(self, exception):
        """
        Override for custom error handling.

        This method gets called if an exception is raised in :py:meth:`run`.
        The returned value of this method is json encoded and sent to the scheduler
        as the `expl` argument. Its string representation will be used as the
        body of the error email sent out if any.

        Default behavior is to return a string representation of the stack trace.
        """

        traceback_string = traceback.format_exc()
        return "Runtime error:\n%s" % traceback_string

    def on_success(self):
        """
        Override for doing custom completion handling for a larger class of steps

        This method gets called when :py:meth:`run` completes without raising any exceptions.

        The returned value is json encoded and sent to the scheduler as the `expl` argument.

        Default behavior is to send an None value"""
        pass

    @contextmanager
    def no_unpicklable_properties(self):
        """
        Remove unpicklable properties before dump step and resume them after.

        This method could be called in substep's dump method, to ensure unpicklable
        properties won't break dump.

        This method is a context-manager which can be called as below:

        .. code-block: python

            class DummyStep(luigi):

                def _dump(self):
                    with self.no_unpicklable_properties():
                        pickle.dumps(self)

        """
        unpicklable_properties = tuple(luigi.worker.StepProcess.forward_reporter_attributes.values())
        reserved_properties = {}
        for property_name in unpicklable_properties:
            if hasattr(self, property_name):
                reserved_properties[property_name] = getattr(self, property_name)
                setattr(self, property_name, 'placeholder_during_pickling')

        yield

        for property_name, value in reserved_properties.items():
            setattr(self, property_name, value)


class MixinNaiveBulkComplete:
    """
    Enables a Step to be efficiently scheduled with e.g. range tools, by providing a bulk_complete implementation which checks completeness in a loop.

    Applicable to steps whose completeness checking is cheap.

    This doesn't exploit output location specific APIs for speed advantage, nevertheless removes redundant scheduler roundtrips.
    """
    @classmethod
    def bulk_complete(cls, parameter_tuples):
        generated_tuples = []
        for parameter_tuple in parameter_tuples:
            if isinstance(parameter_tuple, (list, tuple)):
                if cls(*parameter_tuple).complete():
                    generated_tuples.append(parameter_tuple)
            elif isinstance(parameter_tuple, dict):
                if cls(**parameter_tuple).complete():
                    generated_tuples.append(parameter_tuple)
            else:
                if cls(parameter_tuple).complete():
                    generated_tuples.append(parameter_tuple)
        return generated_tuples


class DynamicRequirements(object):
    """
    Wraps dynamic requirements yielded in steps's run methods to control how completeness checks of
    (e.g.) large chunks of steps are performed. Besides the wrapped *requirements*, instances of
    this class can be passed an optional function *custom_complete* that might implement an
    optimized check for completeness. If set, the function will be called with a single argument,
    *complete_fn*, which should be used to perform the per-step check. Example:

    .. code-block:: python

        class SomeStepWithDynamicRequirements(luigi.Step):
            ...

            def run(self):
                large_chunk_of_steps = [OtherStep(i=i) for i in range(10000)]

                def custom_complete(complete_fn):
                    # example: assume OtherStep always write into the same directory, so just check
                    #          if the first step is complete, and compare basenames for the rest
                    if not complete_fn(large_chunk_of_steps[0]):
                        return False
                    paths = [step.output().path for step in large_chunk_of_steps]
                    basenames = os.listdir(os.path.dirname(paths[0]))  # a single fs call
                    return all(os.path.basename(path) in basenames for path in paths)

                yield DynamicRequirements(large_chunk_of_steps, custom_complete)

    .. py:attribute:: requirements

        The original, wrapped requirements.

    .. py:attribute:: flat_requirements

        Flattened view of the wrapped requirements (via :py:func:`flatten`). Read only.

    .. py:attribute:: paths

        Outputs of the requirements in the identical structure (via :py:func:`getpaths`). Read only.

    .. py:attribute:: custom_complete

       The optional, custom function performing the completeness check of the wrapped requirements.
    """

    def __init__(self, requirements, custom_complete=None):
        super().__init__()

        # store attributes
        self.requirements = requirements
        self.custom_complete = custom_complete

        # cached flat requirements and paths
        self._flat_requirements = None
        self._paths = None

    @property
    def flat_requirements(self):
        if self._flat_requirements is None:
            self._flat_requirements = flatten(self.requirements)
        return self._flat_requirements

    @property
    def paths(self):
        if self._paths is None:
            self._paths = getpaths(self.requirements)
        return self._paths

    def complete(self, complete_fn=None):
        # default completeness check
        if complete_fn is None:
            def complete_fn(step):
                return step.complete()

        # use the custom complete function when set
        if self.custom_complete:
            return self.custom_complete(complete_fn)

        # default implementation
        return all(complete_fn(t) for t in self.flat_requirements)


class ExternalStep(Step):
    """
    Subclass for references to external dependencies.

    An ExternalStep's does not have a `run` implementation, which signifies to
    the framework that this Step's :py:meth:`output` is generated outside of
    Luigi.
    """
    run = None


def externalize(stepclass_or_stepobject):
    """
    Returns an externalized version of a Step. You may both pass an
    instantiated step object or a step class. Some examples:

    .. code-block:: python

        class RequiringStep(luigi.Step):
            def requires(self):
                step_object = self.clone(MyStep)
                return externalize(step_object)

            ...

    Here's mostly equivalent code, but ``externalize`` is applied to a step
    class instead.

    .. code-block:: python

        @luigi.util.requires(externalize(MyStep))
        class RequiringStep(luigi.Step):
            pass
            ...

    Of course, it may also be used directly on classes and objects (for example
    for reexporting or other usage).

    .. code-block:: python

        MyStep = externalize(MyStep)
        my_step_2 = externalize(MyStep2(param='foo'))

    If you however want a step class to be external from the beginning, you're
    better off inheriting :py:class:`ExternalStep` rather than :py:class:`Step`.

    This function tries to be side-effect free by creating a copy of the class
    or the object passed in and then modify that object. In particular this
    code shouldn't do anything.

    .. code-block:: python

        externalize(MyStep)  # BAD: This does nothing (as after luigi 2.4.0)
    """
    copied_value = copy.copy(stepclass_or_stepobject)
    if copied_value is stepclass_or_stepobject:
        # Assume it's a class
        clazz = stepclass_or_stepobject

        @_step_wraps(clazz)
        class _CopyOfClass(clazz):
            # How to copy a class: http://stackoverflow.com/a/9541120/621449
            _visible_in_registry = False
        _CopyOfClass.run = None
        return _CopyOfClass
    else:
        # We assume it's an object
        copied_value.run = None
        return copied_value


class WrapperStep(Step):
    """
    Use for steps that only wrap other steps and that by definition are done if all their requirements exist.
    """

    def complete(self):
        return all(r.complete() for r in flatten(self.requires()))


class Config(Step):
    """
    Class for configuration. See :ref:`ConfigClasses`.
    """
    # TODO: let's refactor Step & Config so that it inherits from a common
    # ParamContainer base class
    pass


def getpaths(struct):
    """
    Maps all Steps in a structured data object to their .output().
    """
    if isinstance(struct, Step):
        return struct.output()
    elif isinstance(struct, dict):
        return struct.__class__((k, getpaths(v)) for k, v in struct.items())
    elif isinstance(struct, (list, tuple)):
        return struct.__class__(getpaths(r) for r in struct)
    else:
        # Remaining case: assume struct is iterable...
        try:
            return [getpaths(r) for r in struct]
        except TypeError:
            raise Exception('Cannot map %s to Step/dict/list' % str(struct))


def flatten(struct):
    """
    Creates a flat list of all items in structured output (dicts, lists, items):

    .. code-block:: python

        >>> sorted(flatten({'a': 'foo', 'b': 'bar'}))
        ['bar', 'foo']
        >>> sorted(flatten(['foo', ['bar', 'troll']]))
        ['bar', 'foo', 'troll']
        >>> flatten('foo')
        ['foo']
        >>> flatten(42)
        [42]
    """
    if struct is None:
        return []
    flat = []
    if isinstance(struct, dict):
        for _, result in struct.items():
            flat += flatten(result)
        return flat
    if isinstance(struct, str):
        return [struct]

    try:
        # if iterable
        iterator = iter(struct)
    except TypeError:
        return [struct]

    for result in iterator:
        flat += flatten(result)
    return flat


def flatten_output(step):
    """
    Lists all output targets by recursively walking output-less (wrapper) steps.
    """

    output_steps = OrderedDict()  # OrderedDict used as ordered set
    steps_to_process = deque([step])
    while steps_to_process:
        current_step = steps_to_process.popleft()
        if flatten(current_step.output()):
            if current_step not in output_steps:
                output_steps[current_step] = None
        else:
            steps_to_process.extend(flatten(current_step.requires()))

    return flatten(step.output() for step in output_steps)


def _step_wraps(step_class):
    # In order to make the behavior of a wrapper class nicer, we set the name of the
    # new class to the wrapped class, and copy over the docstring and module as well.
    # This makes it possible to pickle the wrapped class etc.
    # Btw, this is a slight abuse of functools.wraps. It's meant to be used only for
    # functions, but it works for classes too, if you pass updated=[]
    assigned = functools.WRAPPER_ASSIGNMENTS + ('_namespace_at_class_time',)
    return functools.wraps(step_class, assigned=assigned, updated=[])
