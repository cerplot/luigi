
import email.parser
import functools
import logging
import os
import shutil
import signal
import tempfile
import threading
import time

import psutil
from helpers import (unittest, with_config, skipOnTravisAndGithubActions, TrunTestCase,
                     temporary_unloaded_module)

import trun.notifications
import trun.step_register
import trun.worker
import mock
from trun import ExternalStep, RemoteScheduler, Step, Event
from trun.mock import MockTarget, MockFileSystem
from trun.scheduler import Scheduler
from trun.worker import Worker
from trun.rpc import RPCError
from trun.cmdline import trun_run

trun.notifications.DEBUG = True


class DummyStep(Step):

    def __init__(self, *args, **kwargs):
        super(DummyStep, self).__init__(*args, **kwargs)
        self.has_run = False

    def complete(self):
        return self.has_run

    def run(self):
        logging.debug("%s - setting has_run", self)
        self.has_run = True


class DynamicDummyStep(Step):
    p = trun.Parameter()
    sleep = trun.FloatParameter(default=0.5, significant=False)

    def output(self):
        return trun.LocalTarget(self.p)

    def run(self):
        with self.output().open('w') as f:
            f.write('Done!')
        time.sleep(self.sleep)  # so we can benchmark & see if parallelization works


class DynamicDummyStepWithNamespace(DynamicDummyStep):
    step_namespace = 'banana'


class DynamicRequires(Step):
    p = trun.Parameter()
    use_banana_step = trun.BoolParameter(default=False)

    def output(self):
        return trun.LocalTarget(os.path.join(self.p, 'parent'))

    def run(self):
        if self.use_banana_step:
            step_cls = DynamicDummyStepWithNamespace
        else:
            step_cls = DynamicDummyStep
        dummy_targets = yield [step_cls(os.path.join(self.p, str(i)))
                               for i in range(5)]
        dummy_targets += yield [step_cls(os.path.join(self.p, str(i)))
                                for i in range(5, 7)]
        with self.output().open('w') as f:
            for i, d in enumerate(dummy_targets):
                for line in d.open('r'):
                    print('%d: %s' % (i, line.strip()), file=f)


class DynamicRequiresWrapped(Step):
    p = trun.Parameter()

    def output(self):
        return trun.LocalTarget(os.path.join(self.p, 'parent'))

    def run(self):
        reqs = [
            DynamicDummyStep(p=os.path.join(self.p, '%s.txt' % i), sleep=0.0)
            for i in range(10)
        ]

        # yield again as DynamicRequires
        yield trun.DynamicRequirements(reqs)

        # and again with a custom complete function that does base name comparisons
        def custom_complete(complete_fn):
            if not complete_fn(reqs[0]):
                return False
            paths = [step.output().path for step in reqs]
            basenames = os.listdir(os.path.dirname(paths[0]))
            self._custom_complete_called = True
            self._custom_complete_result = all(os.path.basename(path) in basenames for path in paths)
            return self._custom_complete_result

        yield trun.DynamicRequirements(reqs, custom_complete)

        with self.output().open('w') as f:
            f.write('Done!')


class DynamicRequiresOtherModule(Step):
    p = trun.Parameter()

    def output(self):
        return trun.LocalTarget(os.path.join(self.p, 'baz'))

    def run(self):
        import other_module
        other_target_foo = yield other_module.OtherModuleStep(os.path.join(self.p, 'foo'))  # NOQA
        other_target_bar = yield other_module.OtherModuleStep(os.path.join(self.p, 'bar'))  # NOQA

        with self.output().open('w') as f:
            f.write('Done!')


class DummyErrorStep(Step):
    retry_index = 0

    def run(self):
        self.retry_index += 1
        raise Exception("Retry index is %s for %s" % (self.retry_index, self.step_family))


