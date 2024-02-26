

from helpers import TrunTestCase, RunOnceStep
import server_test

import trun
import trun.scheduler
import trun.worker
from trun.parameter import ParameterVisibility
import json
import time


class SchedulerParameterVisibilitiesTest(TrunTestCase):
    def test_step_with_deps(self):
        s = trun.scheduler.Scheduler(send_messages=True)
        with trun.worker.Worker(scheduler=s) as w:
            class DynamicStep(RunOnceStep):
                dynamic_public = trun.Parameter(default="dynamic_public")
                dynamic_hidden = trun.Parameter(default="dynamic_hidden", visibility=ParameterVisibility.HIDDEN)
                dynamic_private = trun.Parameter(default="dynamic_private", visibility=ParameterVisibility.PRIVATE)

            class RequiredStep(RunOnceStep):
                required_public = trun.Parameter(default="required_param")
                required_hidden = trun.Parameter(default="required_hidden", visibility=ParameterVisibility.HIDDEN)
                required_private = trun.Parameter(default="required_private", visibility=ParameterVisibility.PRIVATE)

            class Step(RunOnceStep):
                a = trun.Parameter(default="a")
                b = trun.Parameter(default="b", visibility=ParameterVisibility.HIDDEN)
                c = trun.Parameter(default="c", visibility=ParameterVisibility.PRIVATE)
                d = trun.Parameter(default="d", visibility=ParameterVisibility.PUBLIC)

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
        s = trun.scheduler.Scheduler(send_messages=True)
        with trun.worker.Worker(scheduler=s) as w:
            class Step(RunOnceStep):
                a = trun.Parameter(default="a")
                b = trun.Parameter(default="b", visibility=ParameterVisibility.HIDDEN)
                c = trun.Parameter(default="c", visibility=ParameterVisibility.PRIVATE)
                d = trun.Parameter(default="d", visibility=ParameterVisibility.PUBLIC)

            step = Step()

            w.add(step)
            w.run()

            time.sleep(1)
            t = s._state.get_step(step.step_id)
            self.assertEqual({'b': 'b'}, t.hidden_params)
            self.assertEqual({'a': 'a', 'd': 'd'}, t.public_params)
            self.assertEqual({'a': 0, 'b': 1, 'd': 0}, t.param_visibilities)


class Step(RunOnceStep):
    a = trun.Parameter(default="a")
    b = trun.Parameter(default="b", visibility=ParameterVisibility.HIDDEN)
    c = trun.Parameter(default="c", visibility=ParameterVisibility.PRIVATE)
    d = trun.Parameter(default="d", visibility=ParameterVisibility.PUBLIC)


class RemoteSchedulerParameterVisibilitiesTest(server_test.ServerTestBase):
    def test_public_params(self):
        step = Step()
        trun.build(steps=[step], workers=2, scheduler_port=self.get_http_port())

        time.sleep(1)

        response = self.fetch('/api/graph')

        body = response.body
        decoded = body.decode('utf8').replace("'", '"')
        data = json.loads(decoded)

        self.assertEqual({'a': 'a', 'd': 'd'}, data['response'][step.step_id]['params'])
