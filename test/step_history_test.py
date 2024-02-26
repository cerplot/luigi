
from helpers import TrunTestCase

import trun
import trun.scheduler
import trun.step_history
import trun.worker

trun.notifications.DEBUG = True


class SimpleStepHistory(trun.step_history.StepHistory):

    def __init__(self):
        self.actions = []

    def step_scheduled(self, step):
        self.actions.append(('scheduled', step.id))

    def step_finished(self, step, successful):
        self.actions.append(('finished', step.id))

    def step_started(self, step, worker_host):
        self.actions.append(('started', step.id))


class StepHistoryTest(TrunTestCase):

    def test_run(self):
        th = SimpleStepHistory()
        sch = trun.scheduler.Scheduler(step_history_impl=th)
        with trun.worker.Worker(scheduler=sch) as w:
            class MyStep(trun.Step):
                pass

            step = MyStep()
            w.add(step)
            w.run()

            self.assertEqual(th.actions, [
                ('scheduled', step.step_id),
                ('started', step.step_id),
                ('finished', step.step_id)
            ])