class WorkerTest(TrunTestCase):

    def run(self, result=None):
        self.sch = Scheduler(retry_delay=100, remove_delay=1000, worker_disconnect_delay=10, stable_done_cooldown_secs=0)
        self.time = time.time
        with Worker(scheduler=self.sch, worker_id='X') as w, Worker(scheduler=self.sch, worker_id='Y') as w2:
            self.w = w
            self.w2 = w2
            super(WorkerTest, self).run(result)

        if time.time != self.time:
            time.time = self.time

    def setTime(self, t):
        time.time = lambda: t

    def test_dep(self):
        class A(Step):

            def run(self):
                self.has_run = True

            def complete(self):
                return self.has_run
        a = A()

        class B(Step):

            def requires(self):
                return a

            def run(self):
                self.has_run = True

            def complete(self):
                return self.has_run

        b = B()
        a.has_run = False
        b.has_run = False

        self.assertTrue(self.w.add(b))
        self.assertTrue(self.w.run())
        self.assertTrue(a.has_run)
        self.assertTrue(b.has_run)

    def test_external_dep(self):
        class A(ExternalStep):

            def complete(self):
                return False
        a = A()

        class B(Step):

            def requires(self):
                return a

            def run(self):
                self.has_run = True

            def complete(self):
                return self.has_run

        b = B()

        a.has_run = False
        b.has_run = False

        self.assertTrue(self.w.add(b))
        self.assertTrue(self.w.run())

        self.assertFalse(a.has_run)
        self.assertFalse(b.has_run)

    def test_externalized_dep(self):
        class A(Step):
            has_run = False

            def run(self):
                self.has_run = True

            def complete(self):
                return self.has_run
        a = A()

        class B(A):
            def requires(self):
                return trun.step.externalize(a)
        b = B()

        self.assertTrue(self.w.add(b))
        self.assertTrue(self.w.run())

        self.assertFalse(a.has_run)
        self.assertFalse(b.has_run)

    def test_legacy_externalized_dep(self):
        class A(Step):
            has_run = False

            def run(self):
                self.has_run = True

            def complete(self):
                return self.has_run
        a = A()
        a.run = NotImplemented

        class B(A):
            def requires(self):
                return a
        b = B()

        self.assertTrue(self.w.add(b))
        self.assertTrue(self.w.run())

        self.assertFalse(a.has_run)
        self.assertFalse(b.has_run)

    def test_type_error_in_tracking_run_deprecated(self):
        class A(Step):
            num_runs = 0

            def complete(self):
                return False

            def run(self, tracking_url_callback=None):
                self.num_runs += 1
                raise TypeError('bad type')

        a = A()
        self.assertTrue(self.w.add(a))
        self.assertFalse(self.w.run())

        # Should only run and fail once, not retry because of the type error
        self.assertEqual(1, a.num_runs)

    def test_tracking_url(self):
        tracking_url = 'http://test_url.com/'

        class A(Step):
            has_run = False

            def complete(self):
                return self.has_run

            def run(self):
                self.set_tracking_url(tracking_url)
                self.has_run = True

        a = A()
        self.assertTrue(self.w.add(a))
        self.assertTrue(self.w.run())
        steps = self.sch.step_list('DONE', '')
        self.assertEqual(1, len(steps))
        self.assertEqual(tracking_url, steps[a.step_id]['tracking_url'])

    def test_fail(self):
        class CustomException(BaseException):
            def __init__(self, msg):
                self.msg = msg

        class A(Step):

            def run(self):
                self.has_run = True
                raise CustomException('bad things')

            def complete(self):
                return self.has_run

        a = A()

        class B(Step):

            def requires(self):
                return a

            def run(self):
                self.has_run = True

            def complete(self):
                return self.has_run

        b = B()

        a.has_run = False
        b.has_run = False

        self.assertTrue(self.w.add(b))
        self.assertFalse(self.w.run())

        self.assertTrue(a.has_run)
        self.assertFalse(b.has_run)

    def test_unknown_dep(self):
        # see related test_remove_dep test (grep for it)
        class A(ExternalStep):

            def complete(self):
                return False

        class C(Step):

            def complete(self):
                return True

        def get_b(dep):
            class B(Step):

                def requires(self):
                    return dep

                def run(self):
                    self.has_run = True

                def complete(self):
                    return False

            b = B()
            b.has_run = False
            return b

        b_a = get_b(A())
        b_c = get_b(C())

        self.assertTrue(self.w.add(b_a))
        # So now another worker goes in and schedules C -> B
        # This should remove the dep A -> B but will screw up the first worker
        self.assertTrue(self.w2.add(b_c))

        self.assertFalse(self.w.run())  # should not run anything - the worker should detect that A is broken
        self.assertFalse(b_a.has_run)
        # not sure what should happen??
        # self.w2.run() # should run B since C is fulfilled
        # self.assertTrue(b_c.has_run)

    def test_unfulfilled_dep(self):
        class A(Step):

            def complete(self):
                return self.done

            def run(self):
                self.done = True

        def get_b(a):
            class B(A):

                def requires(self):
                    return a
            b = B()
            b.done = False
            a.done = True
            return b

        a = A()
        b = get_b(a)

        self.assertTrue(self.w.add(b))
        a.done = False
        self.w.run()
        self.assertTrue(a.complete())
        self.assertTrue(b.complete())

    def test_check_unfulfilled_deps_config(self):
        class A(Step):

            i = trun.IntParameter()

            def __init__(self, *args, **kwargs):
                super(A, self).__init__(*args, **kwargs)
                self.complete_count = 0
                self.has_run = False

            def complete(self):
                self.complete_count += 1
                return self.has_run

            def run(self):
                self.has_run = True

        class B(A):

            def requires(self):
                return A(i=self.i)

        # test the enabled features
        with Worker(scheduler=self.sch, worker_id='1') as w:
            w._config.check_unfulfilled_deps = True
            a1 = A(i=1)
            b1 = B(i=1)
            self.assertTrue(w.add(b1))
            self.assertEqual(a1.complete_count, 1)
            self.assertEqual(b1.complete_count, 1)
            w.run()
            self.assertTrue(a1.complete())
            self.assertTrue(b1.complete())
            self.assertEqual(a1.complete_count, 3)
            self.assertEqual(b1.complete_count, 2)

        # test the disabled features
        with Worker(scheduler=self.sch, worker_id='2') as w:
            w._config.check_unfulfilled_deps = False
            a2 = A(i=2)
            b2 = B(i=2)
            self.assertTrue(w.add(b2))
            self.assertEqual(a2.complete_count, 1)
            self.assertEqual(b2.complete_count, 1)
            w.run()
            self.assertTrue(a2.complete())
            self.assertTrue(b2.complete())
            self.assertEqual(a2.complete_count, 2)
            self.assertEqual(b2.complete_count, 2)

    def test_cache_step_completion_config(self):
        class A(Step):

            i = trun.IntParameter()

            def __init__(self, *args, **kwargs):
                super(A, self).__init__(*args, **kwargs)
                self.complete_count = 0
                self.has_run = False

            def complete(self):
                self.complete_count += 1
                return self.has_run

            def run(self):
                self.has_run = True

        class B(A):

            def run(self):
                yield A(i=self.i + 0)
                yield A(i=self.i + 1)
                yield A(i=self.i + 2)
                self.has_run = True

        # test with enabled cache_step_completion
        with Worker(scheduler=self.sch, worker_id='2', cache_step_completion=True) as w:
            b0 = B(i=0)
            a0 = A(i=0)
            a1 = A(i=1)
            a2 = A(i=2)
            self.assertTrue(w.add(b0))
            # a's are required dynamically, so their counts must be 0
            self.assertEqual(b0.complete_count, 1)
            self.assertEqual(a0.complete_count, 0)
            self.assertEqual(a1.complete_count, 0)
            self.assertEqual(a2.complete_count, 0)
            w.run()
            # the complete methods of a's yielded first in b's run method were called equally often
            self.assertEqual(b0.complete_count, 1)
            self.assertEqual(a0.complete_count, 2)
            self.assertEqual(a1.complete_count, 2)
            self.assertEqual(a2.complete_count, 2)

        # test with disabled cache_step_completion
        with Worker(scheduler=self.sch, worker_id='2', cache_step_completion=False) as w:
            b10 = B(i=10)
            a10 = A(i=10)
            a11 = A(i=11)
            a12 = A(i=12)
            self.assertTrue(w.add(b10))
            # a's are required dynamically, so their counts must be 0
            self.assertEqual(b10.complete_count, 1)
            self.assertEqual(a10.complete_count, 0)
            self.assertEqual(a11.complete_count, 0)
            self.assertEqual(a12.complete_count, 0)
            w.run()
            # the complete methods of a's yielded first in b's run method were called more often
            self.assertEqual(b10.complete_count, 1)
            self.assertEqual(a10.complete_count, 5)
            self.assertEqual(a11.complete_count, 4)
            self.assertEqual(a12.complete_count, 3)

        # test with enabled check_complete_on_run
        with Worker(scheduler=self.sch, worker_id='2', check_complete_on_run=True) as w:
            b20 = B(i=20)
            a20 = A(i=20)
            a21 = A(i=21)
            a22 = A(i=22)
            self.assertTrue(w.add(b20))
            # a's are required dynamically, so their counts must be 0
            self.assertEqual(b20.complete_count, 1)
            self.assertEqual(a20.complete_count, 0)
            self.assertEqual(a21.complete_count, 0)
            self.assertEqual(a22.complete_count, 0)
            w.run()
            # the complete methods of a's yielded first in b's run method were called more often
            self.assertEqual(b20.complete_count, 2)
            self.assertEqual(a20.complete_count, 6)
            self.assertEqual(a21.complete_count, 5)
            self.assertEqual(a22.complete_count, 4)

    def test_gets_missed_work(self):
        class A(Step):
            done = False

            def complete(self):
                return self.done

            def run(self):
                self.done = True

        a = A()
        self.assertTrue(self.w.add(a))

        # simulate a missed get_work response
        self.assertEqual(a.step_id, self.sch.get_work(worker='X')['step_id'])

        self.assertTrue(self.w.run())
        self.assertTrue(a.complete())

    def test_avoid_infinite_reschedule(self):
        class A(Step):

            def complete(self):
                return False

        class B(Step):

            def complete(self):
                return False

            def requires(self):
                return A()

        self.assertTrue(self.w.add(B()))
        self.assertFalse(self.w.run())

    def test_fails_registering_signal(self):
        with mock.patch('trun.worker.signal', spec=['signal']):
            # mock will raise an attribute error getting signal.SIGUSR1
            Worker()

    def test_allow_reschedule_with_many_missing_deps(self):
        class A(Step):

            """ Step that must run twice to succeed """
            i = trun.IntParameter()

            runs = 0

            def complete(self):
                return self.runs >= 2

            def run(self):
                self.runs += 1

        class B(Step):
            done = False

            def requires(self):
                return map(A, range(20))

            def complete(self):
                return self.done

            def run(self):
                self.done = True

        b = B()
        w = Worker(scheduler=self.sch, worker_id='X', max_reschedules=1)
        self.assertTrue(w.add(b))
        self.assertFalse(w.run())

        # For b to be done, we must have rescheduled its dependencies to run them twice
        self.assertTrue(b.complete())
        self.assertTrue(all(a.complete() for a in b.deps()))

    def test_interleaved_workers(self):
        class A(DummyStep):
            pass

        a = A()

        class B(DummyStep):

            def requires(self):
                return a

        ExternalB = trun.step.externalize(B)

        b = B()
        eb = ExternalB()
        self.assertEqual(str(eb), "B()")

        sch = Scheduler(retry_delay=100, remove_delay=1000, worker_disconnect_delay=10)
        with Worker(scheduler=sch, worker_id='X') as w, Worker(scheduler=sch, worker_id='Y') as w2:
            self.assertTrue(w.add(b))
            self.assertTrue(w2.add(eb))
            logging.debug("RUNNING BROKEN WORKER")
            self.assertTrue(w2.run())
            self.assertFalse(a.complete())
            self.assertFalse(b.complete())
            logging.debug("RUNNING FUNCTIONAL WORKER")
            self.assertTrue(w.run())
            self.assertTrue(a.complete())
            self.assertTrue(b.complete())

    def test_interleaved_workers2(self):
        # two steps without dependencies, one external, one not
        class B(DummyStep):
            pass

        ExternalB = trun.step.externalize(B)

        b = B()
        eb = ExternalB()

        self.assertEqual(str(eb), "B()")

        sch = Scheduler(retry_delay=100, remove_delay=1000, worker_disconnect_delay=10)
        with Worker(scheduler=sch, worker_id='X') as w, Worker(scheduler=sch, worker_id='Y') as w2:
            self.assertTrue(w2.add(eb))
            self.assertTrue(w.add(b))

            self.assertTrue(w2.run())
            self.assertFalse(b.complete())
            self.assertTrue(w.run())
            self.assertTrue(b.complete())

    def test_interleaved_workers3(self):
        class A(DummyStep):

            def run(self):
                logging.debug('running A')
                time.sleep(0.1)
                super(A, self).run()

        a = A()

        class B(DummyStep):

            def requires(self):
                return a

            def run(self):
                logging.debug('running B')
                super(B, self).run()

        b = B()

        sch = Scheduler(retry_delay=100, remove_delay=1000, worker_disconnect_delay=10)

        with Worker(scheduler=sch, worker_id='X', keep_alive=True, count_uniques=True) as w:
            with Worker(scheduler=sch, worker_id='Y', keep_alive=True, count_uniques=True, wait_interval=0.1, wait_jitter=0.05) as w2:
                self.assertTrue(w.add(a))
                self.assertTrue(w2.add(b))

                threading.Thread(target=w.run).start()
                self.assertTrue(w2.run())

                self.assertTrue(a.complete())
                self.assertTrue(b.complete())

    def test_die_for_non_unique_pending(self):
        class A(DummyStep):

            def run(self):
                logging.debug('running A')
                time.sleep(0.1)
                super(A, self).run()

        a = A()

        class B(DummyStep):

            def requires(self):
                return a

            def run(self):
                logging.debug('running B')
                super(B, self).run()

        b = B()

        sch = Scheduler(retry_delay=100, remove_delay=1000, worker_disconnect_delay=10)

        with Worker(scheduler=sch, worker_id='X', keep_alive=True, count_uniques=True) as w:
            with Worker(scheduler=sch, worker_id='Y', keep_alive=True, count_uniques=True, wait_interval=0.1, wait_jitter=0.05) as w2:
                self.assertTrue(w.add(b))
                self.assertTrue(w2.add(b))

                self.assertEqual(w._get_work()[0], a.step_id)
                self.assertTrue(w2.run())

                self.assertFalse(a.complete())
                self.assertFalse(b.complete())

    def test_complete_exception(self):
        "Tests that a step is still scheduled if its sister step crashes in the complete() method"
        class A(DummyStep):

            def complete(self):
                raise Exception("doh")

        a = A()

        class C(DummyStep):
            pass

        c = C()

        class B(DummyStep):

            def requires(self):
                return a, c

        b = B()
        sch = Scheduler(retry_delay=100, remove_delay=1000, worker_disconnect_delay=10)
        with Worker(scheduler=sch, worker_id="foo") as w:
            self.assertFalse(w.add(b))
            self.assertTrue(w.run())
            self.assertFalse(b.has_run)
            self.assertTrue(c.has_run)
            self.assertFalse(a.has_run)

    def test_requires_exception(self):
        class A(DummyStep):

            def requires(self):
                raise Exception("doh")

        a = A()

        class D(DummyStep):
            pass

        d = D()

        class C(DummyStep):
            def requires(self):
                return d

        c = C()

        class B(DummyStep):

            def requires(self):
                return c, a

        b = B()
        sch = Scheduler(retry_delay=100, remove_delay=1000, worker_disconnect_delay=10)
        with Worker(scheduler=sch, worker_id="foo") as w:
            self.assertFalse(w.add(b))
            self.assertTrue(w.run())
            self.assertFalse(b.has_run)
            self.assertTrue(c.has_run)
            self.assertTrue(d.has_run)
            self.assertFalse(a.has_run)

    def test_run_csv_batch_job(self):
        completed = set()

        class CsvBatchJob(trun.Step):
            values = trun.parameter.Parameter(batch_method=','.join)
            has_run = False

            def run(self):
                completed.update(self.values.split(','))
                self.has_run = True

            def complete(self):
                return all(value in completed for value in self.values.split(','))

        steps = [CsvBatchJob(str(i)) for i in range(10)]
        for step in steps:
            self.assertTrue(self.w.add(step))
        self.assertTrue(self.w.run())

        for step in steps:
            self.assertTrue(step.complete())
            self.assertFalse(step.has_run)

    def test_run_max_batch_job(self):
        completed = set()

        class MaxBatchJob(trun.Step):
            value = trun.IntParameter(batch_method=max)
            has_run = False

            def run(self):
                completed.add(self.value)
                self.has_run = True

            def complete(self):
                return any(self.value <= ran for ran in completed)

        steps = [MaxBatchJob(i) for i in range(10)]
        for step in steps:
            self.assertTrue(self.w.add(step))
        self.assertTrue(self.w.run())

        for step in steps:
            self.assertTrue(step.complete())
            # only step number 9 should run
            self.assertFalse(step.has_run and step.value < 9)

    def test_run_batch_job_unbatched(self):
        completed = set()

        class MaxNonBatchJob(trun.Step):
            value = trun.IntParameter(batch_method=max)
            has_run = False

            batchable = False

            def run(self):
                completed.add(self.value)
                self.has_run = True

            def complete(self):
                return self.value in completed

        steps = [MaxNonBatchJob((i,)) for i in range(10)]
        for step in steps:
            self.assertTrue(self.w.add(step))
        self.assertTrue(self.w.run())

        for step in steps:
            self.assertTrue(step.complete())
            self.assertTrue(step.has_run)

    def test_run_batch_job_limit_batch_size(self):
        completed = set()
        runs = []

        class CsvLimitedBatchJob(trun.Step):
            value = trun.parameter.Parameter(batch_method=','.join)
            has_run = False

            max_batch_size = 4

            def run(self):
                completed.update(self.value.split(','))
                runs.append(self)

            def complete(self):
                return all(value in completed for value in self.value.split(','))

        steps = [CsvLimitedBatchJob(str(i)) for i in range(11)]
        for step in steps:
            self.assertTrue(self.w.add(step))
        self.assertTrue(self.w.run())

        for step in steps:
            self.assertTrue(step.complete())

        self.assertEqual(3, len(runs))

    def test_fail_max_batch_job(self):
        class MaxBatchFailJob(trun.Step):
            value = trun.IntParameter(batch_method=max)
            has_run = False

            def run(self):
                self.has_run = True
                assert False

            def complete(self):
                return False

        steps = [MaxBatchFailJob(i) for i in range(10)]
        for step in steps:
            self.assertTrue(self.w.add(step))
        self.assertFalse(self.w.run())

        for step in steps:
            # only step number 9 should run
            self.assertFalse(step.has_run and step.value < 9)

        self.assertEqual({step.step_id for step in steps}, set(self.sch.step_list('FAILED', '')))

    def test_gracefully_handle_batch_method_failure(self):
        class BadBatchMethodStep(DummyStep):
            priority = 10
            batch_int_param = trun.IntParameter(batch_method=int.__add__)  # should be sum

        bad_steps = [BadBatchMethodStep(i) for i in range(5)]
        good_steps = [DummyStep()]
        all_steps = good_steps + bad_steps

        self.assertFalse(any(step.complete() for step in all_steps))

        worker = Worker(scheduler=Scheduler(retry_count=1), keep_alive=True)

        for step in all_steps:
            self.assertTrue(worker.add(step))
        self.assertFalse(worker.run())
        self.assertFalse(any(step.complete() for step in bad_steps))

        # we only get to run the good step if the bad step failures were handled gracefully
        self.assertTrue(all(step.complete() for step in good_steps))

    def test_post_error_message_for_failed_batch_methods(self):
        class BadBatchMethodStep(DummyStep):
            batch_int_param = trun.IntParameter(batch_method=int.__add__)  # should be sum

        steps = [BadBatchMethodStep(1), BadBatchMethodStep(2)]

        for step in steps:
            self.assertTrue(self.w.add(step))
        self.assertFalse(self.w.run())

        failed_ids = set(self.sch.step_list('FAILED', ''))
        self.assertEqual({step.step_id for step in steps}, failed_ids)
        self.assertTrue(all(self.sch.fetch_error(step_id)['error'] for step_id in failed_ids))


