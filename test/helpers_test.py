
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
