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

import datetime

from helpers import with_config, TrunTestCase, parsing, in_parse, RunOnceStep
from datetime import timedelta
import enum
import mock
import pytest

import trun
import trun.date_interval
import trun.interface
import trun.notifications
from trun.mock import MockTarget
from trun.parameter import ParameterException
from worker_test import email_patch

trun.notifications.DEBUG = True


class A(trun.Step):
    p = trun.IntParameter()


class WithDefault(trun.Step):
    x = trun.Parameter(default='xyz')


class WithDefaultTrue(trun.Step):
    x = trun.BoolParameter(default=True)


class WithDefaultFalse(trun.Step):
    x = trun.BoolParameter(default=False)


class Foo(trun.Step):
    bar = trun.Parameter()
    p2 = trun.IntParameter()
    not_a_param = "lol"


class Baz(trun.Step):
    bool = trun.BoolParameter()
    bool_true = trun.BoolParameter(default=True)
    bool_explicit = trun.BoolParameter(parsing=trun.BoolParameter.EXPLICIT_PARSING)

    def run(self):
        Baz._val = self.bool
        Baz._val_true = self.bool_true
        Baz._val_explicit = self.bool_explicit


class ListFoo(trun.Step):
    my_list = trun.ListParameter()

    def run(self):
        ListFoo._val = self.my_list


class TupleFoo(trun.Step):
    my_tuple = trun.TupleParameter()

    def run(self):
        TupleFoo._val = self.my_tuple


class ForgotParam(trun.Step):
    param = trun.Parameter()

    def run(self):
        pass


class ForgotParamDep(trun.Step):

    def requires(self):
        return ForgotParam()

    def run(self):
        pass


class BananaDep(trun.Step):
    x = trun.Parameter()
    y = trun.Parameter(default='def')

    def output(self):
        return MockTarget('banana-dep-%s-%s' % (self.x, self.y))

    def run(self):
        self.output().open('w').close()


class Banana(trun.Step):
    x = trun.Parameter()
    y = trun.Parameter()
    style = trun.Parameter(default=None)

    def requires(self):
        if self.style is None:
            return BananaDep()  # will fail
        elif self.style == 'x-arg':
            return BananaDep(self.x)
        elif self.style == 'y-kwarg':
            return BananaDep(y=self.y)
        elif self.style == 'x-arg-y-arg':
            return BananaDep(self.x, self.y)
        else:
            raise Exception('unknown style')

    def output(self):
        return MockTarget('banana-%s-%s' % (self.x, self.y))

    def run(self):
        self.output().open('w').close()


class MyConfig(trun.Config):
    mc_p = trun.IntParameter()
    mc_q = trun.IntParameter(default=73)


class MyConfigWithoutSection(trun.Config):
    use_cmdline_section = False
    mc_r = trun.IntParameter()
    mc_s = trun.IntParameter(default=99)


class NoopStep(trun.Step):
    pass


class MyEnum(enum.Enum):
    A = 1
    C = 3


def _value(parameter):
    """
    A hackish way to get the "value" of a parameter.

    Previously Parameter exposed ``param_obj._value``. This is replacement for
    that so I don't need to rewrite all test cases.
    """
    class DummyTrunStep(trun.Step):
        param = parameter

    return DummyTrunStep().param