class WorkerKeepAliveTests(TrunTestCase):
    def setUp(self):
        self.sch = Scheduler()
        super(WorkerKeepAliveTests, self).setUp()

    def _worker_keep_alive_test(self, first_should_live, second_should_live, step_status=None, **worker_args):
        worker_args.update({
            'scheduler': self.sch,
            'worker_processes': 0,
            'wait_interval': 0.01,
            'wait_jitter': 0.0,
        })
        w1 = Worker(worker_id='w1', **worker_args)
        w2 = Worker(worker_id='w2', **worker_args)
        with w1 as worker1, w2 as worker2:
            worker1.add(DummyStep())
            t1 = threading.Thread(target=worker1.run)
            t1.start()

            worker2.add(DummyStep())
            t2 = threading.Thread(target=worker2.run)
            t2.start()

            if step_status:
                self.sch.add_step(worker='DummyWorker', step_id=DummyStep().step_id, status=step_status)

            # allow workers to run their get work loops a few times
            time.sleep(0.1)

            try:
                self.assertEqual(first_should_live, t1.is_alive())
                self.assertEqual(second_should_live, t2.is_alive())

            finally:
                # mark the step done so the worker threads will die
                self.sch.add_step(worker='DummyWorker', step_id=DummyStep().step_id, status='DONE')
                t1.join()
                t2.join()

    def test_no_keep_alive(self):
        self._worker_keep_alive_test(
            first_should_live=False,
            second_should_live=False,
        )

    def test_keep_alive(self):
        self._worker_keep_alive_test(
            first_should_live=True,
            second_should_live=True,
            keep_alive=True,
        )

    def test_keep_alive_count_uniques(self):
        self._worker_keep_alive_test(
            first_should_live=False,
            second_should_live=False,
            keep_alive=True,
            count_uniques=True,
        )

    def test_keep_alive_count_last_scheduled(self):
        self._worker_keep_alive_test(
            first_should_live=False,
            second_should_live=True,
            keep_alive=True,
            count_last_scheduled=True,
        )

    def test_keep_alive_through_failure(self):
        self._worker_keep_alive_test(
            first_should_live=True,
            second_should_live=True,
            keep_alive=True,
            step_status='FAILED',
        )

    def test_do_not_keep_alive_through_disable(self):
        self._worker_keep_alive_test(
            first_should_live=False,
            second_should_live=False,
            keep_alive=True,
            step_status='DISABLED',
        )


