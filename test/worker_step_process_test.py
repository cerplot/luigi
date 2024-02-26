
from helpers import TrunTestCase, temporary_unloaded_module
import trun
from trun.worker import Worker
import multiprocessing


class ContextManagedStepProcessTest(TrunTestCase):

    def _test_context_manager(self, force_multiprocessing):
        CONTEXT_MANAGER_MODULE = b'''
class MyContextManager:
    def __init__(self, step_process):
        self.step = step_process.step
    def __enter__(self):
        assert not self.step.run_event.is_set(), "the step should not have run yet"
        self.step.enter_event.set()
        return self
    def __exit__(self, exc_type=None, exc_value=None, traceback=None):
        assert self.step.run_event.is_set(), "the step should have run"
        self.step.exit_event.set()
'''

        class DummyEventRecordingStep(trun.Step):
            def __init__(self, *args, **kwargs):
                self.enter_event = multiprocessing.Event()
                self.exit_event = multiprocessing.Event()
                self.run_event = multiprocessing.Event()
                super(DummyEventRecordingStep, self).__init__(*args, **kwargs)

            def run(self):
                assert self.enter_event.is_set(), "the context manager should have been entered"
                assert not self.exit_event.is_set(), "the context manager should not have been exited yet"
                assert not self.run_event.is_set(), "the step should not have run yet"
                self.run_event.set()

            def complete(self):
                return self.run_event.is_set()

        with temporary_unloaded_module(CONTEXT_MANAGER_MODULE) as module_name:
            t = DummyEventRecordingStep()
            w = Worker(step_process_context=module_name + '.MyContextManager',
                       force_multiprocessing=force_multiprocessing)
            w.add(t)
            self.assertTrue(w.run())
            self.assertTrue(t.complete())
            self.assertTrue(t.enter_event.is_set())
            self.assertTrue(t.exit_event.is_set())

    def test_context_manager_without_multiprocessing(self):
        self._test_context_manager(False)

    def test_context_manager_with_multiprocessing(self):
        self._test_context_manager(True)
