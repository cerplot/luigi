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
import doctest
import pickle
import warnings

from helpers import unittest, TrunTestCase, with_config
from datetime import datetime, timedelta

import trun
import trun.step
import trun.util
import collections
from trun.step_register import load_step


class DummyStep(trun.Step):

    param = trun.Parameter()
    bool_param = trun.BoolParameter()
    int_param = trun.IntParameter()
    float_param = trun.FloatParameter()
    date_param = trun.DateParameter()
    datehour_param = trun.DateHourParameter()
    timedelta_param = trun.TimeDeltaParameter()
    insignificant_param = trun.Parameter(significant=False)


DUMMY_STEP_OK_PARAMS = dict(
    param='test',
    bool_param=True,
    int_param=666,
    float_param=123.456,
    date_param=datetime(2014, 9, 13).date(),
    datehour_param=datetime(2014, 9, 13, 9),
    timedelta_param=timedelta(44),  # doesn't support seconds
    insignificant_param='test')


class DefaultInsignificantParamStep(trun.Step):
    insignificant_param = trun.Parameter(significant=False, default='value')
    necessary_param = trun.Parameter(significant=False)


class StepTest(unittest.TestCase):

    def test_steps_doctest(self):
        doctest.testmod(trun.step)

    def test_step_to_str_to_step(self):
        original = DummyStep(**DUMMY_STEP_OK_PARAMS)
        other = DummyStep.from_str_params(original.to_str_params())
        self.assertEqual(original, other)

    def test_step_from_str_insignificant(self):
        params = {'necessary_param': 'needed'}
        original = DefaultInsignificantParamStep(**params)
        other = DefaultInsignificantParamStep.from_str_params(params)
        self.assertEqual(original, other)

    def test_step_missing_necessary_param(self):
        with self.assertRaises(trun.parameter.MissingParameterException):
            DefaultInsignificantParamStep.from_str_params({})

    def test_external_steps_loadable(self):
        step = load_step("trun", "ExternalStep", {})
        self.assertTrue(isinstance(step, trun.ExternalStep))

    def test_getpaths(self):
        class RequiredStep(trun.Step):
            def output(self):
                return trun.LocalTarget("/path/to/target/file")

        t = RequiredStep()
        reqs = {}
        reqs["bare"] = t
        reqs["dict"] = {"key": t}
        reqs["OrderedDict"] = collections.OrderedDict([("key", t)])
        reqs["list"] = [t]
        reqs["tuple"] = (t,)
        reqs["generator"] = (t for _ in range(10))

        struct = trun.step.getpaths(reqs)
        self.assertIsInstance(struct, dict)
        self.assertIsInstance(struct["bare"], trun.Target)
        self.assertIsInstance(struct["dict"], dict)
        self.assertIsInstance(struct["OrderedDict"], collections.OrderedDict)
        self.assertIsInstance(struct["list"], list)
        self.assertIsInstance(struct["tuple"], tuple)
        self.assertTrue(hasattr(struct["generator"], "__iter__"))

    def test_flatten(self):
        flatten = trun.step.flatten
        self.assertEqual(sorted(flatten({'a': 'foo', 'b': 'bar'})), ['bar', 'foo'])
        self.assertEqual(sorted(flatten(['foo', ['bar', 'troll']])), ['bar', 'foo', 'troll'])
        self.assertEqual(flatten('foo'), ['foo'])
        self.assertEqual(flatten(42), [42])
        self.assertEqual(flatten((len(i) for i in ["foo", "troll"])), [3, 5])
        self.assertRaises(TypeError, flatten, (len(i) for i in ["foo", "troll", None]))

    def test_externalized_step_picklable(self):
        step = trun.step.externalize(trun.Step())
        pickled_step = pickle.dumps(step)
        self.assertEqual(step, pickle.loads(pickled_step))

    def test_no_unpicklable_properties(self):
        step = trun.Step()
        step.set_tracking_url = lambda tracking_url: tracking_url
        step.set_status_message = lambda message: message
        with step.no_unpicklable_properties():
            pickle.dumps(step)
        self.assertIsNotNone(step.set_tracking_url)
        self.assertIsNotNone(step.set_status_message)
        tracking_url = step.set_tracking_url('http://test.trun.com/')
        self.assertEqual(tracking_url, 'http://test.trun.com/')
        message = step.set_status_message('message')
        self.assertEqual(message, 'message')

    def test_no_warn_if_param_types_ok(self):
        with warnings.catch_warnings(record=True) as w:
            DummyStep(**DUMMY_STEP_OK_PARAMS)
        self.assertEqual(len(w), 0, msg='No warning should be raised when correct parameter types are used')

    def test_warn_on_non_str_param(self):
        params = dict(**DUMMY_STEP_OK_PARAMS)
        params['param'] = 42
        with self.assertWarnsRegex(UserWarning, 'Parameter "param" with value "42" is not of type string.'):
            DummyStep(**params)

    def test_warn_on_non_timedelta_param(self):
        params = dict(**DUMMY_STEP_OK_PARAMS)

        class MockTimedelta:
            days = 1
            seconds = 1

        params['timedelta_param'] = MockTimedelta()
        with self.assertWarnsRegex(UserWarning, 'Parameter "timedelta_param" with value ".*" is not of type timedelta.'):
            DummyStep(**params)

    def test_disable_window_seconds(self):
        """
        Deprecated disable_window_seconds param uses disable_window value
        """
        class AStep(trun.Step):
            disable_window = 17
        step = AStep()
        self.assertEqual(step.disable_window_seconds, 17)

    @with_config({"AStepWithBadParam": {"bad_param": "bad_value"}})
    def test_bad_param(self):
        class AStepWithBadParam(trun.Step):
            bad_param = trun.IntParameter()

        with self.assertRaisesRegex(ValueError, r"AStepWithBadParam\[args=\(\), kwargs={}\]: Error when parsing the default value of 'bad_param'"):
            AStepWithBadParam()

    @with_config(
        {
            "StepA": {
                "a": "a",
                "b": "b",
                "c": "c",
            },
            "StepB": {
                "a": "a",
                "b": "b",
                "c": "c",
            },
        }
    )
    def test_unconsumed_params(self):
        class StepA(trun.Step):
            a = trun.Parameter(default="a")

        class StepB(trun.Step):
            a = trun.Parameter(default="a")

        with warnings.catch_warnings(record=True) as w:
            warnings.filterwarnings(
                action="ignore",
                category=Warning,
            )
            warnings.simplefilter(
                action="always",
                category=trun.parameter.UnconsumedParameterWarning,
            )

            StepA()
            StepB()

            assert len(w) == 4
            expected = [
                ("b", "StepA"),
                ("c", "StepA"),
                ("b", "StepB"),
                ("c", "StepB"),
            ]
            for i, (expected_value, step_name) in zip(w, expected):
                assert issubclass(i.category, trun.parameter.UnconsumedParameterWarning)
                assert str(i.message) == (
                    "The configuration contains the parameter "
                    f"'{expected_value}' with value '{expected_value}' that is not consumed by "
                    f"the step '{step_name}'."
                )

    @with_config(
        {
            "StepEdgeCase": {
                "camelParam": "camelCase",
                "underscore_param": "underscore",
                "dash-param": "dash",
            },
        }
    )
    def test_unconsumed_params_edge_cases(self):
        class StepEdgeCase(trun.Step):
            camelParam = trun.Parameter()
            underscore_param = trun.Parameter()
            dash_param = trun.Parameter()

        with warnings.catch_warnings(record=True) as w:
            warnings.filterwarnings(
                action="ignore",
                category=Warning,
            )
            warnings.simplefilter(
                action="always",
                category=trun.parameter.UnconsumedParameterWarning,
            )

            step = StepEdgeCase()
            assert len(w) == 0
            assert step.camelParam == "camelCase"
            assert step.underscore_param == "underscore"
            assert step.dash_param == "dash"

    @with_config(
        {
            "StepIgnoreUnconsumed": {
                "a": "a",
                "b": "b",
                "c": "c",
            },
        }
    )
    def test_unconsumed_params_ignore_unconsumed(self):
        class StepIgnoreUnconsumed(trun.Step):
            ignore_unconsumed = {"b", "d"}

            a = trun.Parameter()

        with warnings.catch_warnings(record=True) as w:
            warnings.filterwarnings(
                action="ignore",
                category=Warning,
            )
            warnings.simplefilter(
                action="always",
                category=trun.parameter.UnconsumedParameterWarning,
            )

            StepIgnoreUnconsumed()
            assert len(w) == 1


