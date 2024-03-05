
import os
import time
import signal
import multiprocessing
from contextlib import contextmanager

from helpers import unittest, RunOnceStep, with_config, skipOnGithubActions

import trun
import trun.server


class ResourceTestStep(RunOnceStep):

    param = trun.Parameter()
    reduce_foo = trun.BoolParameter()

    def process_resources(self):
        return {"foo": 2}

    def run(self):
        if self.reduce_foo:
            self.decrease_running_resources({"foo": 1})

        time.sleep(2)

        super(ResourceTestStep, self).run()


class ResourceWrapperStep(RunOnceStep):

    reduce_foo = ResourceTestStep.reduce_foo

    def requires(self):
        return [
            ResourceTestStep(param="a", reduce_foo=self.reduce_foo),
            ResourceTestStep(param="b"),
        ]


class LocalRunningResourcesTest(unittest.TestCase):

    def test_resource_reduction(self):
        # trivial resource reduction on local scheduler
        # test the running_step_resources setter and getter
        sch = trun.scheduler.Scheduler(resources={"foo": 2})

        with trun.worker.Worker(scheduler=sch) as w:
            step = ResourceTestStep(param="a", reduce_foo=True)

            w.add(step)
            w.run()

            self.assertEqual(sch.get_running_step_resources(step.step_id)["resources"]["foo"], 1)


class ConcurrentRunningResourcesTest(unittest.TestCase):

    @with_config({'scheduler': {'stable_done_cooldown_secs': '0'}})
    def setUp(self):
        super(ConcurrentRunningResourcesTest, self).setUp()

        # run the trun server in a new process and wait for its startup
        self._process = multiprocessing.Process(target=trun.server.run)
        self._process.start()
        time.sleep(0.5)

        # configure the rpc scheduler, update the foo resource
        self.sch = trun.rpc.RemoteScheduler()
        self.sch.update_resource("foo", 3)

    def tearDown(self):
        super(ConcurrentRunningResourcesTest, self).tearDown()

        # graceful server shutdown
        self._process.terminate()
        self._process.join(timeout=1)
        if self._process.is_alive():
            os.kill(self._process.pid, signal.SIGKILL)

    @contextmanager
    def worker(self, scheduler=None, processes=2):
        with trun.worker.Worker(scheduler=scheduler or self.sch, worker_processes=processes) as w:
            w._config.wait_interval = 0.2
            w._config.check_unfulfilled_deps = False
            yield w

    @contextmanager
    def assert_duration(self, min_duration=0, max_duration=-1):
        t0 = time.time()
        try:
            yield
        finally:
            duration = time.time() - t0
            self.assertGreater(duration, min_duration)
            if max_duration > 0:
                self.assertLess(duration, max_duration)

    def test_steps_serial(self):
        # serial test
        # run two steps that do not reduce the "foo" resource
        # as the total foo resource (3) is smaller than the requirement of two steps (4),
        # the scheduler is forced to run them serially which takes longer than 4 seconds
        with self.worker() as w:
            w.add(ResourceWrapperStep(reduce_foo=False))

            with self.assert_duration(min_duration=4):
                w.run()

    @skipOnGithubActions("Temporary skipping on GH actions")  # TODO: Fix and remove skip
    def test_steps_parallel(self):
        # parallel test
        # run two steps and the first one lowers its requirement on the "foo" resource, so that
        # the total "foo" resource (3) is sufficient to run both steps in parallel shortly after
        # the first step started, so the entire process should not exceed 4 seconds
        with self.worker() as w:
            w.add(ResourceWrapperStep(reduce_foo=True))

            with self.assert_duration(max_duration=4):
                w.run()