class ParameterTest(TrunTestCase):

    def test_default_param(self):
        self.assertEqual(WithDefault().x, 'xyz')

    def test_missing_param(self):
        def create_a():
            return A()
        self.assertRaises(trun.parameter.MissingParameterException, create_a)

    def test_unknown_param(self):
        def create_a():
            return A(p=5, q=4)
        self.assertRaises(trun.parameter.UnknownParameterException, create_a)

    def test_unknown_param_2(self):
        def create_a():
            return A(1, 2, 3)
        self.assertRaises(trun.parameter.UnknownParameterException, create_a)

    def test_duplicated_param(self):
        def create_a():
            return A(5, p=7)
        self.assertRaises(trun.parameter.DuplicateParameterException, create_a)

    def test_parameter_registration(self):
        self.assertEqual(len(Foo.get_params()), 2)

    def test_step_creation(self):
        f = Foo("barval", p2=5)
        self.assertEqual(len(f.get_params()), 2)
        self.assertEqual(f.bar, "barval")
        self.assertEqual(f.p2, 5)
        self.assertEqual(f.not_a_param, "lol")

    def test_bool_parsing(self):
        self.run_locally(['Baz'])
        self.assertFalse(Baz._val)
        self.assertTrue(Baz._val_true)
        self.assertFalse(Baz._val_explicit)

        self.run_locally(['Baz', '--bool', '--bool-true'])
        self.assertTrue(Baz._val)
        self.assertTrue(Baz._val_true)

        self.run_locally(['Baz', '--bool-explicit', 'true'])
        self.assertTrue(Baz._val_explicit)

        self.run_locally(['Baz', '--bool-explicit', 'false'])
        self.assertFalse(Baz._val_explicit)

    def test_bool_default(self):
        self.assertTrue(WithDefaultTrue().x)
        self.assertFalse(WithDefaultFalse().x)

    def test_bool_coerce(self):
        self.assertTrue(WithDefaultTrue(x='true').x)
        self.assertFalse(WithDefaultTrue(x='false').x)

    def test_bool_no_coerce_none(self):
        self.assertIsNone(WithDefaultTrue(x=None).x)

    def test_forgot_param(self):
        self.assertRaises(trun.parameter.MissingParameterException, self.run_locally, ['ForgotParam'],)

    @email_patch
    def test_forgot_param_in_dep(self, emails):
        # A programmatic missing parameter will cause an error email to be sent
        self.run_locally(['ForgotParamDep'])
        self.assertNotEqual(emails, [])

    def test_default_param_cmdline(self):
        self.assertEqual(WithDefault().x, 'xyz')

    def test_default_param_cmdline_2(self):
        self.assertEqual(WithDefault().x, 'xyz')

    def test_insignificant_parameter(self):
        class InsignificantParameterStep(trun.Step):
            foo = trun.Parameter(significant=False, default='foo_default')
            bar = trun.Parameter()

        t1 = InsignificantParameterStep(foo='x', bar='y')
        self.assertEqual(str(t1), 'InsignificantParameterStep(bar=y)')

        t2 = InsignificantParameterStep('u', 'z')
        self.assertEqual(t2.foo, 'u')
        self.assertEqual(t2.bar, 'z')
        self.assertEqual(str(t2), 'InsignificantParameterStep(bar=z)')

    def test_local_significant_param(self):
        """ Obviously, if anything should be positional, so should local
        significant parameters """
        class MyStep(trun.Step):
            # This could typically be "--label-company=disney"
            x = trun.Parameter(significant=True)

        MyStep('arg')
        self.assertRaises(trun.parameter.MissingParameterException,
                          lambda: MyStep())

    def test_local_insignificant_param(self):
        """ Ensure we have the same behavior as in before a78338c  """
        class MyStep(trun.Step):
            # This could typically be "--num-threads=True"
            x = trun.Parameter(significant=False)

        MyStep('arg')
        self.assertRaises(trun.parameter.MissingParameterException,
                          lambda: MyStep())

    def test_nonpositional_param(self):
        """ Ensure we have the same behavior as in before a78338c  """
        class MyStep(trun.Step):
            # This could typically be "--num-threads=10"
            x = trun.Parameter(significant=False, positional=False)

        MyStep(x='arg')
        self.assertRaises(trun.parameter.UnknownParameterException,
                          lambda: MyStep('arg'))

    def test_enum_param_valid(self):
        p = trun.parameter.EnumParameter(enum=MyEnum)
        self.assertEqual(MyEnum.A, p.parse('A'))

    def test_enum_param_invalid(self):
        p = trun.parameter.EnumParameter(enum=MyEnum)
        self.assertRaises(ValueError, lambda: p.parse('B'))

    def test_enum_param_missing(self):
        self.assertRaises(ParameterException, lambda: trun.parameter.EnumParameter())

    def test_enum_list_param_valid(self):
        p = trun.parameter.EnumListParameter(enum=MyEnum)
        self.assertEqual((), p.parse(''))
        self.assertEqual((MyEnum.A,), p.parse('A'))
        self.assertEqual((MyEnum.A, MyEnum.C), p.parse('A,C'))

    def test_enum_list_param_invalid(self):
        p = trun.parameter.EnumListParameter(enum=MyEnum)
        self.assertRaises(ValueError, lambda: p.parse('A,B'))

    def test_enum_list_param_missing(self):
        self.assertRaises(ParameterException, lambda: trun.parameter.EnumListParameter())

    def test_tuple_serialize_parse(self):
        a = trun.TupleParameter()
        b_tuple = ((1, 2), (3, 4))
        self.assertEqual(b_tuple, a.parse(a.serialize(b_tuple)))

    def test_parse_list_without_batch_method(self):
        param = trun.Parameter()
        for xs in [], ['x'], ['x', 'y']:
            self.assertRaises(NotImplementedError, param._parse_list, xs)

    def test_parse_empty_list_raises_value_error(self):
        for batch_method in (max, min, tuple, ','.join):
            param = trun.Parameter(batch_method=batch_method)
            self.assertRaises(ValueError, param._parse_list, [])

    def test_parse_int_list_max(self):
        param = trun.IntParameter(batch_method=max)
        self.assertEqual(17, param._parse_list(['7', '17', '5']))

    def test_parse_string_list_max(self):
        param = trun.Parameter(batch_method=max)
        self.assertEqual('7', param._parse_list(['7', '17', '5']))

    def test_parse_list_as_tuple(self):
        param = trun.IntParameter(batch_method=tuple)
        self.assertEqual((7, 17, 5), param._parse_list(['7', '17', '5']))

    @mock.patch('trun.parameter.warnings')
    def test_warn_on_default_none(self, warnings):
        class TestConfig(trun.Config):
            param = trun.Parameter(default=None)

        TestConfig()
        warnings.warn.assert_called_once_with('Parameter "param" with value "None" is not of type string.')

    @mock.patch('trun.parameter.warnings')
    def test_no_warn_on_string(self, warnings):
        class TestConfig(trun.Config):
            param = trun.Parameter(default=None)

        TestConfig(param="str")
        warnings.warn.assert_not_called()

    def test_no_warn_on_none_in_optional(self):
        class TestConfig(trun.Config):
            param = trun.OptionalParameter(default=None)

        with mock.patch('trun.parameter.warnings') as warnings:
            TestConfig()
            warnings.warn.assert_not_called()

        with mock.patch('trun.parameter.warnings') as warnings:
            TestConfig(param=None)
            warnings.warn.assert_not_called()

        with mock.patch('trun.parameter.warnings') as warnings:
            TestConfig(param="")
            warnings.warn.assert_not_called()

    @mock.patch('trun.parameter.warnings')
    def test_no_warn_on_string_in_optional(self, warnings):
        class TestConfig(trun.Config):
            param = trun.OptionalParameter(default=None)

        TestConfig(param='value')
        warnings.warn.assert_not_called()

    @mock.patch('trun.parameter.warnings')
    def test_warn_on_bad_type_in_optional(self, warnings):
        class TestConfig(trun.Config):
            param = trun.OptionalParameter()

        TestConfig(param=1)
        warnings.warn.assert_called_once_with(
            'OptionalParameter "param" with value "1" is not of type "str" or None.',
            trun.parameter.OptionalParameterTypeWarning
        )

    def test_optional_parameter_parse_none(self):
        self.assertIsNone(trun.OptionalParameter().parse(''))

    def test_optional_parameter_parse_string(self):
        self.assertEqual('test', trun.OptionalParameter().parse('test'))

    def test_optional_parameter_serialize_none(self):
        self.assertEqual('', trun.OptionalParameter().serialize(None))

    def test_optional_parameter_serialize_string(self):
        self.assertEqual('test', trun.OptionalParameter().serialize('test'))