class StepFlattenOutputTest(unittest.TestCase):
    def test_single_step(self):
        expected = [trun.LocalTarget("f1.txt"), trun.LocalTarget("f2.txt")]

        class TestStep(trun.ExternalStep):
            def output(self):
                return expected

        self.assertListEqual(trun.step.flatten_output(TestStep()), expected)

    def test_wrapper_step(self):
        expected = [trun.LocalTarget("f1.txt"), trun.LocalTarget("f2.txt")]

        class Test1Step(trun.ExternalStep):
            def output(self):
                return expected[0]

        class Test2Step(trun.ExternalStep):
            def output(self):
                return expected[1]

        @trun.util.requires(Test1Step, Test2Step)
        class TestWrapperStep(trun.WrapperStep):
            pass

        self.assertListEqual(trun.step.flatten_output(TestWrapperStep()), expected)

    def test_wrapper_steps_diamond(self):
        expected = [trun.LocalTarget("file.txt")]

        class TestStep(trun.ExternalStep):
            def output(self):
                return expected

        @trun.util.requires(TestStep)
        class LeftWrapperStep(trun.WrapperStep):
            pass

        @trun.util.requires(TestStep)
        class RightWrapperStep(trun.WrapperStep):
            pass

        @trun.util.requires(LeftWrapperStep, RightWrapperStep)
        class MasterWrapperStep(trun.WrapperStep):
            pass

        self.assertListEqual(trun.step.flatten_output(MasterWrapperStep()), expected)


