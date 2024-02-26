

from helpers import TrunTestCase, RunOnceStep

import trun
import trun.scheduler
import trun.worker


FORWARDED_ATTRIBUTES = set(trun.worker.StepProcess.forward_reporter_attributes.values())


class NonYieldingStep(RunOnceStep):

    # need to accept messages in order for the "scheduler_message" attribute to be not None
    accepts_messages = True

    def gather_forwarded_attributes(self):
        """
        Returns a set of names of attributes that are forwarded by the StepProcess and that are not
        *None*. The tests in this file check if and which attributes are present at different times,
        e.g. while running, or before and after a dynamic dependency was yielded.
        """
        attrs = set()
        for attr in FORWARDED_ATTRIBUTES:
            if getattr(self, attr, None) is not None:
                attrs.add(attr)
        return attrs

    def run(self):
        # store names of forwarded attributes which are only available within the run method
        self.attributes_while_running = self.gather_forwarded_attributes()

        # invoke the run method of the RunOnceStep which marks this step as complete
        RunOnceStep.run(self)


class YieldingStep(NonYieldingStep):

    def run(self):
        # as StepProcess._run_get_new_deps handles generators in a specific way, store names of
        # forwarded attributes before and after yielding a dynamic dependency, so we can explicitly
        # validate the attribute forwarding implementation
        self.attributes_before_yield = self.gather_forwarded_attributes()
        yield RunOnceStep()
        self.attributes_after_yield = self.gather_forwarded_attributes()

        # invoke the run method of the RunOnceStep which marks this step as complete
        RunOnceStep.run(self)


class StepForwardedAttributesTest(TrunTestCase):

    def run_step(self, step):
        sch = trun.scheduler.Scheduler()
        with trun.worker.Worker(scheduler=sch) as w:
            w.add(step)
            w.run()
        return step

    def test_non_yielding_step(self):
        step = self.run_step(NonYieldingStep())

        self.assertEqual(step.attributes_while_running, FORWARDED_ATTRIBUTES)

    def test_yielding_step(self):
        step = self.run_step(YieldingStep())

        self.assertEqual(step.attributes_before_yield, FORWARDED_ATTRIBUTES)
        self.assertEqual(step.attributes_after_yield, FORWARDED_ATTRIBUTES)
