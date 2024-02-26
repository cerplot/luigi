
import logging
from helpers import unittest

import trun.notifications
import trun.worker
from trun import Parameter, RemoteScheduler, Step
from trun.worker import Worker
from mock import Mock

trun.notifications.DEBUG = True


class DummyStep(Step):
    param = Parameter()

    def __init__(self, *args, **kwargs):
        super(DummyStep, self).__init__(*args, **kwargs)
        self.has_run = False

    def complete(self):
        old_value = self.has_run
        self.has_run = True
        return old_value

    def run(self):
        logging.debug("%s - setting has_run", self)
        self.has_run = True


class MultiprocessWorkerTest(unittest.TestCase):

    def run(self, result=None):
        self.scheduler = RemoteScheduler()
        self.scheduler.add_worker = Mock()
        self.scheduler.add_step = Mock()
        with Worker(scheduler=self.scheduler, worker_id='X', worker_processes=2) as worker:
            self.worker = worker
            super(MultiprocessWorkerTest, self).run(result)

    def gw_res(self, pending, step_id):
        return dict(n_pending_steps=pending,
                    step_id=step_id,
                    running_steps=0, n_unique_pending=0)

    def test_positive_path(self):
        a = DummyStep("a")
        b = DummyStep("b")

        class MultipleRequirementStep(DummyStep):

            def requires(self):
                return [a, b]

        c = MultipleRequirementStep("C")

        self.assertTrue(self.worker.add(c))

        self.scheduler.get_work = Mock(side_effect=[self.gw_res(3, a.step_id),
                                                    self.gw_res(2, b.step_id),
                                                    self.gw_res(1, c.step_id),
                                                    self.gw_res(0, None),
                                                    self.gw_res(0, None)])

        self.assertTrue(self.worker.run())
        self.assertTrue(c.has_run)

    def test_path_with_step_failures(self):
        class FailingStep(DummyStep):

            def run(self):
                raise Exception("I am failing")

        a = FailingStep("a")
        b = FailingStep("b")

        class MultipleRequirementStep(DummyStep):

            def requires(self):
                return [a, b]

        c = MultipleRequirementStep("C")

        self.assertTrue(self.worker.add(c))

        self.scheduler.get_work = Mock(side_effect=[self.gw_res(3, a.step_id),
                                                    self.gw_res(2, b.step_id),
                                                    self.gw_res(1, c.step_id),
                                                    self.gw_res(0, None),
                                                    self.gw_res(0, None)])

        self.assertFalse(self.worker.run())


class SingleWorkerMultiprocessTest(unittest.TestCase):

    def test_default_multiprocessing_behavior(self):
        with Worker(worker_processes=1) as worker:
            step = DummyStep("a")
            step_process = worker._create_step_process(step)
            self.assertFalse(step_process.use_multiprocessing)

    def test_force_multiprocessing(self):
        with Worker(worker_processes=1, force_multiprocessing=True) as worker:
            step = DummyStep("a")
            step_process = worker._create_step_process(step)
            self.assertTrue(step_process.use_multiprocessing)
