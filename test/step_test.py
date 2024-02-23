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

from helpers import unittest, LuigiTestCase, with_config
from datetime import datetime, timedelta

import luigi
import luigi.step
import luigi.util
import collections
from luigi.step_register import load_step


class DummyStep(luigi.Step):

    param = luigi.Parameter()
    bool_param = luigi.BoolParameter()
    int_param = luigi.IntParameter()
    float_param = luigi.FloatParameter()
    date_param = luigi.DateParameter()
    datehour_param = luigi.DateHourParameter()
    timedelta_param = luigi.TimeDeltaParameter()
    insignificant_param = luigi.Parameter(significant=False)


DUMMY_STEP_OK_PARAMS = dict(
    param='test',
    bool_param=True,
    int_param=666,
    float_param=123.456,
    date_param=datetime(2014, 9, 13).date(),
    datehour_param=datetime(2014, 9, 13, 9),
    timedelta_param=timedelta(44),  # doesn't support seconds
    insignificant_param='test')


class DefaultInsignificantParamStep(luigi.Step):
    insignificant_param = luigi.Parameter(significant=False, default='value')
    necessary_param = luigi.Parameter(significant=False)


class StepTest(unittest.TestCase):

    def test_steps_doctest(self):
        doctest.testmod(luigi.step)

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
        with self.assertRaises(luigi.parameter.MissingParameterException):
            DefaultInsignificantParamStep.from_str_params({})

    def test_external_steps_loadable(self):
        step = load_step("luigi", "ExternalStep", {})
        self.assertTrue(isinstance(step, luigi.ExternalStep))

    def test_getpaths(self):
        class RequiredStep(luigi.Step):
            def output(self):
                return luigi.LocalTarget("/path/to/target/file")

        t = RequiredStep()
        reqs = {}
        reqs["bare"] = t
        reqs["dict"] = {"key": t}
        reqs["OrderedDict"] = collections.OrderedDict([("key", t)])
        reqs["list"] = [t]
        reqs["tuple"] = (t,)
        reqs["generator"] = (t for _ in range(10))

        struct = luigi.step.getpaths(reqs)
        self.assertIsInstance(struct, dict)
        self.assertIsInstance(struct["bare"], luigi.Target)
        self.assertIsInstance(struct["dict"], dict)
        self.assertIsInstance(struct["OrderedDict"], collections.OrderedDict)
        self.assertIsInstance(struct["list"], list)
        self.assertIsInstance(struct["tuple"], tuple)
        self.assertTrue(hasattr(struct["generator"], "__iter__"))

    def test_flatten(self):
        flatten = luigi.step.flatten
        self.assertEqual(sorted(flatten({'a': 'foo', 'b': 'bar'})), ['bar', 'foo'])
        self.assertEqual(sorted(flatten(['foo', ['bar', 'troll']])), ['bar', 'foo', 'troll'])
        self.assertEqual(flatten('foo'), ['foo'])
        self.assertEqual(flatten(42), [42])
        self.assertEqual(flatten((len(i) for i in ["foo", "troll"])), [3, 5])
        self.assertRaises(TypeError, flatten, (len(i) for i in ["foo", "troll", None]))

    def test_externalized_step_picklable(self):
        step = luigi.step.externalize(luigi.Step())
        pickled_step = pickle.dumps(step)
        self.assertEqual(step, pickle.loads(pickled_step))

    def test_no_unpicklable_properties(self):
        step = luigi.Step()
        step.set_tracking_url = lambda tracking_url: tracking_url
        step.set_status_message = lambda message: message
        with step.no_unpicklable_properties():
            pickle.dumps(step)
        self.assertIsNotNone(step.set_tracking_url)
        self.assertIsNotNone(step.set_status_message)
        tracking_url = step.set_tracking_url('http://test.luigi.com/')
        self.assertEqual(tracking_url, 'http://test.luigi.com/')
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
        class AStep(luigi.Step):
            disable_window = 17
        step = AStep()
        self.assertEqual(step.disable_window_seconds, 17)

    @with_config({"AStepWithBadParam": {"bad_param": "bad_value"}})
    def test_bad_param(self):
        class AStepWithBadParam(luigi.Step):
            bad_param = luigi.IntParameter()

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
        class StepA(luigi.Step):
            a = luigi.Parameter(default="a")

        class StepB(luigi.Step):
            a = luigi.Parameter(default="a")

        with warnings.catch_warnings(record=True) as w:
            warnings.filterwarnings(
                action="ignore",
                category=Warning,
            )
            warnings.simplefilter(
                action="always",
                category=luigi.parameter.UnconsumedParameterWarning,
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
                assert issubclass(i.category, luigi.parameter.UnconsumedParameterWarning)
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
        class StepEdgeCase(luigi.Step):
            camelParam = luigi.Parameter()
            underscore_param = luigi.Parameter()
            dash_param = luigi.Parameter()

        with warnings.catch_warnings(record=True) as w:
            warnings.filterwarnings(
                action="ignore",
                category=Warning,
            )
            warnings.simplefilter(
                action="always",
                category=luigi.parameter.UnconsumedParameterWarning,
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
        class StepIgnoreUnconsumed(luigi.Step):
            ignore_unconsumed = {"b", "d"}

            a = luigi.Parameter()

        with warnings.catch_warnings(record=True) as w:
            warnings.filterwarnings(
                action="ignore",
                category=Warning,
            )
            warnings.simplefilter(
                action="always",
                category=luigi.parameter.UnconsumedParameterWarning,
            )

            StepIgnoreUnconsumed()
            assert len(w) == 1


class StepFlattenOutputTest(unittest.TestCase):
    def test_single_step(self):
        expected = [luigi.LocalTarget("f1.txt"), luigi.LocalTarget("f2.txt")]

        class TestStep(luigi.ExternalStep):
            def output(self):
                return expected

        self.assertListEqual(luigi.step.flatten_output(TestStep()), expected)

    def test_wrapper_step(self):
        expected = [luigi.LocalTarget("f1.txt"), luigi.LocalTarget("f2.txt")]

        class Test1Step(luigi.ExternalStep):
            def output(self):
                return expected[0]

        class Test2Step(luigi.ExternalStep):
            def output(self):
                return expected[1]

        @luigi.util.requires(Test1Step, Test2Step)
        class TestWrapperStep(luigi.WrapperStep):
            pass

        self.assertListEqual(luigi.step.flatten_output(TestWrapperStep()), expected)

    def test_wrapper_steps_diamond(self):
        expected = [luigi.LocalTarget("file.txt")]

        class TestStep(luigi.ExternalStep):
            def output(self):
                return expected

        @luigi.util.requires(TestStep)
        class LeftWrapperStep(luigi.WrapperStep):
            pass

        @luigi.util.requires(TestStep)
        class RightWrapperStep(luigi.WrapperStep):
            pass

        @luigi.util.requires(LeftWrapperStep, RightWrapperStep)
        class MasterWrapperStep(luigi.WrapperStep):
            pass

        self.assertListEqual(luigi.step.flatten_output(MasterWrapperStep()), expected)


class ExternalizeStepTest(LuigiTestCase):

    def test_externalize_stepclass(self):
        class MyStep(luigi.Step):
            def run(self):
                pass

        self.assertIsNotNone(MyStep.run)  # Assert what we believe
        step_object = luigi.step.externalize(MyStep)()
        self.assertIsNone(step_object.run)
        self.assertIsNotNone(MyStep.run)  # Check immutability
        self.assertIsNotNone(MyStep().run)  # Check immutability

    def test_externalize_stepobject(self):
        class MyStep(luigi.Step):
            def run(self):
                pass

        step_object = luigi.step.externalize(MyStep())
        self.assertIsNone(step_object.run)
        self.assertIsNotNone(MyStep.run)  # Check immutability
        self.assertIsNotNone(MyStep().run)  # Check immutability

    def test_externalize_stepclass_readable_name(self):
        class MyStep(luigi.Step):
            def run(self):
                pass

        step_class = luigi.step.externalize(MyStep)
        self.assertIsNot(step_class, MyStep)
        self.assertIn("MyStep", step_class.__name__)

    def test_externalize_stepclass_instance_cache(self):
        class MyStep(luigi.Step):
            def run(self):
                pass

        step_class = luigi.step.externalize(MyStep)
        self.assertIsNot(step_class, MyStep)
        self.assertIs(MyStep(), MyStep())  # Assert it have enabled the instance caching
        self.assertIsNot(step_class(), MyStep())  # Now, they should not be the same of course

    def test_externalize_same_id(self):
        class MyStep(luigi.Step):
            def run(self):
                pass

        step_normal = MyStep()
        step_ext_1 = luigi.step.externalize(MyStep)()
        step_ext_2 = luigi.step.externalize(MyStep())
        self.assertEqual(step_normal.step_id, step_ext_1.step_id)
        self.assertEqual(step_normal.step_id, step_ext_2.step_id)

    def test_externalize_same_id_with_step_namespace(self):
        # Dependent on the new behavior from spotify/luigi#1953
        class MyStep(luigi.Step):
            step_namespace = "something.domething"

            def run(self):
                pass

        step_normal = MyStep()
        step_ext_1 = luigi.step.externalize(MyStep())
        step_ext_2 = luigi.step.externalize(MyStep)()
        self.assertEqual(step_normal.step_id, step_ext_1.step_id)
        self.assertEqual(step_normal.step_id, step_ext_2.step_id)
        self.assertEqual(str(step_normal), str(step_ext_1))
        self.assertEqual(str(step_normal), str(step_ext_2))

    def test_externalize_same_id_with_luigi_namespace(self):
        # Dependent on the new behavior from spotify/luigi#1953
        luigi.namespace('lets.externalize')

        class MyStep(luigi.Step):
            def run(self):
                pass
        luigi.namespace()

        step_normal = MyStep()
        step_ext_1 = luigi.step.externalize(MyStep())
        step_ext_2 = luigi.step.externalize(MyStep)()
        self.assertEqual(step_normal.step_id, step_ext_1.step_id)
        self.assertEqual(step_normal.step_id, step_ext_2.step_id)
        self.assertEqual(str(step_normal), str(step_ext_1))
        self.assertEqual(str(step_normal), str(step_ext_2))

    def test_externalize_with_requires(self):
        class MyStep(luigi.Step):
            def run(self):
                pass

        @luigi.util.requires(luigi.step.externalize(MyStep))
        class Requirer(luigi.Step):
            def run(self):
                pass

        self.assertIsNotNone(MyStep.run)  # Check immutability
        self.assertIsNotNone(MyStep().run)  # Check immutability

    def test_externalize_doesnt_affect_the_registry(self):
        class MyStep(luigi.Step):
            pass
        reg_orig = luigi.step_register.Register._get_reg()
        luigi.step.externalize(MyStep)
        reg_afterwards = luigi.step_register.Register._get_reg()
        self.assertEqual(reg_orig, reg_afterwards)

    def test_can_uniquely_command_line_parse(self):
        class MyStep(luigi.Step):
            pass
        # This first check is just an assumption rather than assertion
        self.assertTrue(self.run_locally(['MyStep']))
        luigi.step.externalize(MyStep)
        # Now we check we don't encounter "ambiguous step" issues
        self.assertTrue(self.run_locally(['MyStep']))
        # We do this once again, is there previously was a bug like this.
        luigi.step.externalize(MyStep)
        self.assertTrue(self.run_locally(['MyStep']))


class StepNamespaceTest(LuigiTestCase):

    def setup_steps(self):
        class Foo(luigi.Step):
            pass

        class FooSubclass(Foo):
            pass
        return (Foo, FooSubclass, self.go_mynamespace())

    def go_mynamespace(self):
        luigi.namespace("mynamespace")

        class Foo(luigi.Step):
            p = luigi.IntParameter()

        class Bar(Foo):
            step_namespace = "othernamespace"  # namespace override

        class Baz(Bar):  # inherits namespace for Bar
            pass
        luigi.namespace()
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
        luigi.namespace('a')

        class _BaseStep(luigi.Step):
            pass
        luigi.namespace('b')

        class _ChildStep(_BaseStep):
            pass
        luigi.namespace()  # Reset everything
        child_step = _ChildStep()
        self.assertEqual(child_step.step_family, 'b._ChildStep')
        self.assertEqual(str(child_step), 'b._ChildStep()')

    def test_with_scope(self):
        luigi.namespace('wohoo', scope='step_test')
        luigi.namespace('bleh', scope='')

        class MyStep(luigi.Step):
            pass
        luigi.namespace(scope='step_test')
        luigi.namespace(scope='')
        self.assertEqual(MyStep.get_step_namespace(), 'wohoo')

    def test_with_scope_not_matching(self):
        luigi.namespace('wohoo', scope='incorrect_namespace')
        luigi.namespace('bleh', scope='')

        class MyStep(luigi.Step):
            pass
        luigi.namespace(scope='incorrect_namespace')
        luigi.namespace(scope='')
        self.assertEqual(MyStep.get_step_namespace(), 'bleh')


class AutoNamespaceTest(LuigiTestCase):
    this_module = 'step_test'

    def test_auto_namespace_global(self):
        luigi.auto_namespace()

        class MyStep(luigi.Step):
            pass

        luigi.namespace()
        self.assertEqual(MyStep.get_step_namespace(), self.this_module)

    def test_auto_namespace_scope(self):
        luigi.auto_namespace(scope='step_test')
        luigi.namespace('bleh', scope='')

        class MyStep(luigi.Step):
            pass
        luigi.namespace(scope='step_test')
        luigi.namespace(scope='')
        self.assertEqual(MyStep.get_step_namespace(), self.this_module)

    def test_auto_namespace_not_matching(self):
        luigi.auto_namespace(scope='incorrect_namespace')
        luigi.namespace('bleh', scope='')

        class MyStep(luigi.Step):
            pass
        luigi.namespace(scope='incorrect_namespace')
        luigi.namespace(scope='')
        self.assertEqual(MyStep.get_step_namespace(), 'bleh')

    def test_auto_namespace_not_matching_2(self):
        luigi.auto_namespace(scope='incorrect_namespace')

        class MyStep(luigi.Step):
            pass
        luigi.namespace(scope='incorrect_namespace')
        self.assertEqual(MyStep.get_step_namespace(), '')


class InitSubclassTest(LuigiTestCase):
    def test_step_works_with_init_subclass(self):
        class ReceivesClassKwargs(luigi.Step):
            def __init_subclass__(cls, x, **kwargs):
                super(ReceivesClassKwargs, cls).__init_subclass__()
                cls.x = x

        class Receiver(ReceivesClassKwargs, x=1):
            pass
        self.assertEquals(Receiver.x, 1)
