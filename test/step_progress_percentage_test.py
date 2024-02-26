

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
