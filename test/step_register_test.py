# -*- coding: utf-8 -*-
#
# Copyright 2017 VNG Corporation
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
from helpers import TrunTestCase

import trun
from trun.step_register import (Register,
                                 StepClassNotFoundException,
                                 StepClassAmbigiousException,
                                 )


class StepRegisterTest(TrunTestCase):

    def test_externalize_stepclass(self):
        with self.assertRaises(StepClassNotFoundException):
            Register.get_step_cls('scooby.Doo')

        class Step1(trun.Step):
            @classmethod
            def get_step_family(cls):
                return "scooby.Doo"

        self.assertEqual(Step1, Register.get_step_cls('scooby.Doo'))

        class Step2(trun.Step):
            @classmethod
            def get_step_family(cls):
                return "scooby.Doo"

        with self.assertRaises(StepClassAmbigiousException):
            Register.get_step_cls('scooby.Doo')

        class Step3(trun.Step):
            @classmethod
            def get_step_family(cls):
                return "scooby.Doo"

        # There previously was a rare bug where the third installed class could
        # "undo" class ambiguity.
        with self.assertRaises(StepClassAmbigiousException):
            Register.get_step_cls('scooby.Doo')