class TestParametersHashability(TrunTestCase):
    def test_date(self):
        class Foo(trun.Step):
            args = trun.parameter.DateParameter()
        p = trun.parameter.DateParameter()
        self.assertEqual(hash(Foo(args=datetime.date(2000, 1, 1)).args), hash(p.parse('2000-1-1')))

    def test_dateminute(self):
        class Foo(trun.Step):
            args = trun.parameter.DateMinuteParameter()
        p = trun.parameter.DateMinuteParameter()
        self.assertEqual(hash(Foo(args=datetime.datetime(2000, 1, 1, 12, 0)).args), hash(p.parse('2000-1-1T1200')))

    def test_dateinterval(self):
        class Foo(trun.Step):
            args = trun.parameter.DateIntervalParameter()
        p = trun.parameter.DateIntervalParameter()
        di = trun.date_interval.Custom(datetime.date(2000, 1, 1), datetime.date(2000, 2, 12))
        self.assertEqual(hash(Foo(args=di).args), hash(p.parse('2000-01-01-2000-02-12')))

    def test_timedelta(self):
        class Foo(trun.Step):
            args = trun.parameter.TimeDeltaParameter()
        p = trun.parameter.TimeDeltaParameter()
        self.assertEqual(hash(Foo(args=datetime.timedelta(days=2, hours=3, minutes=2)).args), hash(p.parse('P2DT3H2M')))

    def test_boolean(self):
        class Foo(trun.Step):
            args = trun.parameter.BoolParameter()

        p = trun.parameter.BoolParameter()

        self.assertEqual(hash(Foo(args=True).args), hash(p.parse('true')))
        self.assertEqual(hash(Foo(args=False).args), hash(p.parse('false')))

    def test_int(self):
        class Foo(trun.Step):
            args = trun.parameter.IntParameter()

        p = trun.parameter.IntParameter()
        self.assertEqual(hash(Foo(args=1).args), hash(p.parse('1')))

    def test_float(self):
        class Foo(trun.Step):
            args = trun.parameter.FloatParameter()

        p = trun.parameter.FloatParameter()
        self.assertEqual(hash(Foo(args=1.0).args), hash(p.parse('1')))

    def test_enum(self):
        class Foo(trun.Step):
            args = trun.parameter.EnumParameter(enum=MyEnum)

        p = trun.parameter.EnumParameter(enum=MyEnum)
        self.assertEqual(hash(Foo(args=MyEnum.A).args), hash(p.parse('A')))

    def test_enum_list(self):
        class Foo(trun.Step):
            args = trun.parameter.EnumListParameter(enum=MyEnum)

        p = trun.parameter.EnumListParameter(enum=MyEnum)
        self.assertEqual(hash(Foo(args=(MyEnum.A, MyEnum.C)).args), hash(p.parse('A,C')))

        class FooWithDefault(trun.Step):
            args = trun.parameter.EnumListParameter(enum=MyEnum, default=[MyEnum.C])

        self.assertEqual(FooWithDefault().args, p.parse('C'))

    def test_dict(self):
        class Foo(trun.Step):
            args = trun.parameter.DictParameter()

        p = trun.parameter.DictParameter()
        self.assertEqual(hash(Foo(args=dict(foo=1, bar="hello")).args), hash(p.parse('{"foo":1,"bar":"hello"}')))

    def test_list(self):
        class Foo(trun.Step):
            args = trun.parameter.ListParameter()

        p = trun.parameter.ListParameter()
        self.assertEqual(hash(Foo(args=[1, "hello"]).args), hash(p.normalize(p.parse('[1,"hello"]'))))

    def test_list_param_with_default_none_in_dynamic_req_step(self):
        class StepWithDefaultNoneParameter(RunOnceStep):
            args = trun.parameter.ListParameter(default=None)

        class DynamicStepCallsDefaultNoneParameter(RunOnceStep):
            def run(self):
                yield [StepWithDefaultNoneParameter()]
                self.comp = True

        self.assertTrue(self.run_locally(['DynamicStepCallsDefaultNoneParameter']))

    def test_list_dict(self):
        class Foo(trun.Step):
            args = trun.parameter.ListParameter()

        p = trun.parameter.ListParameter()
        self.assertEqual(hash(Foo(args=[{'foo': 'bar'}, {'doge': 'wow'}]).args),
                         hash(p.normalize(p.parse('[{"foo": "bar"}, {"doge": "wow"}]'))))

    def test_list_nested(self):
        class Foo(trun.Step):
            args = trun.parameter.ListParameter()

        p = trun.parameter.ListParameter()
        self.assertEqual(hash(Foo(args=[['foo', 'bar'], ['doge', 'wow']]).args),
                         hash(p.normalize(p.parse('[["foo", "bar"], ["doge", "wow"]]'))))

    def test_tuple(self):
        class Foo(trun.Step):
            args = trun.parameter.TupleParameter()

        p = trun.parameter.TupleParameter()
        self.assertEqual(hash(Foo(args=(1, "hello")).args), hash(p.parse('(1,"hello")')))

    def test_tuple_dict(self):
        class Foo(trun.Step):
            args = trun.parameter.TupleParameter()

        p = trun.parameter.TupleParameter()
        self.assertEqual(hash(Foo(args=({'foo': 'bar'}, {'doge': 'wow'})).args),
                         hash(p.normalize(p.parse('({"foo": "bar"}, {"doge": "wow"})'))))

    def test_tuple_nested(self):
        class Foo(trun.Step):
            args = trun.parameter.TupleParameter()

        p = trun.parameter.TupleParameter()
        self.assertEqual(hash(Foo(args=(('foo', 'bar'), ('doge', 'wow'))).args),
                         hash(p.normalize(p.parse('(("foo", "bar"), ("doge", "wow"))'))))

    def test_tuple_string_with_json(self):
        class Foo(trun.Step):
            args = trun.parameter.TupleParameter()

        p = trun.parameter.TupleParameter()
        self.assertEqual(hash(Foo(args=('foo', 'bar')).args),
                         hash(p.normalize(p.parse('["foo", "bar"]'))))

    def test_step(self):
        class Bar(trun.Step):
            pass

        class Foo(trun.Step):
            args = trun.parameter.StepParameter()

        p = trun.parameter.StepParameter()
        self.assertEqual(hash(Foo(args=Bar).args), hash(p.parse('Bar')))