class ExternalizeStepTest(TrunTestCase):

    def test_externalize_stepclass(self):
        class MyStep(trun.Step):
            def run(self):
                pass

        self.assertIsNotNone(MyStep.run)  # Assert what we believe
        step_object = trun.step.externalize(MyStep)()
        self.assertIsNone(step_object.run)
        self.assertIsNotNone(MyStep.run)  # Check immutability
        self.assertIsNotNone(MyStep().run)  # Check immutability

    def test_externalize_stepobject(self):
        class MyStep(trun.Step):
            def run(self):
                pass

        step_object = trun.step.externalize(MyStep())
        self.assertIsNone(step_object.run)
        self.assertIsNotNone(MyStep.run)  # Check immutability
        self.assertIsNotNone(MyStep().run)  # Check immutability

    def test_externalize_stepclass_readable_name(self):
        class MyStep(trun.Step):
            def run(self):
                pass

        step_class = trun.step.externalize(MyStep)
        self.assertIsNot(step_class, MyStep)
        self.assertIn("MyStep", step_class.__name__)

    def test_externalize_stepclass_instance_cache(self):
        class MyStep(trun.Step):
            def run(self):
                pass

        step_class = trun.step.externalize(MyStep)
        self.assertIsNot(step_class, MyStep)
        self.assertIs(MyStep(), MyStep())  # Assert it have enabled the instance caching
        self.assertIsNot(step_class(), MyStep())  # Now, they should not be the same of course

    def test_externalize_same_id(self):
        class MyStep(trun.Step):
            def run(self):
                pass

        step_normal = MyStep()
        step_ext_1 = trun.step.externalize(MyStep)()
        step_ext_2 = trun.step.externalize(MyStep())
        self.assertEqual(step_normal.step_id, step_ext_1.step_id)
        self.assertEqual(step_normal.step_id, step_ext_2.step_id)

    def test_externalize_same_id_with_step_namespace(self):
        # Dependent on the new behavior from spotify/trun#1953
        class MyStep(trun.Step):
            step_namespace = "something.domething"

            def run(self):
                pass

        step_normal = MyStep()
        step_ext_1 = trun.step.externalize(MyStep())
        step_ext_2 = trun.step.externalize(MyStep)()
        self.assertEqual(step_normal.step_id, step_ext_1.step_id)
        self.assertEqual(step_normal.step_id, step_ext_2.step_id)
        self.assertEqual(str(step_normal), str(step_ext_1))
        self.assertEqual(str(step_normal), str(step_ext_2))

    def test_externalize_same_id_with_trun_namespace(self):
        # Dependent on the new behavior from spotify/trun#1953
        trun.namespace('lets.externalize')

        class MyStep(trun.Step):
            def run(self):
                pass
        trun.namespace()

        step_normal = MyStep()
        step_ext_1 = trun.step.externalize(MyStep())
        step_ext_2 = trun.step.externalize(MyStep)()
        self.assertEqual(step_normal.step_id, step_ext_1.step_id)
        self.assertEqual(step_normal.step_id, step_ext_2.step_id)
        self.assertEqual(str(step_normal), str(step_ext_1))
        self.assertEqual(str(step_normal), str(step_ext_2))

    def test_externalize_with_requires(self):
        class MyStep(trun.Step):
            def run(self):
                pass

        @trun.util.requires(trun.step.externalize(MyStep))
        class Requirer(trun.Step):
            def run(self):
                pass

        self.assertIsNotNone(MyStep.run)  # Check immutability
        self.assertIsNotNone(MyStep().run)  # Check immutability

    def test_externalize_doesnt_affect_the_registry(self):
        class MyStep(trun.Step):
            pass
        reg_orig = trun.step_register.Register._get_reg()
        trun.step.externalize(MyStep)
        reg_afterwards = trun.step_register.Register._get_reg()
        self.assertEqual(reg_orig, reg_afterwards)

    def test_can_uniquely_command_line_parse(self):
        class MyStep(trun.Step):
            pass
        # This first check is just an assumption rather than assertion
        self.assertTrue(self.run_locally(['MyStep']))
        trun.step.externalize(MyStep)
        # Now we check we don't encounter "ambiguous step" issues
        self.assertTrue(self.run_locally(['MyStep']))
        # We do this once again, is there previously was a bug like this.
        trun.step.externalize(MyStep)
        self.assertTrue(self.run_locally(['MyStep']))


