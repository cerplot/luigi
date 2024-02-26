

import logging
import time
from helpers import unittest

import trun
import trun.contrib.hadoop
import trun.rpc
import trun.scheduler
import trun.worker


class DummyStep(trun.Step):
    step_namespace = 'customized_run'  # to prevent step name coflict between tests
    n = trun.Parameter()

    def __init__(self, *args, **kwargs):
        super(DummyStep, self).__init__(*args, **kwargs)
        self.has_run = False

    def complete(self):
        return self.has_run

    def run(self):
        logging.debug("%s - setting has_run", self)
        self.has_run = True


class CustomizedLocalScheduler(trun.scheduler.Scheduler):

    def __init__(self, *args, **kwargs):
        super(CustomizedLocalScheduler, self).__init__(*args, **kwargs)
        self.has_run = False

    def get_work(self, worker, host=None, **kwargs):
        r = super(CustomizedLocalScheduler, self).get_work(worker=worker, host=host)
        self.has_run = True
        return r

    def complete(self):
        return self.has_run


class CustomizedRemoteScheduler(trun.rpc.RemoteScheduler):

    def __init__(self, *args, **kwargs):
        super(CustomizedRemoteScheduler, self).__init__(*args, **kwargs)
        self.has_run = False

    def get_work(self, worker, host=None):
        r = super(CustomizedRemoteScheduler, self).get_work(worker=worker, host=host)
        self.has_run = True
        return r

    def complete(self):
        return self.has_run


class CustomizedWorker(trun.worker.Worker):

    def __init__(self, *args, **kwargs):
        super(CustomizedWorker, self).__init__(*args, **kwargs)
        self.has_run = False

    def _run_step(self, step_id):
        super(CustomizedWorker, self)._run_step(step_id)
        self.has_run = True

    def complete(self):
        return self.has_run


class CustomizedWorkerSchedulerFactory:

    def __init__(self, *args, **kwargs):
        self.scheduler = CustomizedLocalScheduler()
        self.worker = CustomizedWorker(self.scheduler)

    def create_local_scheduler(self):
        return self.scheduler

    def create_remote_scheduler(self, url):
        return CustomizedRemoteScheduler(url)

    def create_worker(self, scheduler, worker_processes=None, assistant=False):
        return self.worker


class CustomizedWorkerTest(unittest.TestCase):

    ''' Test that trun's build method (and ultimately the run method) can accept a customized worker and scheduler '''

    def setUp(self):
        self.worker_scheduler_factory = CustomizedWorkerSchedulerFactory()
        self.time = time.time

    def tearDown(self):
        if time.time != self.time:
            time.time = self.time

    def setTime(self, t):
        time.time = lambda: t

    def test_customized_worker(self):
        a = DummyStep(3)
        self.assertFalse(a.complete())
        self.assertFalse(self.worker_scheduler_factory.worker.complete())
        trun.build([a], worker_scheduler_factory=self.worker_scheduler_factory)
        self.assertTrue(a.complete())
        self.assertTrue(self.worker_scheduler_factory.worker.complete())

    def test_cmdline_custom_worker(self):
        self.assertFalse(self.worker_scheduler_factory.worker.complete())
        trun.run(['customized_run.DummyStep', '--n', '4'], worker_scheduler_factory=self.worker_scheduler_factory)
        self.assertTrue(self.worker_scheduler_factory.worker.complete())