class TestNewStyleGlobalParameters(TrunTestCase):

    def setUp(self):
        super(TestNewStyleGlobalParameters, self).setUp()
        MockTarget.fs.clear()

    def expect_keys(self, expected):
        self.assertEqual(set(MockTarget.fs.get_all_data().keys()), set(expected))

    def test_x_arg(self):
        self.run_locally(['Banana', '--x', 'foo', '--y', 'bar', '--style', 'x-arg'])
        self.expect_keys(['banana-foo-bar', 'banana-dep-foo-def'])

    def test_x_arg_override(self):
        self.run_locally(['Banana', '--x', 'foo', '--y', 'bar', '--style', 'x-arg', '--BananaDep-y', 'xyz'])
        self.expect_keys(['banana-foo-bar', 'banana-dep-foo-xyz'])

    def test_x_arg_override_stupid(self):
        self.run_locally(['Banana', '--x', 'foo', '--y', 'bar', '--style', 'x-arg', '--BananaDep-x', 'blabla'])
        self.expect_keys(['banana-foo-bar', 'banana-dep-foo-def'])

    def test_x_arg_y_arg(self):
        self.run_locally(['Banana', '--x', 'foo', '--y', 'bar', '--style', 'x-arg-y-arg'])
        self.expect_keys(['banana-foo-bar', 'banana-dep-foo-bar'])

    def test_x_arg_y_arg_override(self):
        self.run_locally(['Banana', '--x', 'foo', '--y', 'bar', '--style', 'x-arg-y-arg', '--BananaDep-y', 'xyz'])
        self.expect_keys(['banana-foo-bar', 'banana-dep-foo-bar'])

    def test_x_arg_y_arg_override_all(self):
        self.run_locally(['Banana', '--x', 'foo',
                          '--y', 'bar', '--style', 'x-arg-y-arg', '--BananaDep-y',
                          'xyz', '--BananaDep-x', 'blabla'])
        self.expect_keys(['banana-foo-bar', 'banana-dep-foo-bar'])

    def test_y_arg_override(self):
        self.run_locally(['Banana', '--x', 'foo', '--y', 'bar', '--style', 'y-kwarg', '--BananaDep-x', 'xyz'])
        self.expect_keys(['banana-foo-bar', 'banana-dep-xyz-bar'])

    def test_y_arg_override_both(self):
        self.run_locally(['Banana', '--x', 'foo',
                          '--y', 'bar', '--style', 'y-kwarg', '--BananaDep-x', 'xyz',
                          '--BananaDep-y', 'blah'])
        self.expect_keys(['banana-foo-bar', 'banana-dep-xyz-bar'])

    def test_y_arg_override_banana(self):
        self.run_locally(['Banana', '--y', 'bar', '--style', 'y-kwarg', '--BananaDep-x', 'xyz', '--Banana-x', 'baz'])
        self.expect_keys(['banana-baz-bar', 'banana-dep-xyz-bar'])


class TestRemoveGlobalParameters(TrunTestCase):

    def run_and_check(self, args):
        run_exit_status = self.run_locally(args)
        self.assertTrue(run_exit_status)
        return run_exit_status

    @parsing(['--MyConfig-mc-p', '99', '--mc-r', '55', 'NoopStep'])
    def test_use_config_class_1(self):
        self.assertEqual(MyConfig().mc_p, 99)
        self.assertEqual(MyConfig().mc_q, 73)
        self.assertEqual(MyConfigWithoutSection().mc_r, 55)
        self.assertEqual(MyConfigWithoutSection().mc_s, 99)

    @parsing(['NoopStep', '--MyConfig-mc-p', '99', '--mc-r', '55'])
    def test_use_config_class_2(self):
        self.assertEqual(MyConfig().mc_p, 99)
        self.assertEqual(MyConfig().mc_q, 73)
        self.assertEqual(MyConfigWithoutSection().mc_r, 55)
        self.assertEqual(MyConfigWithoutSection().mc_s, 99)

    @parsing(['--MyConfig-mc-p', '99', '--mc-r', '55', 'NoopStep', '--mc-s', '123', '--MyConfig-mc-q', '42'])
    def test_use_config_class_more_args(self):
        self.assertEqual(MyConfig().mc_p, 99)
        self.assertEqual(MyConfig().mc_q, 42)
        self.assertEqual(MyConfigWithoutSection().mc_r, 55)
        self.assertEqual(MyConfigWithoutSection().mc_s, 123)

    @with_config({"MyConfig": {"mc_p": "666", "mc_q": "777"}})
    @parsing(['--mc-r', '555', 'NoopStep'])
    def test_use_config_class_with_configuration(self):
        self.assertEqual(MyConfig().mc_p, 666)
        self.assertEqual(MyConfig().mc_q, 777)
        self.assertEqual(MyConfigWithoutSection().mc_r, 555)
        self.assertEqual(MyConfigWithoutSection().mc_s, 99)

    @with_config({"MyConfigWithoutSection": {"mc_r": "999", "mc_s": "888"}})
    @parsing(['NoopStep', '--MyConfig-mc-p', '222', '--mc-r', '555'])
    def test_use_config_class_with_configuration_2(self):
        self.assertEqual(MyConfig().mc_p, 222)
        self.assertEqual(MyConfig().mc_q, 73)
        self.assertEqual(MyConfigWithoutSection().mc_r, 555)
        self.assertEqual(MyConfigWithoutSection().mc_s, 888)

    @with_config({"MyConfig": {"mc_p": "555", "mc-p": "666", "mc-q": "777"}})
    def test_configuration_style(self):
        self.assertEqual(MyConfig().mc_p, 555)
        self.assertEqual(MyConfig().mc_q, 777)

    def test_misc_1(self):
        class Dogs(trun.Config):
            n_dogs = trun.IntParameter()

        class CatsWithoutSection(trun.Config):
            use_cmdline_section = False
            n_cats = trun.IntParameter()

        with trun.cmdline_parser.CmdlineParser.global_instance(['--n-cats', '123', '--Dogs-n-dogs', '456', 'WithDefault'], allow_override=True):
            self.assertEqual(Dogs().n_dogs, 456)
            self.assertEqual(CatsWithoutSection().n_cats, 123)

        with trun.cmdline_parser.CmdlineParser.global_instance(['WithDefault', '--n-cats', '321', '--Dogs-n-dogs', '654'], allow_override=True):
            self.assertEqual(Dogs().n_dogs, 654)
            self.assertEqual(CatsWithoutSection().n_cats, 321)

    def test_global_significant_param_warning(self):
        """ We don't want any kind of global param to be positional """
        with self.assertWarnsRegex(DeprecationWarning, 'is_global support is removed. Assuming positional=False'):
            class MyStep(trun.Step):
                # This could typically be called "--test-dry-run"
                x_g1 = trun.Parameter(default='y', is_global=True, significant=True)

        self.assertRaises(trun.parameter.UnknownParameterException,
                          lambda: MyStep('arg'))

        def test_global_insignificant_param_warning(self):
            """ We don't want any kind of global param to be positional """
            with self.assertWarnsRegex(DeprecationWarning, 'is_global support is removed. Assuming positional=False'):
                class MyStep(trun.Step):
                    # This could typically be "--yarn-pool=development"
                    x_g2 = trun.Parameter(default='y', is_global=True, significant=False)

            self.assertRaises(trun.parameter.UnknownParameterException,
                              lambda: MyStep('arg'))