class WorkerInterruptedTest(unittest.TestCase):
    def setUp(self):
        self.sch = Scheduler(retry_delay=100, remove_delay=1000, worker_disconnect_delay=10)

    requiring_sigusr = unittest.skipUnless(hasattr(signal, 'SIGUSR1'),
                                           'signal.SIGUSR1 not found on this system')

    def _test_stop_getting_new_work(self, worker):
        d = DummyStep()
        with worker:
            worker.add(d)  # For assistant its ok that other steps add it
            self.assertFalse(d.complete())
            worker.handle_interrupt(signal.SIGUSR1, None)
            worker.run()
            self.assertFalse(d.complete())

    @requiring_sigusr
    def test_stop_getting_new_work(self):
        self._test_stop_getting_new_work(
            Worker(scheduler=self.sch))

    @requiring_sigusr
    def test_stop_getting_new_work_assistant(self):
        self._test_stop_getting_new_work(
            Worker(scheduler=self.sch, keep_alive=False, assistant=True))

    @requiring_sigusr
    def test_stop_getting_new_work_assistant_keep_alive(self):
        self._test_stop_getting_new_work(
            Worker(scheduler=self.sch, keep_alive=True, assistant=True))

    def test_existence_of_disabling_option(self):
        # any code equivalent of `os.kill(os.getpid(), signal.SIGUSR1)`
        # seem to give some sort of a "InvocationError"
        Worker(no_install_shutdown_handler=True)

    @with_config({"worker": {"no_install_shutdown_handler": "True"}})
    def test_can_run_trun_in_thread(self):
        class A(DummyStep):
            pass
        step = A()
        # Note that ``signal.signal(signal.SIGUSR1, fn)`` can only be called in the main thread.
        # So if we do not disable the shutdown handler, this would fail.
        t = threading.Thread(target=lambda: trun.build([step], local_scheduler=True))
        t.start()
        t.join()
        self.assertTrue(step.complete())


class WorkerDisabledTest(TrunTestCase):
    def make_sch(self):
        return Scheduler(retry_delay=100, remove_delay=1000, worker_disconnect_delay=10)

    def _test_stop_getting_new_work_build(self, sch, worker):
        """
        I got motivated to create this test case when I saw that the
        execution_summary crashed after my first attempted solution.
        """
        class KillWorkerStep(trun.Step):
            did_actually_run = False

            def run(self):
                sch.disable_worker('my_worker_id')
                KillWorkerStep.did_actually_run = True

        class Factory:
            def create_local_scheduler(self, *args, **kwargs):
                return sch

            def create_worker(self, *args, **kwargs):
                return worker

        trun.build([KillWorkerStep()], worker_scheduler_factory=Factory(), local_scheduler=True)
        self.assertTrue(KillWorkerStep.did_actually_run)

    def _test_stop_getting_new_work_manual(self, sch, worker):
        d = DummyStep()
        with worker:
            worker.add(d)  # For assistant its ok that other steps add it
            self.assertFalse(d.complete())
            sch.disable_worker('my_worker_id')
            worker.run()  # Note: Test could fail by hanging on this line
            self.assertFalse(d.complete())

    def _test_stop_getting_new_work(self, **worker_kwargs):
        worker_kwargs['worker_id'] = 'my_worker_id'

        sch = self.make_sch()
        worker_kwargs['scheduler'] = sch
        self._test_stop_getting_new_work_manual(sch, Worker(**worker_kwargs))

        sch = self.make_sch()
        worker_kwargs['scheduler'] = sch
        self._test_stop_getting_new_work_build(sch, Worker(**worker_kwargs))

    def test_stop_getting_new_work_keep_alive(self):
        self._test_stop_getting_new_work(keep_alive=True, assistant=False)

    def test_stop_getting_new_work_assistant(self):
        self._test_stop_getting_new_work(keep_alive=False, assistant=True)

    def test_stop_getting_new_work_assistant_keep_alive(self):
        self._test_stop_getting_new_work(keep_alive=True, assistant=True)


class DynamicDependenciesTest(unittest.TestCase):
    n_workers = 1
    timeout = float('inf')

    def setUp(self):
        self.p = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.p)

    def test_dynamic_dependencies(self, use_banana_step=False):
        t0 = time.time()
        t = DynamicRequires(p=self.p, use_banana_step=use_banana_step)
        trun.build([t], local_scheduler=True, workers=self.n_workers)
        self.assertTrue(t.complete())

        # loop through output and verify
        with t.output().open('r') as f:
            for i in range(7):
                self.assertEqual(f.readline().strip(), '%d: Done!' % i)

        self.assertTrue(time.time() - t0 < self.timeout)

    def test_dynamic_dependencies_with_namespace(self):
        self.test_dynamic_dependencies(use_banana_step=True)

    def test_dynamic_dependencies_other_module(self):
        t = DynamicRequiresOtherModule(p=self.p)
        trun.build([t], local_scheduler=True, workers=self.n_workers)
        self.assertTrue(t.complete())

    def test_wrapped_dynamic_requirements(self):
        t = DynamicRequiresWrapped(p=self.p)
        trun.build([t], local_scheduler=True, workers=1)
        self.assertTrue(t.complete())
        self.assertTrue(getattr(t, '_custom_complete_called', False))
        self.assertTrue(getattr(t, '_custom_complete_result', False))


class DynamicDependenciesWithMultipleWorkersTest(DynamicDependenciesTest):
    n_workers = 100
    timeout = 3.0  # We run 7 steps that take 0.5s each so it should take less than 3.5s


class WorkerPingThreadTests(unittest.TestCase):

    def test_ping_retry(self):
        """ Worker ping fails once. Ping continues to try to connect to scheduler

        Kind of ugly since it uses actual timing with sleep to test the thread
        """
        sch = Scheduler(
            retry_delay=100,
            remove_delay=1000,
            worker_disconnect_delay=10,
        )

        self._total_pings = 0  # class var so it can be accessed from fail_ping

        def fail_ping(worker):
            # this will be called from within keep-alive thread...
            self._total_pings += 1
            raise Exception("Some random exception")

        sch.ping = fail_ping

        with Worker(
                scheduler=sch,
                worker_id="foo",
                ping_interval=0.01  # very short between pings to make test fast
                ):
            # let the keep-alive thread run for a bit...
            time.sleep(0.1)  # yes, this is ugly but it's exactly what we need to test
        self.assertTrue(
            self._total_pings > 1,
            msg="Didn't retry pings (%d pings performed)" % (self._total_pings,)
        )

    def test_ping_thread_shutdown(self):
        with Worker(ping_interval=0.01) as w:
            self.assertTrue(w._keep_alive_thread.is_alive())
        self.assertFalse(w._keep_alive_thread.is_alive())


def email_patch(test_func, email_config=None):
    EMAIL_CONFIG = {"email": {"receiver": "not-a-real-email-address-for-test-only", "force_send": "true"}}
    if email_config is not None:
        EMAIL_CONFIG.update(email_config)
    emails = []

    def mock_send_email(sender, recipients, msg):
        emails.append(msg)

    @with_config(EMAIL_CONFIG)
    @functools.wraps(test_func)
    @mock.patch('smtplib.SMTP')
    def run_test(self, smtp):
        smtp().sendmail.side_effect = mock_send_email
        test_func(self, emails)

    return run_test


def custom_email_patch(config):
    return functools.partial(email_patch, email_config=config)