class StepNamespaceTest(TrunTestCase):

    def setup_steps(self):
        class Foo(trun.Step):
            pass

        class FooSubclass(Foo):
            pass
        return (Foo, FooSubclass, self.go_mynamespace())

    def go_mynamespace(self):
        trun.namespace("mynamespace")

        class Foo(trun.Step):
            p = trun.IntParameter()

        class Bar(Foo):
            step_namespace = "othernamespace"  # namespace override

        class Baz(Bar):  # inherits namespace for Bar
            pass
        trun.namespace()
        return collections.namedtuple('mynamespace', 'Foo Bar Baz')(Foo, Bar, Baz)

    def test_vanilla(self):
        (Foo, FooSubclass, namespace_test_helper) = self.setup_steps()
        self.assertEqual(Foo.step_family, "Foo")
        self.assertEqual(str(Foo()), "Foo()")

        self.assertEqual(FooSubclass.step_family, "FooSubclass")
        self.assertEqual(str(FooSubclass()), "FooSubclass()")

    def test_namespace(self):
        (Foo, FooSubclass, namespace_test_helper) = self.setup_steps()
        self.assertEqual(namespace_test_helper.Foo.step_family, "mynamespace.Foo")
        self.assertEqual(str(namespace_test_helper.Foo(1)), "mynamespace.Foo(p=1)")

        self.assertEqual(namespace_test_helper.Bar.step_namespace, "othernamespace")
        self.assertEqual(namespace_test_helper.Bar.step_family, "othernamespace.Bar")
        self.assertEqual(str(namespace_test_helper.Bar(1)), "othernamespace.Bar(p=1)")

        self.assertEqual(namespace_test_helper.Baz.step_namespace, "othernamespace")
        self.assertEqual(namespace_test_helper.Baz.step_family, "othernamespace.Baz")
        self.assertEqual(str(namespace_test_helper.Baz(1)), "othernamespace.Baz(p=1)")

    def test_uses_latest_namespace(self):
        trun.namespace('a')

        class _BaseStep(trun.Step):
            pass
        trun.namespace('b')

        class _ChildStep(_BaseStep):
            pass
        trun.namespace()  # Reset everything
        child_step = _ChildStep()
        self.assertEqual(child_step.step_family, 'b._ChildStep')
        self.assertEqual(str(child_step), 'b._ChildStep()')

    def test_with_scope(self):
        trun.namespace('wohoo', scope='step_test')
        trun.namespace('bleh', scope='')

        class MyStep(trun.Step):
            pass
        trun.namespace(scope='step_test')
        trun.namespace(scope='')
        self.assertEqual(MyStep.get_step_namespace(), 'wohoo')

    def test_with_scope_not_matching(self):
        trun.namespace('wohoo', scope='incorrect_namespace')
        trun.namespace('bleh', scope='')

        class MyStep(trun.Step):
            pass
        trun.namespace(scope='incorrect_namespace')
        trun.namespace(scope='')
        self.assertEqual(MyStep.get_step_namespace(), 'bleh')


class AutoNamespaceTest(TrunTestCase):
    this_module = 'step_test'

    def test_auto_namespace_global(self):
        trun.auto_namespace()

        class MyStep(trun.Step):
            pass

        trun.namespace()
        self.assertEqual(MyStep.get_step_namespace(), self.this_module)

    def test_auto_namespace_scope(self):
        trun.auto_namespace(scope='step_test')
        trun.namespace('bleh', scope='')

        class MyStep(trun.Step):
            pass
        trun.namespace(scope='step_test')
        trun.namespace(scope='')
        self.assertEqual(MyStep.get_step_namespace(), self.this_module)

    def test_auto_namespace_not_matching(self):
        trun.auto_namespace(scope='incorrect_namespace')
        trun.namespace('bleh', scope='')

        class MyStep(trun.Step):
            pass
        trun.namespace(scope='incorrect_namespace')
        trun.namespace(scope='')
        self.assertEqual(MyStep.get_step_namespace(), 'bleh')

    def test_auto_namespace_not_matching_2(self):
        trun.auto_namespace(scope='incorrect_namespace')

        class MyStep(trun.Step):
            pass
        trun.namespace(scope='incorrect_namespace')
        self.assertEqual(MyStep.get_step_namespace(), '')


class InitSubclassTest(TrunTestCase):
    def test_step_works_with_init_subclass(self):
        class ReceivesClassKwargs(trun.Step):
            def __init_subclass__(cls, x, **kwargs):
                super(ReceivesClassKwargs, cls).__init_subclass__()
                cls.x = x

        class Receiver(ReceivesClassKwargs, x=1):
            pass
        self.assertEquals(Receiver.x, 1)