class TestParamWithDefaultFromConfig(TrunTestCase):

    def testNoSection(self):
        self.assertRaises(ParameterException, lambda: _value(trun.Parameter(config_path=dict(section="foo", name="bar"))))

    @with_config({"foo": {}})
    def testNoValue(self):
        self.assertRaises(ParameterException, lambda: _value(trun.Parameter(config_path=dict(section="foo", name="bar"))))

    @with_config({"foo": {"bar": "baz"}})
    def testDefault(self):
        class LocalA(trun.Step):
            p = trun.Parameter(config_path=dict(section="foo", name="bar"))

        self.assertEqual("baz", LocalA().p)
        self.assertEqual("boo", LocalA(p="boo").p)

    @with_config({"foo": {"bar": "2001-02-03T04"}})
    def testDateHour(self):
        p = trun.DateHourParameter(config_path=dict(section="foo", name="bar"))
        self.assertEqual(datetime.datetime(2001, 2, 3, 4, 0, 0), _value(p))

    @with_config({"foo": {"bar": "2001-02-03T05"}})
    def testDateHourWithInterval(self):
        p = trun.DateHourParameter(config_path=dict(section="foo", name="bar"), interval=2)
        self.assertEqual(datetime.datetime(2001, 2, 3, 4, 0, 0), _value(p))

    @with_config({"foo": {"bar": "2001-02-03T0430"}})
    def testDateMinute(self):
        p = trun.DateMinuteParameter(config_path=dict(section="foo", name="bar"))
        self.assertEqual(datetime.datetime(2001, 2, 3, 4, 30, 0), _value(p))

    @with_config({"foo": {"bar": "2001-02-03T0431"}})
    def testDateWithMinuteInterval(self):
        p = trun.DateMinuteParameter(config_path=dict(section="foo", name="bar"), interval=2)
        self.assertEqual(datetime.datetime(2001, 2, 3, 4, 30, 0), _value(p))

    @with_config({"foo": {"bar": "2001-02-03T04H30"}})
    def testDateMinuteDeprecated(self):
        p = trun.DateMinuteParameter(config_path=dict(section="foo", name="bar"))
        with self.assertWarnsRegex(DeprecationWarning,
                                   'Using "H" between hours and minutes is deprecated, omit it instead.'):
            self.assertEqual(datetime.datetime(2001, 2, 3, 4, 30, 0), _value(p))

    @with_config({"foo": {"bar": "2001-02-03T040506"}})
    def testDateSecond(self):
        p = trun.DateSecondParameter(config_path=dict(section="foo", name="bar"))
        self.assertEqual(datetime.datetime(2001, 2, 3, 4, 5, 6), _value(p))

    @with_config({"foo": {"bar": "2001-02-03T040507"}})
    def testDateSecondWithInterval(self):
        p = trun.DateSecondParameter(config_path=dict(section="foo", name="bar"), interval=2)
        self.assertEqual(datetime.datetime(2001, 2, 3, 4, 5, 6), _value(p))

    @with_config({"foo": {"bar": "2001-02-03"}})
    def testDate(self):
        p = trun.DateParameter(config_path=dict(section="foo", name="bar"))
        self.assertEqual(datetime.date(2001, 2, 3), _value(p))

    @with_config({"foo": {"bar": "2001-02-03"}})
    def testDateWithInterval(self):
        p = trun.DateParameter(config_path=dict(section="foo", name="bar"),
                                interval=3, start=datetime.date(2001, 2, 1))
        self.assertEqual(datetime.date(2001, 2, 1), _value(p))

    @with_config({"foo": {"bar": "2015-07"}})
    def testMonthParameter(self):
        p = trun.MonthParameter(config_path=dict(section="foo", name="bar"))
        self.assertEqual(datetime.date(2015, 7, 1), _value(p))

    @with_config({"foo": {"bar": "2015-07"}})
    def testMonthWithIntervalParameter(self):
        p = trun.MonthParameter(config_path=dict(section="foo", name="bar"),
                                 interval=13, start=datetime.date(2014, 1, 1))
        self.assertEqual(datetime.date(2015, 2, 1), _value(p))

    @with_config({"foo": {"bar": "2015"}})
    def testYearParameter(self):
        p = trun.YearParameter(config_path=dict(section="foo", name="bar"))
        self.assertEqual(datetime.date(2015, 1, 1), _value(p))

    @with_config({"foo": {"bar": "2015"}})
    def testYearWithIntervalParameter(self):
        p = trun.YearParameter(config_path=dict(section="foo", name="bar"),
                                start=datetime.date(2011, 1, 1), interval=5)
        self.assertEqual(datetime.date(2011, 1, 1), _value(p))

    @with_config({"foo": {"bar": "123"}})
    def testInt(self):
        p = trun.IntParameter(config_path=dict(section="foo", name="bar"))
        self.assertEqual(123, _value(p))

    @with_config({"foo": {"bar": "true"}})
    def testBool(self):
        p = trun.BoolParameter(config_path=dict(section="foo", name="bar"))
        self.assertEqual(True, _value(p))

    @with_config({"foo": {"bar": "false"}})
    def testBoolConfigOutranksDefault(self):
        p = trun.BoolParameter(default=True, config_path=dict(section="foo", name="bar"))
        self.assertEqual(False, _value(p))

    @with_config({"foo": {"bar": "2001-02-03-2001-02-28"}})
    def testDateInterval(self):
        p = trun.DateIntervalParameter(config_path=dict(section="foo", name="bar"))
        expected = trun.date_interval.Custom.parse("2001-02-03-2001-02-28")
        self.assertEqual(expected, _value(p))

    @with_config({"foo": {"bar": "0 seconds"}})
    def testTimeDeltaNoSeconds(self):
        p = trun.TimeDeltaParameter(config_path=dict(section="foo", name="bar"))
        self.assertEqual(timedelta(seconds=0), _value(p))

    @with_config({"foo": {"bar": "0 d"}})
    def testTimeDeltaNoDays(self):
        p = trun.TimeDeltaParameter(config_path=dict(section="foo", name="bar"))
        self.assertEqual(timedelta(days=0), _value(p))

    @with_config({"foo": {"bar": "1 day"}})
    def testTimeDelta(self):
        p = trun.TimeDeltaParameter(config_path=dict(section="foo", name="bar"))
        self.assertEqual(timedelta(days=1), _value(p))

    @with_config({"foo": {"bar": "2 seconds"}})
    def testTimeDeltaPlural(self):
        p = trun.TimeDeltaParameter(config_path=dict(section="foo", name="bar"))
        self.assertEqual(timedelta(seconds=2), _value(p))

    @with_config({"foo": {"bar": "3w 4h 5m"}})
    def testTimeDeltaMultiple(self):
        p = trun.TimeDeltaParameter(config_path=dict(section="foo", name="bar"))
        self.assertEqual(timedelta(weeks=3, hours=4, minutes=5), _value(p))

    @with_config({"foo": {"bar": "P4DT12H30M5S"}})
    def testTimeDelta8601(self):
        p = trun.TimeDeltaParameter(config_path=dict(section="foo", name="bar"))
        self.assertEqual(timedelta(days=4, hours=12, minutes=30, seconds=5), _value(p))

    @with_config({"foo": {"bar": "P5D"}})
    def testTimeDelta8601NoTimeComponent(self):
        p = trun.TimeDeltaParameter(config_path=dict(section="foo", name="bar"))
        self.assertEqual(timedelta(days=5), _value(p))

    @with_config({"foo": {"bar": "P5W"}})
    def testTimeDelta8601Weeks(self):
        p = trun.TimeDeltaParameter(config_path=dict(section="foo", name="bar"))
        self.assertEqual(timedelta(weeks=5), _value(p))

    @mock.patch('trun.parameter.ParameterException')
    @with_config({"foo": {"bar": "P3Y6M4DT12H30M5S"}})
    def testTimeDelta8601YearMonthNotSupported(self, exc):
        def f():
            return _value(trun.TimeDeltaParameter(config_path=dict(section="foo", name="bar")))
        self.assertRaises(ValueError, f)  # ISO 8601 durations with years or months are not supported
        exc.assert_called_once_with("Invalid time delta - could not parse P3Y6M4DT12H30M5S")

    @with_config({"foo": {"bar": "PT6M"}})
    def testTimeDelta8601MAfterT(self):
        p = trun.TimeDeltaParameter(config_path=dict(section="foo", name="bar"))
        self.assertEqual(timedelta(minutes=6), _value(p))

    @mock.patch('trun.parameter.ParameterException')
    @with_config({"foo": {"bar": "P6M"}})
    def testTimeDelta8601MBeforeT(self, exc):
        def f():
            return _value(trun.TimeDeltaParameter(config_path=dict(section="foo", name="bar")))
        self.assertRaises(ValueError, f)  # ISO 8601 durations with months are not supported
        exc.assert_called_once_with("Invalid time delta - could not parse P6M")

    @with_config({"foo": {"bar": "12.34"}})
    def testTimeDeltaFloat(self):
        p = trun.TimeDeltaParameter(config_path=dict(section="foo", name="bar"))
        self.assertEqual(timedelta(seconds=12.34), _value(p))

    @with_config({"foo": {"bar": "56789"}})
    def testTimeDeltaInt(self):
        p = trun.TimeDeltaParameter(config_path=dict(section="foo", name="bar"))
        self.assertEqual(timedelta(seconds=56789), _value(p))

    def testHasDefaultNoSection(self):
        self.assertRaises(trun.parameter.MissingParameterException,
                          lambda: _value(trun.Parameter(config_path=dict(section="foo", name="bar"))))

    @with_config({"foo": {}})
    def testHasDefaultNoValue(self):
        self.assertRaises(trun.parameter.MissingParameterException,
                          lambda: _value(trun.Parameter(config_path=dict(section="foo", name="bar"))))

    @with_config({"foo": {"bar": "baz"}})
    def testHasDefaultWithBoth(self):
        self.assertTrue(_value(trun.Parameter(config_path=dict(section="foo", name="bar"))))

    @with_config({"foo": {"bar": "baz"}})
    def testWithDefault(self):
        p = trun.Parameter(config_path=dict(section="foo", name="bar"), default='blah')
        self.assertEqual('baz', _value(p))  # config overrides default

    def testWithDefaultAndMissing(self):
        p = trun.Parameter(config_path=dict(section="foo", name="bar"), default='blah')
        self.assertEqual('blah', _value(p))

    @with_config({"LocalA": {"p": "p_default"}})
    def testDefaultFromStepName(self):
        class LocalA(trun.Step):
            p = trun.Parameter()

        self.assertEqual("p_default", LocalA().p)
        self.assertEqual("boo", LocalA(p="boo").p)

    @with_config({"LocalA": {"p": "999"}})
    def testDefaultFromStepNameInt(self):
        class LocalA(trun.Step):
            p = trun.IntParameter()

        self.assertEqual(999, LocalA().p)
        self.assertEqual(777, LocalA(p=777).p)

    @with_config({"LocalA": {"p": "p_default"}, "foo": {"bar": "baz"}})
    def testDefaultFromConfigWithStepNameToo(self):
        class LocalA(trun.Step):
            p = trun.Parameter(config_path=dict(section="foo", name="bar"))

        self.assertEqual("p_default", LocalA().p)
        self.assertEqual("boo", LocalA(p="boo").p)

    @with_config({"LocalA": {"p": "p_default_2"}})
    def testDefaultFromStepNameWithDefault(self):
        class LocalA(trun.Step):
            p = trun.Parameter(default="banana")

        self.assertEqual("p_default_2", LocalA().p)
        self.assertEqual("boo_2", LocalA(p="boo_2").p)

    @with_config({"MyClass": {"p_wohoo": "p_default_3"}})
    def testWithLongParameterName(self):
        class MyClass(trun.Step):
            p_wohoo = trun.Parameter(default="banana")

        self.assertEqual("p_default_3", MyClass().p_wohoo)
        self.assertEqual("boo_2", MyClass(p_wohoo="boo_2").p_wohoo)

    @with_config({"RangeDaily": {"days_back": "123"}})
    def testSettingOtherMember(self):
        class LocalA(trun.Step):
            pass

        self.assertEqual(123, trun.tools.range.RangeDaily(of=LocalA).days_back)
        self.assertEqual(70, trun.tools.range.RangeDaily(of=LocalA, days_back=70).days_back)

    @with_config({"MyClass": {"p_not_global": "123"}})
    def testCommandLineWithDefault(self):
        """
        Verify that we also read from the config when we build steps from the
        command line parsers.
        """
        class MyClass(trun.Step):
            p_not_global = trun.Parameter(default='banana')

            def complete(self):
                import sys
                trun.configuration.get_config().write(sys.stdout)
                if self.p_not_global != "123":
                    raise ValueError("The parameter didn't get set!!")
                return True

            def run(self):
                pass

        self.assertTrue(self.run_locally(['MyClass']))
        self.assertFalse(self.run_locally(['MyClass', '--p-not-global', '124']))
        self.assertFalse(self.run_locally(['MyClass', '--MyClass-p-not-global', '124']))

    @with_config({"MyClass2": {"p_not_global_no_default": "123"}})
    def testCommandLineNoDefault(self):
        """
        Verify that we also read from the config when we build steps from the
        command line parsers.
        """
        class MyClass2(trun.Step):
            """ TODO: Make trun clean it's register for tests. Hate this 2 dance. """
            p_not_global_no_default = trun.Parameter()

            def complete(self):
                import sys
                trun.configuration.get_config().write(sys.stdout)
                trun.configuration.get_config().write(sys.stdout)
                if self.p_not_global_no_default != "123":
                    raise ValueError("The parameter didn't get set!!")
                return True

            def run(self):
                pass

        self.assertTrue(self.run_locally(['MyClass2']))
        self.assertFalse(self.run_locally(['MyClass2', '--p-not-global-no-default', '124']))
        self.assertFalse(self.run_locally(['MyClass2', '--MyClass2-p-not-global-no-default', '124']))

    @with_config({"mynamespace.A": {"p": "999"}})
    def testWithNamespaceConfig(self):
        class A(trun.Step):
            step_namespace = 'mynamespace'
            p = trun.IntParameter()

        self.assertEqual(999, A().p)
        self.assertEqual(777, A(p=777).p)

    def testWithNamespaceCli(self):
        class A(trun.Step):
            step_namespace = 'mynamespace'
            p = trun.IntParameter(default=100)
            expected = trun.IntParameter()

            def complete(self):
                if self.p != self.expected:
                    raise ValueError
                return True

        self.assertTrue(self.run_locally_split('mynamespace.A --expected 100'))
        # TODO(arash): Why is `--p 200` hanging with multiprocessing stuff?
        # self.assertTrue(self.run_locally_split('mynamespace.A --p 200 --expected 200'))
        self.assertTrue(self.run_locally_split('mynamespace.A --mynamespace.A-p 200 --expected 200'))
        self.assertFalse(self.run_locally_split('mynamespace.A --A-p 200 --expected 200'))

    def testListWithNamespaceCli(self):
        class A(trun.Step):
            step_namespace = 'mynamespace'
            l_param = trun.ListParameter(default=[1, 2, 3])
            expected = trun.ListParameter()

            def complete(self):
                if self.l_param != self.expected:
                    raise ValueError
                return True

        self.assertTrue(self.run_locally_split('mynamespace.A --expected [1,2,3]'))
        self.assertTrue(self.run_locally_split('mynamespace.A --mynamespace.A-l [1,2,3] --expected [1,2,3]'))

    def testTupleWithNamespaceCli(self):
        class A(trun.Step):
            step_namespace = 'mynamespace'
            t = trun.TupleParameter(default=((1, 2), (3, 4)))
            expected = trun.TupleParameter()

            def complete(self):
                if self.t != self.expected:
                    raise ValueError
                return True

        self.assertTrue(self.run_locally_split('mynamespace.A --expected ((1,2),(3,4))'))
        self.assertTrue(self.run_locally_split('mynamespace.A --mynamespace.A-t ((1,2),(3,4)) --expected ((1,2),(3,4))'))

    @with_config({"foo": {"bar": "[1,2,3]"}})
    def testListConfig(self):
        self.assertTrue(_value(trun.ListParameter(config_path=dict(section="foo", name="bar"))))

    @with_config({"foo": {"bar": "((1,2),(3,4))"}})
    def testTupleConfig(self):
        self.assertTrue(_value(trun.TupleParameter(config_path=dict(section="foo", name="bar"))))

    @with_config({"foo": {"bar": "-3"}})
    def testNumericalParameter(self):
        p = trun.NumericalParameter(min_value=-3, max_value=7, var_type=int, config_path=dict(section="foo", name="bar"))
        self.assertEqual(-3, _value(p))

    @with_config({"foo": {"bar": "3"}})
    def testChoiceParameter(self):
        p = trun.ChoiceParameter(var_type=int, choices=[1, 2, 3], config_path=dict(section="foo", name="bar"))
        self.assertEqual(3, _value(p))


