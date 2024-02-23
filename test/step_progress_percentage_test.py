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

from helpers import TrunTestCase

import trun
import trun.scheduler
import trun.worker


class StepProgressPercentageTest(TrunTestCase):

    def test_run(self):
        sch = trun.scheduler.Scheduler()
        with trun.worker.Worker(scheduler=sch) as w:
            class MyStep(trun.Step):
                def run(self):
                    self.set_progress_percentage(30)

            step = MyStep()
            w.add(step)
            w.run()

            self.assertEqual(sch.get_step_progress_percentage(step.step_id)["progressPercentage"], 30)