class WorkerEmailTest(TrunTestCase):

    def run(self, result=None):
        super(WorkerEmailTest, self).setUp()
        sch = Scheduler(retry_delay=100, remove_delay=1000, worker_disconnect_delay=10)
        with Worker(scheduler=sch, worker_id="foo") as self.worker:
            super(WorkerEmailTest, self).run(result)

    @email_patch
    def test_connection_error(self, emails):
        sch = RemoteScheduler('http://tld.invalid:1337', connect_timeout=1)
        sch._rpc_retry_wait = 1  # shorten wait time to speed up tests

        class A(DummyStep):
            pass

        a = A()
        self.assertEqual(emails, [])
        with Worker(scheduler=sch) as worker:
            try:
                worker.add(a)
            except RPCError as e:
                self.assertTrue(str(e).find("Errors (3 attempts)") != -1)
                self.assertNotEqual(emails, [])
                self.assertTrue(emails[0].find("Trun: Framework error while scheduling %s" % (a,)) != -1)
            else:
                self.fail()

    @email_patch
    def test_complete_error(self, emails):
        class A(DummyStep):

            def complete(self):
                raise Exception("b0rk")

        a = A()
        self.assertEqual(emails, [])
        self.worker.add(a)
        self.assertTrue(emails[0].find("Trun: %s failed scheduling" % (a,)) != -1)
        self.worker.run()
        self.assertTrue(emails[0].find("Trun: %s failed scheduling" % (a,)) != -1)
        self.assertFalse(a.has_run)

    @with_config({'batch_email': {'email_interval': '0'}, 'worker': {'send_failure_email': 'False'}})
    @email_patch
    def test_complete_error_email_batch(self, emails):
        class A(DummyStep):
            def complete(self):
                raise Exception("b0rk")

        scheduler = Scheduler(batch_emails=True)
        worker = Worker(scheduler)
        a = A()
        self.assertEqual(emails, [])
        worker.add(a)
        self.assertEqual(emails, [])
        worker.run()
        self.assertEqual(emails, [])
        self.assertFalse(a.has_run)
        scheduler.prune()
        self.assertTrue("1 scheduling failure" in emails[0])

    @with_config({'batch_email': {'email_interval': '0'}, 'worker': {'send_failure_email': 'False'}})
    @email_patch
    def test_complete_error_email_batch_to_owner(self, emails):
        class A(DummyStep):
            owner_email = 'a_owner@test.com'

            def complete(self):
                raise Exception("b0rk")

        scheduler = Scheduler(batch_emails=True)
        worker = Worker(scheduler)
        a = A()
        self.assertEqual(emails, [])
        worker.add(a)
        self.assertEqual(emails, [])
        worker.run()
        self.assertEqual(emails, [])
        self.assertFalse(a.has_run)
        scheduler.prune()
        self.assertTrue(any(
            "1 scheduling failure" in email and 'a_owner@test.com' in email
            for email in emails))

    @email_patch
    def test_announce_scheduling_failure_unexpected_error(self, emails):

        class A(DummyStep):
            owner_email = 'a_owner@test.com'

            def complete(self):
                pass

        scheduler = Scheduler(batch_emails=True)
        worker = Worker(scheduler)
        a = A()

        with mock.patch.object(worker._scheduler, 'announce_scheduling_failure',
                               side_effect=Exception('Unexpected')), self.assertRaises(Exception):
            worker.add(a)
        self.assertTrue(len(emails) == 2)  # One for `complete` error, one for exception in announcing.
        self.assertTrue('Trun: Framework error while scheduling' in emails[1])
        self.assertTrue('a_owner@test.com' in emails[1])

    @email_patch
    def test_requires_error(self, emails):
        class A(DummyStep):

            def requires(self):
                raise Exception("b0rk")

        a = A()
        self.assertEqual(emails, [])
        self.worker.add(a)
        self.assertTrue(emails[0].find("Trun: %s failed scheduling" % (a,)) != -1)
        self.worker.run()
        self.assertFalse(a.has_run)

    @with_config({'batch_email': {'email_interval': '0'}, 'worker': {'send_failure_email': 'False'}})
    @email_patch
    def test_requires_error_email_batch(self, emails):
        class A(DummyStep):

            def requires(self):
                raise Exception("b0rk")

        scheduler = Scheduler(batch_emails=True)
        worker = Worker(scheduler)
        a = A()
        self.assertEqual(emails, [])
        worker.add(a)
        self.assertEqual(emails, [])
        worker.run()
        self.assertFalse(a.has_run)
        scheduler.prune()
        self.assertTrue("1 scheduling failure" in emails[0])

    @email_patch
    def test_complete_return_value(self, emails):
        class A(DummyStep):

            def complete(self):
                pass  # no return value should be an error

        a = A()
        self.assertEqual(emails, [])
        self.worker.add(a)
        self.assertTrue(emails[0].find("Trun: %s failed scheduling" % (a,)) != -1)
        self.worker.run()
        self.assertTrue(emails[0].find("Trun: %s failed scheduling" % (a,)) != -1)
        self.assertFalse(a.has_run)

    @with_config({'batch_email': {'email_interval': '0'}, 'worker': {'send_failure_email': 'False'}})
    @email_patch
    def test_complete_return_value_email_batch(self, emails):
        class A(DummyStep):

            def complete(self):
                pass  # no return value should be an error

        scheduler = Scheduler(batch_emails=True)
        worker = Worker(scheduler)
        a = A()
        self.assertEqual(emails, [])
        worker.add(a)
        self.assertEqual(emails, [])
        self.worker.run()
        self.assertEqual(emails, [])
        self.assertFalse(a.has_run)
        scheduler.prune()
        self.assertTrue("1 scheduling failure" in emails[0])

    @email_patch
    def test_run_error(self, emails):
        class A(trun.Step):
            def run(self):
                raise Exception("b0rk")

        a = A()
        trun.build([a], workers=1, local_scheduler=True)
        self.assertEqual(1, len(emails))
        self.assertTrue(emails[0].find("Trun: %s FAILED" % (a,)) != -1)

    @email_patch
    def test_run_error_long_traceback(self, emails):
        class A(trun.Step):
            def run(self):
                raise Exception("b0rk"*10500)

        a = A()
        trun.build([a], workers=1, local_scheduler=True)
        self.assertTrue(len(emails[0]) < 10000)
        self.assertTrue(emails[0].find("Traceback exceeds max length and has been truncated"))

    @with_config({'batch_email': {'email_interval': '0'}, 'worker': {'send_failure_email': 'False'}})
    @email_patch
    def test_run_error_email_batch(self, emails):
        class A(trun.Step):
            owner_email = ['a@test.com', 'b@test.com']

            def run(self):
                raise Exception("b0rk")
        scheduler = Scheduler(batch_emails=True)
        worker = Worker(scheduler)
        worker.add(A())
        worker.run()
        scheduler.prune()
        self.assertEqual(3, len(emails))
        self.assertTrue(any('a@test.com' in email for email in emails))
        self.assertTrue(any('b@test.com' in email for email in emails))

    @with_config({'batch_email': {'email_interval': '0'}, 'worker': {'send_failure_email': 'False'}})
    @email_patch
    def test_run_error_batch_email_string(self, emails):
        class A(trun.Step):
            owner_email = 'a@test.com'

            def run(self):
                raise Exception("b0rk")
        scheduler = Scheduler(batch_emails=True)
        worker = Worker(scheduler)
        worker.add(A())
        worker.run()
        scheduler.prune()
        self.assertEqual(2, len(emails))
        self.assertTrue(any('a@test.com' in email for email in emails))

    @with_config({'worker': {'send_failure_email': 'False'}})
    @email_patch
    def test_run_error_no_email(self, emails):
        class A(trun.Step):
            def run(self):
                raise Exception("b0rk")

        trun.build([A()], workers=1, local_scheduler=True)
        self.assertFalse(emails)

    @staticmethod
    def read_email(email_msg):
        subject_obj, body_obj = email.parser.Parser().parsestr(email_msg).walk()
        return str(subject_obj['Subject']), str(body_obj.get_payload(decode=True))

    @email_patch
    def test_step_process_dies_with_email(self, emails):
        a = SendSignalStep(signal.SIGKILL)
        trun.build([a], workers=2, local_scheduler=True)
        self.assertEqual(1, len(emails))
        subject, body = self.read_email(emails[0])
        self.assertIn("Trun: {} FAILED".format(a), subject)
        self.assertIn("died unexpectedly with exit code -9", body)

    @with_config({'worker': {'send_failure_email': 'False'}})
    @email_patch
    def test_step_process_dies_no_email(self, emails):
        trun.build([SendSignalStep(signal.SIGKILL)], workers=2, local_scheduler=True)
        self.assertEqual([], emails)

    @email_patch
    def test_step_times_out(self, emails):
        class A(trun.Step):
            worker_timeout = 0.0001

            def run(self):
                time.sleep(5)

        a = A()
        trun.build([a], workers=2, local_scheduler=True)
        self.assertEqual(1, len(emails))
        subject, body = self.read_email(emails[0])
        self.assertIn("Trun: %s FAILED" % (a,), subject)
        self.assertIn("timed out after 0.0001 seconds and was terminated.", body)

    @with_config({'worker': {'send_failure_email': 'False'}})
    @email_patch
    def test_step_times_out_no_email(self, emails):
        class A(trun.Step):
            worker_timeout = 0.0001

            def run(self):
                time.sleep(5)

        trun.build([A()], workers=2, local_scheduler=True)
        self.assertEqual([], emails)

    @with_config(dict(worker=dict(retry_external_steps='true')))
    @email_patch
    def test_external_step_retries(self, emails):
        """
        Test that we do not send error emails on the failures of external steps
        """
        class A(trun.ExternalStep):
            pass

        a = A()
        trun.build([a], workers=2, local_scheduler=True)
        self.assertEqual(emails, [])

    @email_patch
    def test_no_error(self, emails):
        class A(DummyStep):
            pass
        a = A()
        self.assertEqual(emails, [])
        self.worker.add(a)
        self.assertEqual(emails, [])
        self.worker.run()
        self.assertEqual(emails, [])
        self.assertTrue(a.complete())

    @custom_email_patch({"email": {"receiver": "not-a-real-email-address-for-test-only", 'format': 'none'}})
    def test_disable_emails(self, emails):
        class A(trun.Step):

            def complete(self):
                raise Exception("b0rk")

        self.worker.add(A())
        self.assertEqual(emails, [])