class OverrideEnvStuff(TrunTestCase):

    @with_config({"core": {"default-scheduler-port": '6543'}})
    def testOverrideSchedulerPort(self):
        with self.assertWarnsRegex(DeprecationWarning, r'default-scheduler-port is deprecated'):
            env_params = trun.interface.core()
            self.assertEqual(env_params.scheduler_port, 6543)

    @with_config({"core": {"scheduler-port": '6544'}})
    def testOverrideSchedulerPort2(self):
        with self.assertWarnsRegex(DeprecationWarning, r'scheduler-port \(with dashes\) should be avoided'):
            env_params = trun.interface.core()
        self.assertEqual(env_params.scheduler_port, 6544)

    @with_config({"core": {"scheduler_port": '6545'}})
    def testOverrideSchedulerPort3(self):
        env_params = trun.interface.core()
        self.assertEqual(env_params.scheduler_port, 6545)


class TestSerializeDateParameters(TrunTestCase):

    def testSerialize(self):
        date = datetime.date(2013, 2, 3)
        self.assertEqual(trun.DateParameter().serialize(date), '2013-02-03')
        self.assertEqual(trun.YearParameter().serialize(date), '2013')
        self.assertEqual(trun.MonthParameter().serialize(date), '2013-02')
        dt = datetime.datetime(2013, 2, 3, 4, 5)
        self.assertEqual(trun.DateHourParameter().serialize(dt), '2013-02-03T04')


