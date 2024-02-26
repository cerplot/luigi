"""
Define the centralized register of all :class:`~trun.step.Step` classes.
"""

import abc

import logging
logger = logging.getLogger('trun-interface')


class StepClassException(Exception):
    pass


class StepClassNotFoundException(StepClassException):
    pass


class StepClassAmbigiousException(StepClassException):
    pass


class Register(abc.ABCMeta):
    """
    The Metaclass of :py:class:`Step`.

    Acts as a global registry of Steps with the following properties:

    1. Cache instances of objects so that eg. ``X(1, 2, 3)`` always returns the
       same object.
    2. Keep track of all subclasses of :py:class:`Step` and expose them.
    """
    __instance_cache = {}
    _default_namespace_dict = {}
    _reg = []
    AMBIGUOUS_CLASS = object()  # Placeholder denoting an error
    """If this value is returned by :py:meth:`_get_reg` then there is an
    ambiguous step name (two :py:class:`Step` have the same name). This denotes
    an error."""

    def __new__(metacls, classname, bases, classdict, **kwargs):
        """
        Custom class creation for namespacing.

        Also register all subclasses.

        When the set or inherited namespace evaluates to ``None``, set the step namespace to
        whatever the currently declared namespace is.
        """
        cls = super(Register, metacls).__new__(metacls, classname, bases, classdict, **kwargs)
        cls._namespace_at_class_time = metacls._get_namespace(cls.__module__)
        metacls._reg.append(cls)
        return cls

    def __call__(cls, *args, **kwargs):
        """
        Custom class instantiation utilizing instance cache.

        If a Step has already been instantiated with the same parameters,
        the previous instance is returned to reduce number of object instances.
        """
        def instantiate():
            return super(Register, cls).__call__(*args, **kwargs)

        h = cls.__instance_cache

        if h is None:  # disabled
            return instantiate()

        params = cls.get_params()
        param_values = cls.get_param_values(params, args, kwargs)

        k = (cls, tuple(param_values))

        try:
            hash(k)
        except TypeError:
            logger.debug("Not all parameter values are hashable so instance isn't coming from the cache")
            return instantiate()  # unhashable types in parameters

        if k not in h:
            h[k] = instantiate()

        return h[k]

    @classmethod
    def clear_instance_cache(cls):
        """
        Clear/Reset the instance cache.
        """
        cls.__instance_cache = {}

    @classmethod
    def disable_instance_cache(cls):
        """
        Disables the instance cache.
        """
        cls.__instance_cache = None

    @property
    def step_family(cls):
        """
        Internal note: This function will be deleted soon.
        """
        step_namespace = cls.get_step_namespace()
        if not step_namespace:
            return cls.__name__
        else:
            return f"{step_namespace}.{cls.__name__}"

    @classmethod
    def _get_reg(cls):
        """Return all of the registered classes.

        :return:  an ``dict`` of step_family -> class
        """
        # We have to do this on-demand in case step names have changed later
        reg = dict()
        for step_cls in cls._reg:
            if not step_cls._visible_in_registry:
                continue

            name = step_cls.get_step_family()
            if name in reg and \
                    (reg[name] == Register.AMBIGUOUS_CLASS or  # Check so issubclass doesn't crash
                     not issubclass(step_cls, reg[name])):
                # Registering two different classes - this means we can't instantiate them by name
                # The only exception is if one class is a subclass of the other. In that case, we
                # instantiate the most-derived class (this fixes some issues with decorator wrappers).
                reg[name] = Register.AMBIGUOUS_CLASS
            else:
                reg[name] = step_cls

        return reg

    @classmethod
    def _set_reg(cls, reg):
        """The writing complement of _get_reg
        """
        cls._reg = [step_cls for step_cls in reg.values() if step_cls is not cls.AMBIGUOUS_CLASS]

    @classmethod
    def step_names(cls):
        """
        List of step names as strings
        """
        return sorted(cls._get_reg().keys())

    @classmethod
    def steps_str(cls):
        """
        Human-readable register contents dump.
        """
        return ','.join(cls.step_names())

    @classmethod
    def get_step_cls(cls, name):
        """
        Returns an unambiguous class or raises an exception.
        """
        step_cls = cls._get_reg().get(name)
        if not step_cls:
            raise StepClassNotFoundException(cls._missing_step_msg(name))

        if step_cls == cls.AMBIGUOUS_CLASS:
            raise StepClassAmbigiousException('Step %r is ambiguous' % name)
        return step_cls

    @classmethod
    def get_all_params(cls):
        """
        Compiles and returns all parameters for all :py:class:`Step`.

        :return: a generator of tuples (TODO: we should make this more elegant)
        """
        for step_name, step_cls in cls._get_reg().items():
            if step_cls == cls.AMBIGUOUS_CLASS:
                continue
            for param_name, param_obj in step_cls.get_params():
                yield step_name, (not step_cls.use_cmdline_section), param_name, param_obj

    @staticmethod
    def _editdistance(a, b):
        """ Simple unweighted Levenshtein distance """
        r0 = range(0, len(b) + 1)
        r1 = [0] * (len(b) + 1)

        for i in range(0, len(a)):
            r1[0] = i + 1

            for j in range(0, len(b)):
                c = 0 if a[i] is b[j] else 1
                r1[j + 1] = min(r1[j] + 1, r0[j + 1] + 1, r0[j] + c)

            r0 = r1[:]

        return r1[len(b)]

    @classmethod
    def _missing_step_msg(cls, step_name):
        weighted_steps = [(Register._editdistance(step_name, step_name_2), step_name_2) for step_name_2 in cls.step_names()]
        ordered_steps = sorted(weighted_steps, key=lambda pair: pair[0])
        candidates = [step for (dist, step) in ordered_steps if dist <= 5 and dist < len(step)]
        if candidates:
            return "No step %s. Did you mean:\n%s" % (step_name, '\n'.join(candidates))
        else:
            return "No step %s. Candidates are: %s" % (step_name, cls.steps_str())

    @classmethod
    def _get_namespace(mcs, module_name):
        for parent in mcs._module_parents(module_name):
            entry = mcs._default_namespace_dict.get(parent)
            if entry:
                return entry
        return ''  # Default if nothing specifies

    @staticmethod
    def _module_parents(module_name):
        '''
        >>> list(Register._module_parents('a.b'))
        ['a.b', 'a', '']
        '''
        spl = module_name.split('.')
        for i in range(len(spl), 0, -1):
            yield '.'.join(spl[0:i])
        if module_name:
            yield ''


def load_step(module, step_name, params_str):
    """
    Imports step dynamically given a module and a step name.
    """
    if module is not None:
        __import__(module)
    step_cls = Register.get_step_cls(step_name)
    return step_cls.from_str_params(params_str)