class RaiseSystemExit(trun.Step):

    def run(self):
        raise SystemExit("System exit!!")


class SendSignalStep(trun.Step):
    signal = trun.IntParameter()

    def run(self):
        os.kill(os.getpid(), self.signal)


class HangTheWorkerStep(trun.Step):
    worker_timeout = trun.IntParameter(default=None)

    def run(self):
        while True:
            pass

    def complete(self):
        return False


class MultipleWorkersTest(unittest.TestCase):

    @unittest.skip('Always skip. There are many intermittent failures')
    def test_multiple_workers(self):
        # Test using multiple workers
        # Also test generating classes dynamically since this may reflect issues with
        # various platform and how multiprocessing is implemented. If it's using os.fork
        # under the hood it should be fine, but dynamic classses can't be pickled, so
        # other implementations of multiprocessing (using spawn etc) may fail
        class MyDynamicStep(trun.Step):
            x = trun.Parameter()

            def run(self):
                time.sleep(0.1)

        t0 = time.time()
        trun.build([MyDynamicStep(i) for i in range(100)], workers=100, local_scheduler=True)
        self.assertTrue(time.time() < t0 + 5.0)  # should ideally take exactly 0.1s, but definitely less than 10.0

    def test_zero_workers(self):
        d = DummyStep()
        trun.build([d], workers=0, local_scheduler=True)
        self.assertFalse(d.complete())

    def test_system_exit(self):
        # This would hang indefinitely before this fix:
        # https://github.com/spotify/trun/pull/439
        trun.build([RaiseSystemExit()], workers=2, local_scheduler=True)

    def test_term_worker(self):
        trun.build([SendSignalStep(signal.SIGTERM)], workers=2, local_scheduler=True)

    def test_kill_worker(self):
        trun.build([SendSignalStep(signal.SIGKILL)], workers=2, local_scheduler=True)

    def test_purge_multiple_workers(self):
        w = Worker(worker_processes=2, wait_interval=0.01)
        t1 = SendSignalStep(signal.SIGTERM)
        t2 = SendSignalStep(signal.SIGKILL)
        w.add(t1)
        w.add(t2)

        w._run_step(t1.step_id)
        w._run_step(t2.step_id)
        time.sleep(1.0)

        w._handle_next_step()
        w._handle_next_step()
        w._handle_next_step()

    def test_stop_worker_kills_subprocesses(self):
        with Worker(worker_processes=2) as w:
            hung_step = HangTheWorkerStep()
            w.add(hung_step)

            w._run_step(hung_step.step_id)
            pids = [p.pid for p in w._running_steps.values()]
            self.assertEqual(1, len(pids))
            pid = pids[0]

            def is_running():
                return pid in {p.pid for p in psutil.Process().children()}

            self.assertTrue(is_running())
        self.assertFalse(is_running())

    @mock.patch('trun.worker.time')
    def test_no_process_leak_from_repeatedly_running_same_step(self, worker_time):
        with Worker(worker_processes=2) as w:
            hung_step = HangTheWorkerStep()
            w.add(hung_step)

            w._run_step(hung_step.step_id)
            children = set(psutil.Process().children())

            # repeatedly try to run the same step id
            for _ in range(10):
                worker_time.sleep.reset_mock()
                w._run_step(hung_step.step_id)

                # should sleep after each attempt
                worker_time.sleep.assert_called_once_with(mock.ANY)

            # only one process should be running
            self.assertEqual(children, set(psutil.Process().children()))

    def test_time_out_hung_worker(self):
        trun.build([HangTheWorkerStep(0.1)], workers=2, local_scheduler=True)

    def test_time_out_hung_single_worker(self):
        trun.build([HangTheWorkerStep(0.1)], workers=1, local_scheduler=True)

    @skipOnTravisAndGithubActions('https://travis-ci.org/spotify/trun/jobs/72953986')
    @mock.patch('trun.worker.time')
    def test_purge_hung_worker_default_timeout_time(self, mock_time):
        w = Worker(worker_processes=2, wait_interval=0.01, timeout=5)
        mock_time.time.return_value = 0
        step = HangTheWorkerStep()
        w.add(step)
        w._run_step(step.step_id)

        mock_time.time.return_value = 5
        w._handle_next_step()
        self.assertEqual(1, len(w._running_steps))

        mock_time.time.return_value = 6
        w._handle_next_step()
        self.assertEqual(0, len(w._running_steps))

    @skipOnTravisAndGithubActions('https://travis-ci.org/spotify/trun/jobs/76645264')
    @mock.patch('trun.worker.time')
    def test_purge_hung_worker_override_timeout_time(self, mock_time):
        w = Worker(worker_processes=2, wait_interval=0.01, timeout=5)
        mock_time.time.return_value = 0
        step = HangTheWorkerStep(worker_timeout=10)
        w.add(step)
        w._run_step(step.step_id)

        mock_time.time.return_value = 10
        w._handle_next_step()
        self.assertEqual(1, len(w._running_steps))

        mock_time.time.return_value = 11
        w._handle_next_step()
        self.assertEqual(0, len(w._running_steps))


class Dummy2Step(Step):
    p = trun.Parameter()

    def output(self):
        return MockTarget(self.p)

    def run(self):
        f = self.output().open('w')
        f.write('test')
        f.close()


class AssistantTest(unittest.TestCase):
    def run(self, result=None):
        self.sch = Scheduler(retry_delay=100, remove_delay=1000, worker_disconnect_delay=10)
        self.assistant = Worker(scheduler=self.sch, worker_id='Y', assistant=True)
        with Worker(scheduler=self.sch, worker_id='X') as w:
            self.w = w
            super(AssistantTest, self).run(result)

    def test_get_work(self):
        d = Dummy2Step('123')
        self.w.add(d)

        self.assertFalse(d.complete())
        self.assistant.run()
        self.assertTrue(d.complete())

    def test_bad_job_type(self):
        class Dummy3Step(Dummy2Step):
            step_family = 'UnknownStepFamily'

        d = Dummy3Step('123')
        self.w.add(d)

        self.assertFalse(d.complete())
        self.assertFalse(self.assistant.run())
        self.assertFalse(d.complete())
        self.assertEqual(list(self.sch.step_list('FAILED', '').keys()), [d.step_id])

    def test_unimported_job_type(self):
        MODULE_CONTENTS = b'''
import trun


class UnimportedStep(trun.Step):
    def complete(self):
        return False
'''
        reg = trun.step_register.Register._get_reg()

        class UnimportedStep(trun.Step):
            step_module = None  # Set it here, so it's generally settable
        trun.step_register.Register._set_reg(reg)

        step = UnimportedStep()

        # verify that it can't run the step without the module info necessary to import it
        self.w.add(step)
        self.assertFalse(self.assistant.run())
        self.assertEqual(list(self.sch.step_list('FAILED', '').keys()), [step.step_id])

        # check that it can import with the right module
        with temporary_unloaded_module(MODULE_CONTENTS) as step.step_module:
            self.w.add(step)
            self.assertTrue(self.assistant.run())
            self.assertEqual(list(self.sch.step_list('DONE', '').keys()), [step.step_id])

    def test_unimported_job_sends_failure_message(self):
        class NotInAssistantStep(trun.Step):
            step_family = 'Unknown'
            step_module = None

        step = NotInAssistantStep()
        self.w.add(step)
        self.assertFalse(self.assistant.run())
        self.assertEqual(list(self.sch.step_list('FAILED', '').keys()), [step.step_id])
        self.assertTrue(self.sch.fetch_error(step.step_id)['error'])


class ForkBombStep(trun.Step):
    depth = trun.IntParameter()
    breadth = trun.IntParameter()
    p = trun.Parameter(default=(0, ))  # ehm for some weird reason [0] becomes a tuple...?

    def output(self):
        return MockTarget('.'.join(map(str, self.p)))

    def run(self):
        with self.output().open('w') as f:
            f.write('Done!')

    def requires(self):
        if len(self.p) < self.depth:
            for i in range(self.breadth):
                yield ForkBombStep(self.depth, self.breadth, self.p + (i, ))


class StepLimitTest(unittest.TestCase):
    def tearDown(self):
        MockFileSystem().remove('')

    @with_config({'worker': {'step_limit': '6'}})
    def test_step_limit_exceeded(self):
        w = Worker()
        t = ForkBombStep(3, 2)
        w.add(t)
        w.run()
        self.assertFalse(t.complete())
        leaf_steps = [ForkBombStep(3, 2, branch) for branch in [(0, 0, 0), (0, 0, 1), (0, 1, 0), (0, 1, 1)]]
        self.assertEqual(3, sum(t.complete() for t in leaf_steps),
                         "should have gracefully completed as much as possible even though the single last leaf didn't get scheduled")

    @with_config({'worker': {'step_limit': '7'}})
    def test_step_limit_not_exceeded(self):
        w = Worker()
        t = ForkBombStep(3, 2)
        w.add(t)
        w.run()
        self.assertTrue(t.complete())

    def test_no_step_limit(self):
        w = Worker()
        t = ForkBombStep(4, 2)
        w.add(t)
        w.run()
        self.assertTrue(t.complete())


