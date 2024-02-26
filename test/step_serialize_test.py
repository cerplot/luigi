"""
We want to test that step_id is consistent when generated from:

 1. A real step instance
 2. The step_family and a dictionary of parameter values (as strings)
 3. A json representation of #2

We use the hypothesis package to do property-based tests.

"""

import string
import trun
import json
from datetime import datetime

import hypothesis as hyp
from hypothesis.strategies import datetimes as hyp_datetimes

_no_value = trun.parameter._no_value


def _mk_param_strategy(param_cls, param_value_strat, with_default=None):
    if with_default is None:
        default = hyp.strategies.one_of(hyp.strategies.just(_no_value), param_value_strat)
    elif with_default:
        default = param_value_strat
    else:
        default = hyp.strategies.just(_no_value)

    return hyp.strategies.builds(param_cls,
                                 description=hyp.strategies.text(alphabet=string.printable),
                                 default=default)


def _mk_step(name, params):
    return type(name, (trun.Step, ), params)


# identifiers must be str not unicode in Python2
identifiers = hyp.strategies.builds(str, hyp.strategies.text(alphabet=string.ascii_letters, min_size=1, max_size=16))
text = hyp.strategies.text(alphabet=string.printable)

# Trun parameters with a default
parameters_def = _mk_param_strategy(trun.Parameter, text, True)
int_parameters_def = _mk_param_strategy(trun.IntParameter, hyp.strategies.integers(), True)
float_parameters_def = _mk_param_strategy(trun.FloatParameter,
                                          hyp.strategies.floats(min_value=-1e100, max_value=+1e100), True)
bool_parameters_def = _mk_param_strategy(trun.BoolParameter, hyp.strategies.booleans(), True)
date_parameters_def = _mk_param_strategy(trun.DateParameter, hyp_datetimes(min_value=datetime(1900, 1, 1)), True)

any_default_parameters = hyp.strategies.one_of(
    parameters_def, int_parameters_def, float_parameters_def, bool_parameters_def, date_parameters_def
)

# Steps with up to 3 random parameters
steps_with_defaults = hyp.strategies.builds(
    _mk_step,
    name=identifiers,
    params=hyp.strategies.dictionaries(identifiers, any_default_parameters, max_size=3)
)


def _step_to_dict(step):
    # Generate the parameter value dictionary.  Use each parameter's serialize() method
    param_dict = {}
    for key, param in step.get_params():
        param_dict[key] = param.serialize(getattr(step, key))

    return param_dict


def _step_from_dict(step_cls, param_dict):
    # Regenerate the step from the dictionary
    step_params = {}
    for key, param in step_cls.get_params():
        step_params[key] = param.parse(param_dict[key])

    return step_cls(**step_params)


@hyp.given(steps_with_defaults)
def test_serializable(step_cls):
    step = step_cls()

    param_dict = _step_to_dict(step)
    step2 = _step_from_dict(step_cls, param_dict)

    assert step.step_id == step2.step_id


@hyp.given(steps_with_defaults)
def test_json_serializable(step_cls):
    step = step_cls()

    param_dict = _step_to_dict(step)

    param_dict = json.loads(json.dumps(param_dict))
    step2 = _step_from_dict(step_cls, param_dict)

    assert step.step_id == step2.step_id


@hyp.given(steps_with_defaults)
def test_step_id_alphanumeric(step_cls):
    step = step_cls()
    step_id = step.step_id
    valid = string.ascii_letters + string.digits + '_'

    assert [x for x in step_id if x not in valid] == []

# TODO : significant an non-significant parameters
