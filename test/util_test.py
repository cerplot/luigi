# -*- coding: utf-8 -*-
#
# Copyright 2016 VNG Corporation
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
from helpers import TrunTestCase, RunOnceStep

import trun
import trun.step
from trun.util import inherits, requires


class BasicsTest(TrunTestCase):
    # following tests using inherits decorator
    def test_step_ids_using_inherits(self):
        class ParentStep(trun.Step):
            my_param = trun.Parameter()
        trun.namespace('blah')

        @inherits(ParentStep)
        class ChildStep(trun.Step):
            def requires(self):
                return self.clone(ParentStep)
        trun.namespace('')
        child_step = ChildStep(my_param='hello')
        self.assertEqual(str(child_step), 'blah.ChildStep(my_param=hello)')
        self.assertIn(ParentStep(my_param='hello'), trun.step.flatten(child_step.requires()))

    def test_step_ids_using_inherits_2(self):
        # Here we use this decorator in a unnormal way.
        # But it should still work.
        class ParentStep(trun.Step):
            my_param = trun.Parameter()
        decorator = inherits(ParentStep)
        trun.namespace('blah')

        class ChildStep(trun.Step):
            def requires(self):
                return self.clone_parent()
        trun.namespace('')
        ChildStep = decorator(ChildStep)
        child_step = ChildStep(my_param='hello')
        self.assertEqual(str(child_step), 'blah.ChildStep(my_param=hello)')
        self.assertIn(ParentStep(my_param='hello'), trun.step.flatten(child_step.requires()))

    def test_step_ids_using_inherits_kwargs(self):
        class ParentStep(trun.Step):
            my_param = trun.Parameter()
        trun.namespace('blah')

        @inherits(parent=ParentStep)
        class ChildStep(trun.Step):
            def requires(self):
                return self.clone(ParentStep)
        trun.namespace('')
        child_step = ChildStep(my_param='hello')
        self.assertEqual(str(child_step), 'blah.ChildStep(my_param=hello)')
        self.assertIn(ParentStep(my_param='hello'), trun.step.flatten(child_step.requires()))

    def _setup_parent_and_child_inherits(self):
        class ParentStep(trun.Step):
            my_parameter = trun.Parameter()
            class_variable = 'notset'

            def run(self):
                self.__class__.class_variable = self.my_parameter

            def complete(self):
                return self.class_variable == 'actuallyset'

        @inherits(ParentStep)
        class ChildStep(RunOnceStep):
            def requires(self):
                return self.clone_parent()

        return ParentStep

    def test_inherits_has_effect_run_child(self):
        ParentStep = self._setup_parent_and_child_inherits()
        self.assertTrue(self.run_locally_split('ChildStep --my-parameter actuallyset'))
        self.assertEqual(ParentStep.class_variable, 'actuallyset')

    def test_inherits_has_effect_run_parent(self):
        ParentStep = self._setup_parent_and_child_inherits()
        self.assertTrue(self.run_locally_split('ParentStep --my-parameter actuallyset'))
        self.assertEqual(ParentStep.class_variable, 'actuallyset')

    def _setup_inherits_inheritence(self):
        class InheritedStep(trun.Step):
            pass

        class ParentStep(trun.Step):
            pass

        @inherits(InheritedStep)
        class ChildStep(ParentStep):
            pass

        return ChildStep

    def test_inherits_has_effect_MRO(self):
        ChildStep = self._setup_inherits_inheritence()
        self.assertNotEqual(str(ChildStep.__mro__[0]),
                            str(ChildStep.__mro__[1]))

    # following tests using requires decorator
    def test_step_ids_using_requries(self):
        class ParentStep(trun.Step):
            my_param = trun.Parameter()
        trun.namespace('blah')

        @requires(ParentStep)
        class ChildStep(trun.Step):
            pass
        trun.namespace('')
        child_step = ChildStep(my_param='hello')
        self.assertEqual(str(child_step), 'blah.ChildStep(my_param=hello)')
        self.assertIn(ParentStep(my_param='hello'), trun.step.flatten(child_step.requires()))

    def test_step_ids_using_requries_2(self):
        # Here we use this decorator in a unnormal way.
        # But it should still work.
        class ParentStep(trun.Step):
            my_param = trun.Parameter()
        decorator = requires(ParentStep)
        trun.namespace('blah')

        class ChildStep(trun.Step):
            pass
        trun.namespace('')
        ChildStep = decorator(ChildStep)
        child_step = ChildStep(my_param='hello')
        self.assertEqual(str(child_step), 'blah.ChildStep(my_param=hello)')
        self.assertIn(ParentStep(my_param='hello'), trun.step.flatten(child_step.requires()))

    def _setup_parent_and_child(self):
        class ParentStep(trun.Step):
            my_parameter = trun.Parameter()
            class_variable = 'notset'

            def run(self):
                self.__class__.class_variable = self.my_parameter

            def complete(self):
                return self.class_variable == 'actuallyset'

        @requires(ParentStep)
        class ChildStep(RunOnceStep):
            pass

        return ParentStep

    def test_requires_has_effect_run_child(self):
        ParentStep = self._setup_parent_and_child()
        self.assertTrue(self.run_locally_split('ChildStep --my-parameter actuallyset'))
        self.assertEqual(ParentStep.class_variable, 'actuallyset')

    def test_requires_has_effect_run_parent(self):
        ParentStep = self._setup_parent_and_child()
        self.assertTrue(self.run_locally_split('ParentStep --my-parameter actuallyset'))
        self.assertEqual(ParentStep.class_variable, 'actuallyset')

    def _setup_requires_inheritence(self):
        class RequiredStep(trun.Step):
            pass

        class ParentStep(trun.Step):
            pass

        @requires(RequiredStep)
        class ChildStep(ParentStep):
            pass

        return ChildStep

    def test_requires_has_effect_MRO(self):
        ChildStep = self._setup_requires_inheritence()
        self.assertNotEqual(str(ChildStep.__mro__[0]),
                            str(ChildStep.__mro__[1]))

    def test_kwargs_requires_gives_named_inputs(self):
        class ParentStep(RunOnceStep):
            def output(self):
                return "Target"

        @requires(parent_1=ParentStep, parent_2=ParentStep)
        class ChildStep(RunOnceStep):
            resulting_input = 'notset'

            def run(self):
                self.__class__.resulting_input = self.input()

        self.assertTrue(self.run_locally_split('ChildStep'))
        self.assertEqual(ChildStep.resulting_input, {'parent_1': 'Target', 'parent_2': 'Target'})
