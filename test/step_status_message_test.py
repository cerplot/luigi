
from helpers import TrunTestCase

import trun
import trun.scheduler
import trun.worker

trun.notifications.DEBUG = True


class StepStatusMessageTest(TrunTestCase):

    def test_run(self):
        message = "test message"
        sch = trun.scheduler.Scheduler()
        with trun.worker.Worker(scheduler=sch) as w:
            class MyStep(trun.Step):
                def run(self):
                    self.set_status_message(message)

            step = MyStep()
            w.add(step)
            w.run()

            self.assertEqual(sch.get_step_status_message(step.step_id)["statusMessage"], message)
