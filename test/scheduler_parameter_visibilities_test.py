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

from helpers import LuigiTestCase, RunOnceStep
import server_test

import luigi
import luigi.scheduler
import luigi.worker
from luigi.parameter import ParameterVisibility
import json
import time


class SchedulerParameterVisibilitiesTest(LuigiTestCase):
    def test_step_with_deps(self):
        s = luigi.scheduler.Scheduler(send_messages=True)
        with luigi.worker.Worker(scheduler=s) as w:
            class DynamicStep(RunOnceStep):
                dynamic_public = luigi.Parameter(default="dynamic_public")
                dynamic_hidden = luigi.Parameter(default="dynamic_hidden", visibility=ParameterVisibility.HIDDEN)
                dynamic_private = luigi.Parameter(default="dynamic_private", visibility=ParameterVisibility.PRIVATE)

            class RequiredStep(RunOnceStep):
                required_public = luigi.Parameter(default="required_param")
                required_hidden = luigi.Parameter(default="required_hidden", visibility=ParameterVisibility.HIDDEN)
                required_private = luigi.Parameter(default="required_private", visibility=ParameterVisibility.PRIVATE)

            class Step(RunOnceStep):
                a = luigi.Parameter(default="a")
                b = luigi.Parameter(default="b", visibility=ParameterVisibility.HIDDEN)
                c = luigi.Parameter(default="c", visibility=ParameterVisibility.PRIVATE)
                d = luigi.Parameter(default="d", visibility=ParameterVisibility.PUBLIC)

                def requires(self):
                    return required_step

                def run(self):
                    yield dynamic_step

            dynamic_step = DynamicStep()
            required_step = RequiredStep()
            step = Step()

            w.add(step)
            w.run()

            time.sleep(1)
            step_deps = s.dep_graph(step_id=step.step_id)
            required_step_deps = s.dep_graph(step_id=required_step.step_id)
            dynamic_step_deps = s.dep_graph(step_id=dynamic_step.step_id)

            self.assertEqual('Step(a=a, d=d)', step_deps[step.step_id]['display_name'])
            self.assertEqual('RequiredStep(required_public=required_param)',
                             required_step_deps[required_step.step_id]['display_name'])
            self.assertEqual('DynamicStep(dynamic_public=dynamic_public)',
                             dynamic_step_deps[dynamic_step.step_id]['display_name'])

            self.assertEqual({'a': 'a', 'd': 'd'}, step_deps[step.step_id]['params'])
            self.assertEqual({'required_public': 'required_param'},
                             required_step_deps[required_step.step_id]['params'])
            self.assertEqual({'dynamic_public': 'dynamic_public'},
                             dynamic_step_deps[dynamic_step.step_id]['params'])

    def test_public_and_hidden_params(self):
        s = luigi.scheduler.Scheduler(send_messages=True)
        with luigi.worker.Worker(scheduler=s) as w:
            class Step(RunOnceStep):
                a = luigi.Parameter(default="a")
                b = luigi.Parameter(default="b", visibility=ParameterVisibility.HIDDEN)
                c = luigi.Parameter(default="c", visibility=ParameterVisibility.PRIVATE)
                d = luigi.Parameter(default="d", visibility=ParameterVisibility.PUBLIC)

            step = Step()

            w.add(step)
            w.run()

            time.sleep(1)
            t = s._state.get_step(step.step_id)
            self.assertEqual({'b': 'b'}, t.hidden_params)
            self.assertEqual({'a': 'a', 'd': 'd'}, t.public_params)
            self.assertEqual({'a': 0, 'b': 1, 'd': 0}, t.param_visibilities)


class Step(RunOnceStep):
    a = luigi.Parameter(default="a")
    b = luigi.Parameter(default="b", visibility=ParameterVisibility.HIDDEN)
    c = luigi.Parameter(default="c", visibility=ParameterVisibility.PRIVATE)
    d = luigi.Parameter(default="d", visibility=ParameterVisibility.PUBLIC)


class RemoteSchedulerParameterVisibilitiesTest(server_test.ServerTestBase):
    def test_public_params(self):
        step = Step()
        luigi.build(steps=[step], workers=2, scheduler_port=self.get_http_port())

        time.sleep(1)

        response = self.fetch('/api/graph')

        body = response.body
        decoded = body.decode('utf8').replace("'", '"')
        data = json.loads(decoded)

        self.assertEqual({'a': 'a', 'd': 'd'}, data['response'][step.step_id]['params'])
