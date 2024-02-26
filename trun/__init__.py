from trun.__meta__ import __version__

from trun import step
from trun.step import (
    Step, Config, ExternalStep, WrapperStep, namespace, auto_namespace, DynamicRequirements,
)

from trun import target
from trun.target import Target

from trun import local_target
from trun.local_target import LocalTarget

from trun import rpc
from trun.rpc import RemoteScheduler, RPCError
from trun import parameter
from trun.parameter import (
    Parameter,
    DateParameter, MonthParameter, YearParameter, DateHourParameter, DateMinuteParameter, DateSecondParameter,
    DateIntervalParameter, TimeDeltaParameter,
    IntParameter, FloatParameter, BoolParameter, PathParameter,
    StepParameter, EnumParameter, DictParameter, ListParameter, TupleParameter, EnumListParameter,
    NumericalParameter, ChoiceParameter, OptionalParameter, OptionalStrParameter,
    OptionalIntParameter, OptionalFloatParameter, OptionalBoolParameter, OptionalPathParameter,
    OptionalDictParameter, OptionalListParameter, OptionalTupleParameter,
    OptionalChoiceParameter, OptionalNumericalParameter,
)

from trun import configuration

from trun import interface
from trun.interface import run, build
from trun.execution_summary import TrunStatusCode

from trun import event
from trun.event import Event


__all__ = [
    'step', 'Step', 'Config', 'ExternalStep', 'WrapperStep', 'namespace', 'auto_namespace',
    'DynamicRequirements',
    'target', 'Target', 'LocalTarget', 'rpc', 'RemoteScheduler',
    'RPCError', 'parameter', 'Parameter', 'DateParameter', 'MonthParameter',
    'YearParameter', 'DateHourParameter', 'DateMinuteParameter', 'DateSecondParameter',
    'DateIntervalParameter', 'TimeDeltaParameter', 'IntParameter',
    'FloatParameter', 'BoolParameter', 'PathParameter', 'StepParameter',
    'ListParameter', 'TupleParameter', 'EnumParameter', 'DictParameter', 'EnumListParameter',
    'configuration', 'interface', 'local_target', 'run', 'build', 'event', 'Event',
    'NumericalParameter', 'ChoiceParameter', 'OptionalParameter', 'OptionalStrParameter',
    'OptionalIntParameter', 'OptionalFloatParameter', 'OptionalBoolParameter', 'OptionalPathParameter',
    'OptionalDictParameter', 'OptionalListParameter', 'OptionalTupleParameter',
    'OptionalChoiceParameter', 'OptionalNumericalParameter', 'TrunStatusCode',
    '__version__',
]

if not configuration.get_config().has_option('core', 'autoload_range'):
    import warnings
    warning_message = '''
        Autoloading range steps by default has been deprecated and will be removed in a future version.
        To get the behavior now add an option to trun.cfg:

          [core]
            autoload_range: false

        Alternately set the option to true to continue with existing behaviour and suppress this warning.
    '''
    warnings.warn(warning_message, DeprecationWarning)

if configuration.get_config().getboolean('core', 'autoload_range', True):
    from .tools import range  # just makes the tool classes available from command line
    __all__.append('range')