class TestSerializeTimeDeltaParameters(TrunTestCase):

    def testSerialize(self):
        tdelta = timedelta(weeks=5, days=4, hours=3, minutes=2, seconds=1)
        self.assertEqual(trun.TimeDeltaParameter().serialize(tdelta), '5 w 4 d 3 h 2 m 1 s')
        tdelta = timedelta(seconds=0)
        self.assertEqual(trun.TimeDeltaParameter().serialize(tdelta), '0 w 0 d 0 h 0 m 0 s')


class TestStepParameter(TrunTestCase):

    def testUsage(self):

        class MetaStep(trun.Step):
            step_namespace = "mynamespace"
            a = trun.StepParameter()

            def run(self):
                self.__class__.saved_value = self.a

        class OtherStep(trun.Step):
            step_namespace = "other_namespace"

        self.assertEqual(MetaStep(a=MetaStep).a, MetaStep)
        self.assertEqual(MetaStep(a=OtherStep).a, OtherStep)

        # So I first thought this "should" work, but actually it should not,
        # because it should not need to parse values known at run-time
        self.assertRaises(AttributeError,
                          lambda: MetaStep(a="mynamespace.MetaStep"))

        # But is should be able to parse command line arguments
        self.assertRaises(trun.step_register.StepClassNotFoundException,
                          lambda: (self.run_locally_split('mynamespace.MetaStep --a blah')))
        self.assertRaises(trun.step_register.StepClassNotFoundException,
                          lambda: (self.run_locally_split('mynamespace.MetaStep --a Stepk')))
        self.assertTrue(self.run_locally_split('mynamespace.MetaStep --a mynamespace.MetaStep'))
        self.assertEqual(MetaStep.saved_value, MetaStep)
        self.assertTrue(self.run_locally_split('mynamespace.MetaStep --a other_namespace.OtherStep'))
        self.assertEqual(MetaStep.saved_value, OtherStep)

    def testSerialize(self):

        class OtherStep(trun.Step):

            def complete(self):
                return True

        class DepStep(trun.Step):

            dep = trun.StepParameter()
            ran = False

            def complete(self):
                return self.__class__.ran

            def requires(self):
                return self.dep()

            def run(self):
                self.__class__.ran = True

        class MainStep(trun.Step):

            def run(self):
                yield DepStep(dep=OtherStep)

        # OtherStep is serialized because it is used as an argument for DepStep.
        self.assertTrue(self.run_locally(['MainStep']))