class WorkerConfigurationTest(unittest.TestCase):

    def test_asserts_for_worker(self):
        """
        Test that Worker() asserts that it's sanely configured
        """
        Worker(wait_interval=1)  # This shouldn't raise
        self.assertRaises(AssertionError, Worker, wait_interval=0)


class WorkerWaitJitterTest(unittest.TestCase):
    @with_config({'worker': {'wait_jitter': '10.0'}})
    @mock.patch("random.uniform")
    @mock.patch("time.sleep")
    def test_wait_jitter(self, mock_sleep, mock_random):
        """ verify configured jitter amount """
        mock_random.return_value = 1.0

        w = Worker()
        x = w._sleeper()
        next(x)
        mock_random.assert_called_with(0, 10.0)
        mock_sleep.assert_called_with(2.0)

        mock_random.return_value = 2.0
        next(x)
        mock_random.assert_called_with(0, 10.0)
        mock_sleep.assert_called_with(3.0)

    @mock.patch("random.uniform")
    @mock.patch("time.sleep")
    def test_wait_jitter_default(self, mock_sleep, mock_random):
        """ verify default jitter is as expected """
        mock_random.return_value = 1.0
        w = Worker()
        x = w._sleeper()
        next(x)
        mock_random.assert_called_with(0, 5.0)
        mock_sleep.assert_called_with(2.0)

        mock_random.return_value = 3.3
        next(x)
        mock_random.assert_called_with(0, 5.0)
        mock_sleep.assert_called_with(4.3)


class KeyboardInterruptBehaviorTest(TrunTestCase):

    def test_propagation_when_executing(self):
        """
        Ensure that keyboard interrupts causes trun to quit when you are
        executing steps.

        TODO: Add a test that tests the multiprocessing (--worker >1) case
        """
        class KeyboardInterruptStep(trun.Step):
            def run(self):
                raise KeyboardInterrupt()

        cmd = 'KeyboardInterruptStep --local-scheduler --no-lock'.split(' ')
        self.assertRaises(KeyboardInterrupt, trun_run, cmd)

    def test_propagation_when_scheduling(self):
        """
        Test that KeyboardInterrupt causes trun to quit while scheduling.
        """
        class KeyboardInterruptStep(trun.Step):
            def complete(self):
                raise KeyboardInterrupt()

        class ExternalKeyboardInterruptStep(trun.ExternalStep):
            def complete(self):
                raise KeyboardInterrupt()

        self.assertRaises(KeyboardInterrupt, trun_run,
                          ['KeyboardInterruptStep', '--local-scheduler', '--no-lock'])
        self.assertRaises(KeyboardInterrupt, trun_run,
                          ['ExternalKeyboardInterruptStep', '--local-scheduler', '--no-lock'])


class WorkerPurgeEventHandlerTest(unittest.TestCase):

    @mock.patch('trun.worker.ContextManagedStepProcess')
    def test_process_killed_handler(self, step_proc):
        result = []

        @HangTheWorkerStep.event_handler(Event.PROCESS_FAILURE)
        def store_step(t, error_msg):
            self.assertTrue(error_msg)
            result.append(t)

        w = Worker()
        step = HangTheWorkerStep()
        step_process = mock.MagicMock(is_alive=lambda: False, exitcode=-14, step=step)
        step_proc.return_value = step_process

        w.add(step)
        w._run_step(step.step_id)
        w._handle_next_step()

        self.assertEqual(result, [step])

    @mock.patch('trun.worker.time')
    def test_timeout_handler(self, mock_time):
        result = []

        @HangTheWorkerStep.event_handler(Event.TIMEOUT)
        def store_step(t, error_msg):
            self.assertTrue(error_msg)
            result.append(t)

        w = Worker(worker_processes=2, wait_interval=0.01, timeout=5)
        mock_time.time.return_value = 0
        step = HangTheWorkerStep(worker_timeout=1)
        w.add(step)
        w._run_step(step.step_id)

        mock_time.time.return_value = 3
        w._handle_next_step()

        self.assertEqual(result, [step])

    @mock.patch('trun.worker.time')
    def test_timeout_handler_single_worker(self, mock_time):
        result = []

        @HangTheWorkerStep.event_handler(Event.TIMEOUT)
        def store_step(t, error_msg):
            self.assertTrue(error_msg)
            result.append(t)

        w = Worker(wait_interval=0.01, timeout=5)
        mock_time.time.return_value = 0
        step = HangTheWorkerStep(worker_timeout=1)
        w.add(step)
        w._run_step(step.step_id)

        mock_time.time.return_value = 3
        w._handle_next_step()

        self.assertEqual(result, [step])


