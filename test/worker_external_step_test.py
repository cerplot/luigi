
import trun
from trun.local_target import LocalTarget
from trun.scheduler import Scheduler
import trun.server
import trun.worker
import trun.step
from mock import patch
from helpers import with_config, unittest
import os
import tempfile
import shutil


class TestExternalFileStep(trun.ExternalStep):
    """ Mocking steps is a pain, so touch a file instead """
    path = trun.Parameter()
    times_to_call = trun.IntParameter()

    def __init__(self, *args, **kwargs):
        super(TestExternalFileStep, self).__init__(*args, **kwargs)
        self.times_called = 0

    def complete(self):
        """
        Create the file we need after a number of preconfigured attempts
        """
        self.times_called += 1

        if self.times_called >= self.times_to_call:
            open(self.path, 'a').close()

        return os.path.exists(self.path)

    def output(self):
        return LocalTarget(path=self.path)


class TestStep(trun.Step):
    """
    Requires a single file dependency
    """
    tempdir = trun.Parameter()
    complete_after = trun.IntParameter()

    def __init__(self, *args, **kwargs):
        super(TestStep, self).__init__(*args, **kwargs)
        self.output_path = os.path.join(self.tempdir, "test.output")
        self.dep_path = os.path.join(self.tempdir, "test.dep")
        self.dependency = TestExternalFileStep(path=self.dep_path,
                                               times_to_call=self.complete_after)

    def requires(self):
        yield self.dependency

    def output(self):
        return LocalTarget(
            path=self.output_path)

    def run(self):
        open(self.output_path, 'a').close()


class WorkerExternalStepTest(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.mkdtemp(prefix='trun-test-')

    def tearDown(self):
        shutil.rmtree(self.tempdir)

    def _assert_complete(self, steps):
        for t in steps:
            self.assert_(t.complete())

    def _build(self, steps):
        with self._make_worker() as w:
            for t in steps:
                w.add(t)
            w.run()

    def _make_worker(self):
        self.scheduler = Scheduler(prune_on_get_work=True)
        return trun.worker.Worker(scheduler=self.scheduler, worker_processes=1)

    def test_external_dependency_already_complete(self):
        """
        Test that the test step completes when its dependency exists at the
        start of the execution.
        """
        test_step = TestStep(tempdir=self.tempdir, complete_after=1)
        trun.build([test_step], local_scheduler=True)

        assert os.path.exists(test_step.dep_path)
        assert os.path.exists(test_step.output_path)

        # complete() is called once per failure, twice per success
        assert test_step.dependency.times_called == 2

    @with_config({'worker': {'retry_external_steps': 'true'},
                  'scheduler': {'retry_delay': '0.0'}})
    def test_external_dependency_gets_rechecked(self):
        """
        Test that retry_external_steps re-checks external steps
        """
        assert trun.worker.worker().retry_external_steps is True

        test_step = TestStep(tempdir=self.tempdir, complete_after=10)
        self._build([test_step])

        assert os.path.exists(test_step.dep_path)
        assert os.path.exists(test_step.output_path)

        self.assertGreaterEqual(test_step.dependency.times_called, 10)

    @with_config({'worker': {'retry_external_steps': 'true',
                             'keep_alive': 'true',
                             'wait_interval': '0.00001'},
                  'scheduler': {'retry_delay': '0.01'}})
    def test_external_dependency_worker_is_patient(self):
        """
        Test that worker doesn't "give up" with keep_alive option

        Instead, it should sleep for random.uniform() seconds, then ask
        scheduler for work.
        """
        assert trun.worker.worker().retry_external_steps is True

        with patch('random.uniform', return_value=0.001):
            test_step = TestStep(tempdir=self.tempdir, complete_after=5)
            self._build([test_step])

        assert os.path.exists(test_step.dep_path)
        assert os.path.exists(test_step.output_path)

        self.assertGreaterEqual(test_step.dependency.times_called, 5)

    def test_external_dependency_bare(self):
        """
        Test ExternalStep without altering global settings.
        """
        assert trun.worker.worker().retry_external_steps is False

        test_step = TestStep(tempdir=self.tempdir, complete_after=5)

        scheduler = trun.scheduler.Scheduler(retry_delay=0.01,
                                              prune_on_get_work=True)
        with trun.worker.Worker(
                retry_external_steps=True, scheduler=scheduler,
                keep_alive=True, wait_interval=0.00001, wait_jitter=0) as w:
            w.add(test_step)
            w.run()

        assert os.path.exists(test_step.dep_path)
        assert os.path.exists(test_step.output_path)

        self.assertGreaterEqual(test_step.dependency.times_called, 5)

    @with_config({'worker': {'retry_external_steps': 'true', },
                  'scheduler': {'retry_delay': '0.0'}})
    def test_external_step_complete_but_missing_dep_at_runtime(self):
        """
        Test external step complete but has missing upstream dependency at
        runtime.

        Should not get "unfulfilled dependencies" error.
        """
        test_step = TestStep(tempdir=self.tempdir, complete_after=3)
        test_step.run = NotImplemented

        assert len(test_step.deps()) > 0

        # split up scheduling step and running to simulate runtime scenario
        with self._make_worker() as w:
            w.add(test_step)
            # touch output so test_step should be considered complete at runtime
            open(test_step.output_path, 'a').close()
            success = w.run()

        self.assertTrue(success)
        # upstream dependency output didn't exist at runtime
        self.assertFalse(os.path.exists(test_step.dep_path))
