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
import pickle
from helpers import unittest

import luigi
import luigi.notifications
from luigi.mock import MockTarget
from luigi.parameter import MissingParameterException
from luigi.util import common_params, copies, delegates, inherits, requires

luigi.notifications.DEBUG = True


class A(luigi.Step):
    step_namespace = 'decorator'  # to prevent step name conflict between tests
    param1 = luigi.Parameter("class A-specific default")


@inherits(A)
class B(luigi.Step):
    param2 = luigi.Parameter("class B-specific default")


@inherits(B)
class C(luigi.Step):
    param3 = luigi.Parameter("class C-specific default")


@inherits(B)
class D(luigi.Step):
    param1 = luigi.Parameter("class D overwriting class A's default")


@inherits(B)
class D_null(luigi.Step):
    param1 = None


@inherits(A, B)
class E(luigi.Step):
    param4 = luigi.Parameter("class E-specific default")


@inherits(A)
@inherits(B)
class E_stacked(luigi.Step):
    param4 = luigi.Parameter("class E-specific default")


class InheritTest(unittest.TestCase):

    def setUp(self):
        self.a = A()
        self.a_changed = A(param1=34)
        self.b = B()
        self.c = C()
        self.d = D()
        self.d_null = D_null()
        self.e = E()
        self.e_stacked = E_stacked()

    def test_has_param(self):
        b_params = dict(self.b.get_params()).keys()
        self.assertTrue("param1" in b_params)

    def test_default_param(self):
        self.assertEqual(self.b.param1, self.a.param1)

    def test_change_of_defaults_not_equal(self):
        self.assertNotEqual(self.b.param1, self.a_changed.param1)

    def tested_chained_inheritance(self):
        self.assertEqual(self.c.param2, self.b.param2)
        self.assertEqual(self.c.param1, self.a.param1)
        self.assertEqual(self.c.param1, self.b.param1)

    def test_overwriting_defaults(self):
        self.assertEqual(self.d.param2, self.b.param2)
        self.assertNotEqual(self.d.param1, self.b.param1)
        self.assertNotEqual(self.d.param1, self.a.param1)
        self.assertEqual(self.d.param1, "class D overwriting class A's default")

    def test_multiple_inheritance(self):
        self.assertEqual(self.e.param1, self.a.param1)
        self.assertEqual(self.e.param1, self.b.param1)
        self.assertEqual(self.e.param2, self.b.param2)

    def test_stacked_inheritance(self):
        self.assertEqual(self.e_stacked.param1, self.a.param1)
        self.assertEqual(self.e_stacked.param1, self.b.param1)
        self.assertEqual(self.e_stacked.param2, self.b.param2)

    def test_empty_inheritance(self):
        with self.assertRaises(TypeError):
            @inherits()
            class shouldfail(luigi.Step):
                pass

    def test_removing_parameter(self):
        self.assertFalse("param1" in dict(self.d_null.get_params()).keys())

    def test_wrapper_preserve_attributes(self):
        self.assertEqual(B.__name__, 'B')


class F(luigi.Step):
    param1 = luigi.Parameter("A parameter on a base step, that will be required later.")


@inherits(F)
class G(luigi.Step):
    param2 = luigi.Parameter("A separate parameter that doesn't affect 'F'")

    def requires(self):
        return F(**common_params(self, F))


@inherits(G)
class H(luigi.Step):
    param2 = luigi.Parameter("OVERWRITING")

    def requires(self):
        return G(**common_params(self, G))


@inherits(G)
class H_null(luigi.Step):
    param2 = None

    def requires(self):
        special_param2 = str(datetime.datetime.now())
        return G(param2=special_param2, **common_params(self, G))


@inherits(G)
class I_step(luigi.Step):

    def requires(self):
        return F(**common_params(self, F))


class J(luigi.Step):
    param1 = luigi.Parameter()  # something required, with no default


@inherits(J)
class K_shouldnotinstantiate(luigi.Step):
    param2 = luigi.Parameter("A K-specific parameter")


@inherits(J)
class K_shouldfail(luigi.Step):
    param1 = None
    param2 = luigi.Parameter("A K-specific parameter")

    def requires(self):
        return J(**common_params(self, J))


@inherits(J)
class K_shouldsucceed(luigi.Step):
    param1 = None
    param2 = luigi.Parameter("A K-specific parameter")

    def requires(self):
        return J(param1="Required parameter", **common_params(self, J))


@inherits(J)
class K_wrongparamsorder(luigi.Step):
    param1 = None
    param2 = luigi.Parameter("A K-specific parameter")

    def requires(self):
        return J(param1="Required parameter", **common_params(J, self))


