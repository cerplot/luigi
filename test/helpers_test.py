# -*- coding: utf-8 -*-
#
# Copyright 2012-2016 Spotify AB
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
import trun
import trun.date_interval
import trun.interface
import trun.notifications
from helpers import TrunTestCase, RunOnceStep


class TrunTestCaseTest(TrunTestCase):

    def test_1(self):
        class MyClass(trun.Step):
            pass

        self.assertTrue(self.run_locally(['MyClass']))

    def test_2(self):
        class MyClass(trun.Step):
            pass

        self.assertTrue(self.run_locally(['MyClass']))


class RunOnceStepTest(TrunTestCase):

    def test_complete_behavior(self):
        """
        Verify that RunOnceStep works as expected.

        This step will fail if it is a normal ``trun.Step``, because
        RequiringStep will not run (missing dependency at runtime).
        """
        class MyStep(RunOnceStep):
            pass

        class RequiringStep(trun.Step):
            counter = 0

            def requires(self):
                yield MyStep()

            def run(self):
                RequiringStep.counter += 1

        self.run_locally(['RequiringStep'])
        self.assertEqual(1, RequiringStep.counter)
