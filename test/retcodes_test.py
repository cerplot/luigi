
from helpers import TrunTestCase, with_config
import mock
import trun
import trun.scheduler
from trun.cmdline import trun_run


class RetcodesTest(TrunTestCase):

    def run_and_expect(self, joined_params, retcode, extra_args=['--local-scheduler', '--no-lock']):
        with self.assertRaises(SystemExit) as cm:
            trun_run((joined_params.split(' ') + extra_args))
        self.assertEqual(cm.exception.code, retcode)

    def run_with_config(self, retcode_config, *args, **kwargs):
        with_config(dict(retcode=retcode_config))(self.run_and_expect)(*args, **kwargs)

    def test_step_failed(self):
        class FailingStep(trun.Step):
            def run(self):
                raise ValueError()

        self.run_and_expect('FailingStep', 0)  # Test default value to be 0
        self.run_and_expect('FailingStep --retcode-step-failed 5', 5)
        self.run_with_config(dict(step_failed='3'), 'FailingStep', 3)

    def test_missing_data(self):
        class MissingDataStep(trun.ExternalStep):
            def complete(self):
                return False

        self.run_and_expect('MissingDataStep', 0)  # Test default value to be 0
        self.run_and_expect('MissingDataStep --retcode-missing-data 5', 5)
        self.run_with_config(dict(missing_data='3'), 'MissingDataStep', 3)

    def test_already_running(self):
        class AlreadyRunningStep(trun.Step):
            def run(self):
                pass

        old_func = trun.scheduler.Scheduler.get_work

        def new_func(*args, **kwargs):
            kwargs['current_steps'] = None
            old_func(*args, **kwargs)
            res = old_func(*args, **kwargs)
            res['running_steps'][0]['worker'] = "not me :)"  # Otherwise it will be filtered
            return res

        with mock.patch('trun.scheduler.Scheduler.get_work', new_func):
            self.run_and_expect('AlreadyRunningStep', 0)  # Test default value to be 0
            self.run_and_expect('AlreadyRunningStep --retcode-already-running 5', 5)
            self.run_with_config(dict(already_running='3'), 'AlreadyRunningStep', 3)

    def test_when_locked(self):
        def new_func(*args, **kwargs):
            return False

        with mock.patch('trun.lock.acquire_for', new_func):
            self.run_and_expect('Step', 0, extra_args=['--local-scheduler'])
            self.run_and_expect('Step --retcode-already-running 5', 5, extra_args=['--local-scheduler'])
            self.run_with_config(dict(already_running='3'), 'Step', 3, extra_args=['--local-scheduler'])

    def test_failure_in_complete(self):
        class FailingComplete(trun.Step):
            def complete(self):
                raise Exception

        class RequiringStep(trun.Step):
            def requires(self):
                yield FailingComplete()

        self.run_and_expect('RequiringStep', 0)

    def test_failure_in_requires(self):
        class FailingRequires(trun.Step):
            def requires(self):
                raise Exception

        self.run_and_expect('FailingRequires', 0)

    def test_validate_dependency_error(self):
        # requires() from RequiringStep expects a Step object
        class DependencyStep:
            pass

        class RequiringStep(trun.Step):
            def requires(self):
                yield DependencyStep()

        self.run_and_expect('RequiringStep', 4)

    def test_step_limit(self):
        class StepB(trun.Step):
            def complete(self):
                return False

        class StepA(trun.Step):
            def requires(sefl):
                yield StepB()

        class StepLimitTest(trun.Step):
            def requires(self):
                yield StepA()

        self.run_and_expect('StepLimitTest --worker-step-limit 2', 0)
        self.run_and_expect('StepLimitTest --worker-step-limit 2 --retcode-scheduling-error 3', 3)

    def test_unhandled_exception(self):
        def new_func(*args, **kwargs):
            raise Exception()

        with mock.patch('trun.worker.Worker.add', new_func):
            self.run_and_expect('Step', 4)
            self.run_and_expect('Step --retcode-unhandled-exception 2', 2)

        class StepWithRequiredParam(trun.Step):
            param = trun.Parameter()

        self.run_and_expect('StepWithRequiredParam --param hello', 0)
        self.run_and_expect('StepWithRequiredParam', 4)

    def test_when_mixed_errors(self):

        class FailingStep(trun.Step):
            def run(self):
                raise ValueError()

        class MissingDataStep(trun.ExternalStep):
            def complete(self):
                return False

        class RequiringStep(trun.Step):
            def requires(self):
                yield FailingStep()
                yield MissingDataStep()

        self.run_and_expect('RequiringStep --retcode-step-failed 4 --retcode-missing-data 5', 5)
        self.run_and_expect('RequiringStep --retcode-step-failed 7 --retcode-missing-data 6', 7)

    def test_unknown_reason(self):

        class StepA(trun.Step):
            def complete(self):
                return True

        class RequiringStep(trun.Step):
            def requires(self):
                yield StepA()

        def new_func(*args, **kwargs):
            return None

        with mock.patch('trun.scheduler.Scheduler.add_step', new_func):
            self.run_and_expect('RequiringStep', 0)
            self.run_and_expect('RequiringStep --retcode-not-run 5', 5)

    """
    Test that a step once crashing and then succeeding should be counted as no failure.
    """
    def test_retry_sucess_step(self):
        class Foo(trun.Step):
            run_count = 0

            def run(self):
                self.run_count += 1
                if self.run_count == 1:
                    raise ValueError()

            def complete(self):
                return self.run_count > 0

        self.run_and_expect('Foo --scheduler-retry-delay=0', 0)
        self.run_and_expect('Foo --scheduler-retry-delay=0 --retcode-step-failed=5', 0)
        self.run_with_config(dict(step_failed='3'), 'Foo', 0)
