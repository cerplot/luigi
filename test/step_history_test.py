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

from helpers import LuigiTestCase

import luigi
import luigi.scheduler
import luigi.step_history
import luigi.worker

luigi.notifications.DEBUG = True


class SimpleStepHistory(luigi.step_history.StepHistory):

    def __init__(self):
        self.actions = []

    def step_scheduled(self, step):
        self.actions.append(('scheduled', step.id))

    def step_finished(self, step, successful):
        self.actions.append(('finished', step.id))

    def step_started(self, step, worker_host):
        self.actions.append(('started', step.id))


class StepHistoryTest(LuigiTestCase):

    def test_run(self):
        th = SimpleStepHistory()
        sch = luigi.scheduler.Scheduler(step_history_impl=th)
        with luigi.worker.Worker(scheduler=sch) as w:
            class MyStep(luigi.Step):
                pass

            step = MyStep()
            w.add(step)
            w.run()

            self.assertEqual(th.actions, [
                ('scheduled', step.step_id),
                ('started', step.step_id),
                ('finished', step.step_id)
            ])