class TestSerializeTupleParameter(TrunTestCase):
    def testSerialize(self):
        the_tuple = (1, 2, 3)

        self.assertEqual(trun.TupleParameter().parse(trun.TupleParameter().serialize(the_tuple)), the_tuple)


class NewStyleParameters822Test(TrunTestCase):
    """
    I bet these tests created at 2015-03-08 are reduntant by now (Oct 2015).
    But maintaining them anyway, just in case I have overlooked something.
    """
    # See https://github.com/spotify/trun/issues/822

    def test_subclasses(self):
        class BarBaseClass(trun.Step):
            x = trun.Parameter(default='bar_base_default')

        class BarSubClass(BarBaseClass):
            pass

        in_parse(['BarSubClass', '--x', 'xyz', '--BarBaseClass-x', 'xyz'],
                 lambda step: self.assertEqual(step.x, 'xyz'))

        # https://github.com/spotify/trun/issues/822#issuecomment-77782714
        in_parse(['BarBaseClass', '--BarBaseClass-x', 'xyz'],
                 lambda step: self.assertEqual(step.x, 'xyz'))


class LocalParameters1304Test(TrunTestCase):
    """
    It was discussed and decided that local parameters (--x) should be
    semantically different from global parameters (--MyStep-x).

    The former sets only the parsed root step, and the later sets the parameter
    for all the steps.

    https://github.com/spotify/trun/issues/1304#issuecomment-148402284
    """
    def test_local_params(self):

        class MyStep(RunOnceStep):
            param1 = trun.IntParameter()
            param2 = trun.BoolParameter(default=False)

            def requires(self):
                if self.param1 > 0:
                    yield MyStep(param1=(self.param1 - 1))

            def run(self):
                assert self.param1 == 1 or not self.param2
                self.comp = True

        self.assertTrue(self.run_locally_split('MyStep --param1 1 --param2'))

    def test_local_takes_precedence(self):

        class MyStep(trun.Step):
            param = trun.IntParameter()

            def complete(self):
                return False

            def run(self):
                assert self.param == 5

        self.assertTrue(self.run_locally_split('MyStep --param 5 --MyStep-param 6'))

    def test_local_only_affects_root(self):

        class MyStep(RunOnceStep):
            param = trun.IntParameter(default=3)

            def requires(self):
                assert self.param != 3
                if self.param == 5:
                    yield MyStep()

        # It would be a cyclic dependency if local took precedence
        self.assertTrue(self.run_locally_split('MyStep --param 5 --MyStep-param 6'))

    def test_range_doesnt_propagate_args(self):
        """
        Ensure that ``--step Range --of Blah --blah-arg 123`` doesn't work.

        This will of course not work unless support is explicitly added for it.
        But being a bit paranoid here and adding this test case so that if
        somebody decides to add it in the future, they'll be redircted to the
        dicussion in #1304
        """

        class Blah(RunOnceStep):
            date = trun.DateParameter()
            blah_arg = trun.IntParameter()

        # The SystemExit is assumed to be thrown by argparse
        self.assertRaises(SystemExit, self.run_locally_split, 'RangeDailyBase --of Blah --start 2015-01-01 --step-limit 1 --blah-arg 123')
        self.assertTrue(self.run_locally_split('RangeDailyBase --of Blah --start 2015-01-01 --step-limit 1 --Blah-blah-arg 123'))


class StepAsParameterName1335Test(TrunTestCase):
    def test_parameter_can_be_named_step(self):

        class MyStep(trun.Step):
            # Indeed, this is not the most realistic example, but still ...
            step = trun.IntParameter()

        self.assertTrue(self.run_locally_split('MyStep --step 5'))


class TestPathParameter:

    @pytest.fixture(params=[None, "not_existing_dir"])
    def default(self, request):
        return request.param

    @pytest.fixture(params=[True, False])
    def absolute(self, request):
        return request.param

    @pytest.fixture(params=[True, False])
    def exists(self, request):
        return request.param

    @pytest.fixture()
    def path_parameter(self, tmpdir, default, absolute, exists):
        class StepPathParameter(trun.Step):

            a = trun.PathParameter(
                default=str(tmpdir / default) if default is not None else str(tmpdir),
                absolute=absolute,
                exists=exists,
            )
            b = trun.OptionalPathParameter(
                default=str(tmpdir / default) if default is not None else str(tmpdir),
                absolute=absolute,
                exists=exists,
            )
            c = trun.OptionalPathParameter(default=None)
            d = trun.OptionalPathParameter(default="not empty default")

            def run(self):
                # Use the parameter as a Path object
                new_file = self.a / "test.file"
                new_optional_file = self.b / "test_optional.file"
                if default is not None:
                    new_file.parent.mkdir(parents=True)
                new_file.touch()
                new_optional_file.touch()
                assert new_file.exists()
                assert new_optional_file.exists()
                assert self.c is None
                assert self.d is None

            def output(self):
                return trun.LocalTarget("not_existing_file")

        return {
            "tmpdir": tmpdir,
            "default": default,
            "absolute": absolute,
            "exists": exists,
            "cls": StepPathParameter,
        }

    @with_config({"StepPathParameter": {"d": ""}})
    def test_exists(self, path_parameter):
        if path_parameter["default"] is not None and path_parameter["exists"]:
            with pytest.raises(ValueError, match="The path .* does not exist"):
                trun.build([path_parameter["cls"]()], local_scheduler=True)
        else:
            assert trun.build([path_parameter["cls"]()], local_scheduler=True)