class PerStepRetryPolicyBehaviorTest(TrunTestCase):
    def setUp(self):
        super(PerStepRetryPolicyBehaviorTest, self).setUp()
        self.per_step_retry_count = 3
        self.default_retry_count = 1
        self.sch = Scheduler(retry_delay=0.1, retry_count=self.default_retry_count, prune_on_get_work=True)

    def test_with_all_disabled_with_single_worker(self):
        """
            With this test, a case which has a step (TestWrapperStep), requires two another steps (TestErrorStep1,TestErrorStep1) which both is failed, is
            tested.

            Step TestErrorStep1 has default retry_count which is 1, but Step TestErrorStep2 has retry_count at step level as 2.

            This test is running on single worker
        """

        class TestErrorStep1(DummyErrorStep):
            pass

        e1 = TestErrorStep1()

        class TestErrorStep2(DummyErrorStep):
            retry_count = self.per_step_retry_count

        e2 = TestErrorStep2()

        class TestWrapperStep(trun.WrapperStep):
            def requires(self):
                return [e2, e1]

        wt = TestWrapperStep()

        with Worker(scheduler=self.sch, worker_id='X', keep_alive=True, wait_interval=0.1, wait_jitter=0.05) as w1:
            self.assertTrue(w1.add(wt))

            self.assertFalse(w1.run())

            self.assertEqual([wt.step_id], list(self.sch.step_list('PENDING', 'UPSTREAM_DISABLED').keys()))

            self.assertEqual(sorted([e1.step_id, e2.step_id]), sorted(self.sch.step_list('DISABLED', '').keys()))

            self.assertEqual(0, self.sch._state.get_step(wt.step_id).num_failures())
            self.assertEqual(self.per_step_retry_count, self.sch._state.get_step(e2.step_id).num_failures())
            self.assertEqual(self.default_retry_count, self.sch._state.get_step(e1.step_id).num_failures())

    def test_with_all_disabled_with_multiple_worker(self):
        """
            With this test, a case which has a step (TestWrapperStep), requires two another steps (TestErrorStep1,TestErrorStep1) which both is failed, is
            tested.

            Step TestErrorStep1 has default retry_count which is 1, but Step TestErrorStep2 has retry_count at step level as 2.

            This test is running on multiple worker
        """

        class TestErrorStep1(DummyErrorStep):
            pass

        e1 = TestErrorStep1()

        class TestErrorStep2(DummyErrorStep):
            retry_count = self.per_step_retry_count

        e2 = TestErrorStep2()

        class TestWrapperStep(trun.WrapperStep):
            def requires(self):
                return [e2, e1]

        wt = TestWrapperStep()

        with Worker(scheduler=self.sch, worker_id='X', keep_alive=True, wait_interval=0.1, wait_jitter=0.05) as w1:
            with Worker(scheduler=self.sch, worker_id='Y', keep_alive=True, wait_interval=0.1, wait_jitter=0.05) as w2:
                with Worker(scheduler=self.sch, worker_id='Z', keep_alive=True, wait_interval=0.1, wait_jitter=0.05) as w3:
                    self.assertTrue(w1.add(wt))
                    self.assertTrue(w2.add(e2))
                    self.assertTrue(w3.add(e1))

                    self.assertFalse(w3.run())
                    self.assertFalse(w2.run())
                    self.assertTrue(w1.run())

                    self.assertEqual([wt.step_id], list(self.sch.step_list('PENDING', 'UPSTREAM_DISABLED').keys()))

                    self.assertEqual(sorted([e1.step_id, e2.step_id]), sorted(self.sch.step_list('DISABLED', '').keys()))

                    self.assertEqual(0, self.sch._state.get_step(wt.step_id).num_failures())
                    self.assertEqual(self.per_step_retry_count, self.sch._state.get_step(e2.step_id).num_failures())
                    self.assertEqual(self.default_retry_count, self.sch._state.get_step(e1.step_id).num_failures())

    def test_with_includes_success_with_single_worker(self):
        """
            With this test, a case which has a step (TestWrapperStep), requires one (TestErrorStep1) FAILED and one (TestSuccessStep1) SUCCESS, is tested.

            Step TestSuccessStep1 will be DONE successfully, but Step TestErrorStep1 will be failed and it has retry_count at step level as 2.

            This test is running on single worker
        """

        class TestSuccessStep1(DummyStep):
            pass

        s1 = TestSuccessStep1()

        class TestErrorStep1(DummyErrorStep):
            retry_count = self.per_step_retry_count

        e1 = TestErrorStep1()

        class TestWrapperStep(trun.WrapperStep):
            def requires(self):
                return [e1, s1]

        wt = TestWrapperStep()

        with Worker(scheduler=self.sch, worker_id='X', keep_alive=True, wait_interval=0.1, wait_jitter=0.05) as w1:
            self.assertTrue(w1.add(wt))

            self.assertFalse(w1.run())

            self.assertEqual([wt.step_id], list(self.sch.step_list('PENDING', 'UPSTREAM_DISABLED').keys()))
            self.assertEqual([e1.step_id], list(self.sch.step_list('DISABLED', '').keys()))
            self.assertEqual([s1.step_id], list(self.sch.step_list('DONE', '').keys()))

            self.assertEqual(0, self.sch._state.get_step(wt.step_id).num_failures())
            self.assertEqual(self.per_step_retry_count, self.sch._state.get_step(e1.step_id).num_failures())
            self.assertEqual(0, self.sch._state.get_step(s1.step_id).num_failures())

    def test_with_includes_success_with_multiple_worker(self):
        """
            With this test, a case which has a step (TestWrapperStep), requires one (TestErrorStep1) FAILED and one (TestSuccessStep1) SUCCESS, is tested.

            Step TestSuccessStep1 will be DONE successfully, but Step TestErrorStep1 will be failed and it has retry_count at step level as 2.

            This test is running on multiple worker
        """

        class TestSuccessStep1(DummyStep):
            pass

        s1 = TestSuccessStep1()

        class TestErrorStep1(DummyErrorStep):
            retry_count = self.per_step_retry_count

        e1 = TestErrorStep1()

        class TestWrapperStep(trun.WrapperStep):
            def requires(self):
                return [e1, s1]

        wt = TestWrapperStep()

        with Worker(scheduler=self.sch, worker_id='X', keep_alive=True, wait_interval=0.1, wait_jitter=0.05) as w1:
            with Worker(scheduler=self.sch, worker_id='Y', keep_alive=True, wait_interval=0.1, wait_jitter=0.05) as w2:
                with Worker(scheduler=self.sch, worker_id='Z', keep_alive=True, wait_interval=0.1, wait_jitter=0.05) as w3:
                    self.assertTrue(w1.add(wt))
                    self.assertTrue(w2.add(e1))
                    self.assertTrue(w3.add(s1))

                    self.assertTrue(w3.run())
                    self.assertFalse(w2.run())
                    self.assertTrue(w1.run())

                    self.assertEqual([wt.step_id], list(self.sch.step_list('PENDING', 'UPSTREAM_DISABLED').keys()))
                    self.assertEqual([e1.step_id], list(self.sch.step_list('DISABLED', '').keys()))
                    self.assertEqual([s1.step_id], list(self.sch.step_list('DONE', '').keys()))

                    self.assertEqual(0, self.sch._state.get_step(wt.step_id).num_failures())
                    self.assertEqual(self.per_step_retry_count, self.sch._state.get_step(e1.step_id).num_failures())
                    self.assertEqual(0, self.sch._state.get_step(s1.step_id).num_failures())

    def test_with_dynamic_dependencies_with_single_worker(self):
        """
            With this test, a case includes dependency steps(TestErrorStep1,TestErrorStep2) which both are failed.

            Step TestErrorStep1 has default retry_count which is 1, but Step TestErrorStep2 has retry_count at step level as 2.

            This test is running on single worker
        """

        class TestErrorStep1(DummyErrorStep):
            pass

        e1 = TestErrorStep1()

        class TestErrorStep2(DummyErrorStep):
            retry_count = self.per_step_retry_count

        e2 = TestErrorStep2()

        class TestSuccessStep1(DummyStep):
            pass

        s1 = TestSuccessStep1()

        class TestWrapperStep(DummyStep):
            def requires(self):
                return [s1]

            def run(self):
                super(TestWrapperStep, self).run()
                yield e2, e1

        wt = TestWrapperStep()

        with Worker(scheduler=self.sch, worker_id='X', keep_alive=True, wait_interval=0.1, wait_jitter=0.05) as w1:
            self.assertTrue(w1.add(wt))

            self.assertFalse(w1.run())

            self.assertEqual([wt.step_id], list(self.sch.step_list('PENDING', 'UPSTREAM_DISABLED').keys()))

            self.assertEqual(sorted([e1.step_id, e2.step_id]), sorted(self.sch.step_list('DISABLED', '').keys()))

            self.assertEqual(0, self.sch._state.get_step(wt.step_id).num_failures())
            self.assertEqual(0, self.sch._state.get_step(s1.step_id).num_failures())
            self.assertEqual(self.per_step_retry_count, self.sch._state.get_step(e2.step_id).num_failures())
            self.assertEqual(self.default_retry_count, self.sch._state.get_step(e1.step_id).num_failures())

    def test_with_dynamic_dependencies_with_multiple_workers(self):
        """
            With this test, a case includes dependency steps(TestErrorStep1,TestErrorStep2) which both are failed.

            Step TestErrorStep1 has default retry_count which is 1, but Step TestErrorStep2 has retry_count at step level as 2.

            This test is running on multiple worker
        """

        class TestErrorStep1(DummyErrorStep):
            pass

        e1 = TestErrorStep1()

        class TestErrorStep2(DummyErrorStep):
            retry_count = self.per_step_retry_count

        e2 = TestErrorStep2()

        class TestSuccessStep1(DummyStep):
            pass

        s1 = TestSuccessStep1()

        class TestWrapperStep(DummyStep):
            def requires(self):
                return [s1]

            def run(self):
                super(TestWrapperStep, self).run()
                yield e2, e1

        wt = TestWrapperStep()

        with Worker(scheduler=self.sch, worker_id='X', keep_alive=True, wait_interval=0.1, wait_jitter=0.05) as w1:
            with Worker(scheduler=self.sch, worker_id='Y', keep_alive=True, wait_interval=0.1, wait_jitter=0.05) as w2:
                self.assertTrue(w1.add(wt))
                self.assertTrue(w2.add(s1))

                self.assertTrue(w2.run())
                self.assertFalse(w1.run())

                self.assertEqual([wt.step_id], list(self.sch.step_list('PENDING', 'UPSTREAM_DISABLED').keys()))

                self.assertEqual(sorted([e1.step_id, e2.step_id]), sorted(self.sch.step_list('DISABLED', '').keys()))

                self.assertEqual(0, self.sch._state.get_step(wt.step_id).num_failures())
                self.assertEqual(0, self.sch._state.get_step(s1.step_id).num_failures())
                self.assertEqual(self.per_step_retry_count, self.sch._state.get_step(e2.step_id).num_failures())
                self.assertEqual(self.default_retry_count, self.sch._state.get_step(e1.step_id).num_failures())

    def test_per_step_disable_persist_with_single_worker(self):
        """
        Ensure that `Step.disable_window` impacts the step retrying policy:
        - with the scheduler retry policy (disable_window=3), step fails twice and gets disabled
        - with the step retry policy (disable_window=0.5) step never gets into the DISABLED state
        """
        class TwoErrorsThenSuccessStep(Step):
            """
            The step is failing two times and then succeeds, waiting 1s before each try
            """
            retry_index = 0
            disable_window = None

            def run(self):
                time.sleep(1)
                self.retry_index += 1
                if self.retry_index < 3:
                    raise Exception("Retry index is %s for %s" % (self.retry_index, self.step_family))

        t = TwoErrorsThenSuccessStep()

        sch = Scheduler(retry_delay=0.1, retry_count=2, prune_on_get_work=True, disable_window=2)
        with Worker(scheduler=sch, worker_id='X', keep_alive=True, wait_interval=0.1, wait_jitter=0.05) as w:
            self.assertTrue(w.add(t))
            self.assertFalse(w.run())

            self.assertEqual(2, t.retry_index)
            self.assertEqual([t.step_id], list(sch.step_list('DISABLED').keys()))
            self.assertEqual(2, sch._state.get_step(t.step_id).num_failures())

        t = TwoErrorsThenSuccessStep()
        t.retry_index = 0
        t.disable_window = 0.5

        sch = Scheduler(retry_delay=0.1, retry_count=2, prune_on_get_work=True, disable_window=2)
        with Worker(scheduler=sch, worker_id='X', keep_alive=True, wait_interval=0.1, wait_jitter=0.05) as w:
            self.assertTrue(w.add(t))
            # Worker.run return False even if a step failed first but eventually succeeded.
            self.assertFalse(w.run())

            self.assertEqual(3, t.retry_index)
            self.assertEqual([t.step_id], list(sch.step_list('DONE').keys()))
            self.assertEqual(1, len(sch._state.get_step(t.step_id).failures))
