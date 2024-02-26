
import sys

import trun
import trun.date_interval
import trun.notifications
from trun.interface import _WorkerSchedulerFactory
from trun.worker import Worker
from trun.interface import core
from trun.execution_summary import TrunStatusCode

from mock import Mock, patch, MagicMock
from helpers import TrunTestCase, with_config

trun.notifications.DEBUG = True


class InterfaceTest(TrunTestCase):

    def setUp(self):
        self.worker = Worker()

        self.worker_scheduler_factory = _WorkerSchedulerFactory()
        self.worker_scheduler_factory.create_worker = Mock(return_value=self.worker)
        self.worker_scheduler_factory.create_local_scheduler = Mock()
        super(InterfaceTest, self).setUp()

        class NoOpStep(trun.Step):
            param = trun.Parameter()

        self.step_a = NoOpStep("a")
        self.step_b = NoOpStep("b")

    def _create_summary_dict_with(self, updates={}):
        summary_dict = {
            'completed': set(),
            'already_done': set(),
            'ever_failed': set(),
            'failed': set(),
            'scheduling_error': set(),
            'still_pending_ext': set(),
            'still_pending_not_ext': set(),
            'run_by_other_worker': set(),
            'upstream_failure': set(),
            'upstream_missing_dependency': set(),
            'upstream_run_by_other_worker': set(),
            'upstream_scheduling_error': set(),
            'not_run': set()
        }
        summary_dict.update(updates)
        return summary_dict

    def _summary_dict_module_path():
        return 'trun.execution_summary._summary_dict'

    def test_interface_run_positive_path(self):
        self.worker.add = Mock(side_effect=[True, True])
        self.worker.run = Mock(return_value=True)
        self.assertTrue(self._run_interface())

    def test_interface_run_positive_path_with_detailed_summary_enabled(self):
        self.worker.add = Mock(side_effect=[True, True])
        self.worker.run = Mock(return_value=True)
        self.assertTrue(self._run_interface(detailed_summary=True).scheduling_succeeded)

    def test_interface_run_with_add_failure(self):
        self.worker.add = Mock(side_effect=[True, False])
        self.worker.run = Mock(return_value=True)
        self.assertFalse(self._run_interface())

    def test_interface_run_with_add_failure_with_detailed_summary_enabled(self):
        self.worker.add = Mock(side_effect=[True, False])
        self.worker.run = Mock(return_value=True)
        self.assertFalse(self._run_interface(detailed_summary=True).scheduling_succeeded)

    def test_interface_run_with_run_failure(self):
        self.worker.add = Mock(side_effect=[True, True])
        self.worker.run = Mock(return_value=False)
        self.assertFalse(self._run_interface())

    def test_interface_run_with_run_failure_with_detailed_summary_enabled(self):
        self.worker.add = Mock(side_effect=[True, True])
        self.worker.run = Mock(return_value=False)
        self.assertFalse(self._run_interface(detailed_summary=True).scheduling_succeeded)

    @patch(_summary_dict_module_path())
    def test_that_status_is_success(self, fake_summary_dict):
        # Nothing in failed steps so, should succeed
        fake_summary_dict.return_value = self._create_summary_dict_with()
        trun_run_result = self._run_interface(detailed_summary=True)
        self.assertEqual(trun_run_result.status, TrunStatusCode.SUCCESS)

    @patch(_summary_dict_module_path())
    def test_that_status_is_success_with_retry(self, fake_summary_dict):
        # Nothing in failed steps (only an entry in ever_failed) so, should succeed with retry
        fake_summary_dict.return_value = self._create_summary_dict_with({
            'ever_failed': [self.step_a]
        })
        trun_run_result = self._run_interface(detailed_summary=True)
        self.assertEqual(trun_run_result.status, TrunStatusCode.SUCCESS_WITH_RETRY)

    @patch(_summary_dict_module_path())
    def test_that_status_is_failed_when_there_is_one_failed_step(self, fake_summary_dict):
        # Should fail because a step failed
        fake_summary_dict.return_value = self._create_summary_dict_with({
            'ever_failed': [self.step_a],
            'failed': [self.step_a]
        })
        trun_run_result = self._run_interface(detailed_summary=True)
        self.assertEqual(trun_run_result.status, TrunStatusCode.FAILED)

    @patch(_summary_dict_module_path())
    def test_that_status_is_failed_with_scheduling_failure(self, fake_summary_dict):
        # Failed step and also a scheduling error
        fake_summary_dict.return_value = self._create_summary_dict_with({
            'ever_failed': [self.step_a],
            'failed': [self.step_a],
            'scheduling_error': [self.step_b]
        })
        trun_run_result = self._run_interface(detailed_summary=True)
        self.assertEqual(trun_run_result.status, TrunStatusCode.FAILED_AND_SCHEDULING_FAILED)

    @patch(_summary_dict_module_path())
    def test_that_status_is_scheduling_failed_with_one_scheduling_error(self, fake_summary_dict):
        # Scheduling error for at least one step
        fake_summary_dict.return_value = self._create_summary_dict_with({
            'scheduling_error': [self.step_b]
        })
        trun_run_result = self._run_interface(detailed_summary=True)
        self.assertEqual(trun_run_result.status, TrunStatusCode.SCHEDULING_FAILED)

    @patch(_summary_dict_module_path())
    def test_that_status_is_not_run_with_one_step_not_run(self, fake_summary_dict):
        # At least one of the steps was not run
        fake_summary_dict.return_value = self._create_summary_dict_with({
            'not_run': [self.step_a]
        })
        trun_run_result = self._run_interface(detailed_summary=True)
        self.assertEqual(trun_run_result.status, TrunStatusCode.NOT_RUN)

    @patch(_summary_dict_module_path())
    def test_that_status_is_missing_ext_with_one_step_with_missing_external_dependency(self, fake_summary_dict):
        # Missing external dependency for at least one step
        fake_summary_dict.return_value = self._create_summary_dict_with({
            'still_pending_ext': [self.step_a]
        })
        trun_run_result = self._run_interface(detailed_summary=True)
        self.assertEqual(trun_run_result.status, TrunStatusCode.MISSING_EXT)

    def test_stops_worker_on_add_exception(self):
        worker = MagicMock()
        self.worker_scheduler_factory.create_worker = Mock(return_value=worker)
        worker.add = Mock(side_effect=AttributeError)

        self.assertRaises(AttributeError, self._run_interface)
        self.assertTrue(worker.__exit__.called)

    def test_stops_worker_on_run_exception(self):
        worker = MagicMock()
        self.worker_scheduler_factory.create_worker = Mock(return_value=worker)
        worker.add = Mock(side_effect=[True, True])
        worker.run = Mock(side_effect=AttributeError)

        self.assertRaises(AttributeError, self._run_interface)
        self.assertTrue(worker.__exit__.called)

    def test_just_run_main_step_cls(self):
        class MyTestStep(trun.Step):
            pass

        class MyOtherTestStep(trun.Step):
            my_param = trun.Parameter()

        with patch.object(sys, 'argv', ['my_module.py', '--no-lock', '--local-scheduler']):
            trun.run(main_step_cls=MyTestStep)

        with patch.object(sys, 'argv', ['my_module.py', '--no-lock', '--my-param', 'my_value', '--local-scheduler']):
            trun.run(main_step_cls=MyOtherTestStep)

    def _run_interface(self, **env_params):
        return trun.interface.build(
                                    [self.step_a, self.step_b],
                                    worker_scheduler_factory=self.worker_scheduler_factory,
                                    **env_params)


class CoreConfigTest(TrunTestCase):

    @with_config({})
    def test_parallel_scheduling_processes_default(self):
        self.assertEquals(0, core().parallel_scheduling_processes)

    @with_config({'core': {'parallel-scheduling-processes': '1234'}})
    def test_parallel_scheduling_processes(self):
        from trun.interface import core
        self.assertEquals(1234, core().parallel_scheduling_processes)