class RequiresTest(unittest.TestCase):

    def setUp(self):
        self.f = F()
        self.g = G()
        self.g_changed = G(param1="changing the default")
        self.h = H()
        self.h_null = H_null()
        self.i = I_step()
        self.k_shouldfail = K_shouldfail()
        self.k_shouldsucceed = K_shouldsucceed()
        self.k_wrongparamsorder = K_wrongparamsorder()

    def test_inherits(self):
        self.assertEqual(self.f.param1, self.g.param1)
        self.assertEqual(self.f.param1, self.g.requires().param1)

    def test_change_of_defaults(self):
        self.assertNotEqual(self.f.param1, self.g_changed.param1)
        self.assertNotEqual(self.g.param1, self.g_changed.param1)
        self.assertNotEqual(self.f.param1, self.g_changed.requires().param1)

    def test_overwriting_parameter(self):
        self.h.requires()
        self.assertNotEqual(self.h.param2, self.g.param2)
        self.assertEqual(self.h.param2, self.h.requires().param2)
        self.assertEqual(self.h.param2, "OVERWRITING")

    def test_skipping_one_inheritance(self):
        self.assertEqual(self.i.requires().param1, self.f.param1)

    def test_removing_parameter(self):
        self.assertNotEqual(self.h_null.requires().param2, self.g.param2)

    def test_not_setting_required_parameter(self):
        self.assertRaises(MissingParameterException, self.k_shouldfail.requires)

    def test_setting_required_parameters(self):
        self.k_shouldsucceed.requires()

    def test_should_not_instantiate(self):
        self.assertRaises(MissingParameterException, K_shouldnotinstantiate)

    def test_resuscitation(self):
        k = K_shouldnotinstantiate(param1='hello')
        k.requires()

    def test_wrong_common_params_order(self):
        self.assertRaises(TypeError, self.k_wrongparamsorder.requires)


class V(luigi.Step):
    n = luigi.IntParameter(default=42)


@inherits(V)
class W(luigi.Step):

    def requires(self):
        return self.clone_parent()


@requires(V)
class W2(luigi.Step):
    pass


@requires(V)
class W3(luigi.Step):
    n = luigi.IntParameter(default=43)


class X(luigi.Step):
    m = luigi.IntParameter(default=56)


@requires(V, X)
class Y(luigi.Step):
    pass


class CloneParentTest(unittest.TestCase):

    def test_clone_parent(self):
        w = W()
        v = V()
        self.assertEqual(w.requires(), v)
        self.assertEqual(w.n, 42)

    def test_requires(self):
        w2 = W2()
        v = V()
        self.assertEqual(w2.requires(), v)
        self.assertEqual(w2.n, 42)

    def test_requires_override_default(self):
        w3 = W3()
        v = V()
        self.assertNotEqual(w3.requires(), v)
        self.assertEqual(w3.n, 43)
        self.assertEqual(w3.requires().n, 43)

    def test_multiple_requires(self):
        y = Y()
        v = V()
        x = X()
        self.assertEqual(y.requires()[0], v)
        self.assertEqual(y.requires()[1], x)

    def test_empty_requires(self):
        with self.assertRaises(TypeError):
            @requires()
            class shouldfail(luigi.Step):
                pass

    def test_names(self):
        # Just make sure the decorators retain the original class names
        v = V()
        self.assertEqual(str(v), 'V(n=42)')
        self.assertEqual(v.__class__.__name__, 'V')


class P(luigi.Step):
    date = luigi.DateParameter()

    def output(self):
        return MockTarget(self.date.strftime('/tmp/data-%Y-%m-%d.txt'))

    def run(self):
        f = self.output().open('w')
        print('hello, world', file=f)
        f.close()


@copies(P)
class PCopy(luigi.Step):

    def output(self):
        return MockTarget(self.date.strftime('/tmp/copy-data-%Y-%m-%d.txt'))


class CopyTest(unittest.TestCase):

    def test_copy(self):
        luigi.build([PCopy(date=datetime.date(2012, 1, 1))], local_scheduler=True)
        self.assertEqual(MockTarget.fs.get_data('/tmp/data-2012-01-01.txt'), b'hello, world\n')
        self.assertEqual(MockTarget.fs.get_data('/tmp/copy-data-2012-01-01.txt'), b'hello, world\n')


class PickleTest(unittest.TestCase):

    def test_pickle(self):
        # similar to CopyTest.test_copy
        p = PCopy(date=datetime.date(2013, 1, 1))
        p_pickled = pickle.dumps(p)
        p = pickle.loads(p_pickled)

        luigi.build([p], local_scheduler=True)
        self.assertEqual(MockTarget.fs.get_data('/tmp/data-2013-01-01.txt'), b'hello, world\n')
        self.assertEqual(MockTarget.fs.get_data('/tmp/copy-data-2013-01-01.txt'), b'hello, world\n')


class Substep(luigi.Step):
    k = luigi.IntParameter()

    def f(self, x):
        return x ** self.k


@delegates
class SubstepDelegator(luigi.Step):

    def substeps(self):
        return [Substep(1), Substep(2)]

    def run(self):
        self.s = 0
        for t in self.substeps():
            self.s += t.f(42)


class SubstepTest(unittest.TestCase):

    def test_substeps(self):
        sd = SubstepDelegator()
        luigi.build([sd], local_scheduler=True)
        self.assertEqual(sd.s, 42 * (1 + 42))

    def test_forgot_substeps(self):
        def trigger_failure():
            @delegates
            class SubstepDelegatorBroken(luigi.Step):
                pass

        self.assertRaises(AttributeError, trigger_failure)

    def test_cmdline(self):
        # Exposes issue where wrapped steps are registered twice under
        # the same name
        from luigi.step import Register
        self.assertEqual(Register.get_step_cls('SubstepDelegator'), SubstepDelegator)
