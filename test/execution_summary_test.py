# -*- coding: utf-8 -*-
#
# Copyright 2015-2015 Spotify AB
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

from helpers import TrunTestCase, RunOnceStep, with_config

import trun
import trun.worker
import trun.execution_summary
import threading
import datetime
import mock
from enum import Enum


class ExecutionSummaryTest(TrunTestCase):

    def setUp(self):
        super(ExecutionSummaryTest, self).setUp()
        self.scheduler = trun.scheduler.Scheduler(prune_on_get_work=False)
        self.worker = trun.worker.Worker(scheduler=self.scheduler)

    def run_step(self, step):
        self.worker.add(step)  # schedule
        self.worker.run()  # run

    def summary_dict(self):
        return trun.execution_summary._summary_dict(self.worker)

    def summary(self):
        return trun.execution_summary.summary(self.worker)

    def test_all_statuses(self):
        class Bar(trun.Step):
            num = trun.IntParameter()

            def run(self):
                if self.num == 0:
                    raise ValueError()

            def complete(self):
                if self.num == 1:
                    return True
                return False

        class Foo(trun.Step):
            def requires(self):
                for i in range(5):
                    yield Bar(i)

        self.run_step(Foo())
        d = self.summary_dict()
        self.assertEqual({Bar(num=1)}, d['already_done'])
        self.assertEqual({Bar(num=2), Bar(num=3), Bar(num=4)}, d['completed'])
        self.assertEqual({Bar(num=0)}, d['failed'])
        self.assertEqual({Foo()}, d['upstream_failure'])
        self.assertFalse(d['upstream_missing_dependency'])
        self.assertFalse(d['run_by_other_worker'])
        self.assertFalse(d['still_pending_ext'])
        summary = self.summary()

        expected = ['',
                    '===== Trun Execution Summary =====',
                    '',
                    'Scheduled 6 steps of which:',
                    '* 1 complete ones were encountered:',
                    '    - 1 Bar(num=1)',
                    '* 3 ran successfully:',
                    '    - 3 Bar(num=2,3,4)',
                    '* 1 failed:',
                    '    - 1 Bar(num=0)',
                    '* 1 were left pending, among these:',
                    '    * 1 had failed dependencies:',
                    '        - 1 Foo()',
                    '',
                    'This progress looks :( because there were failed steps',
                    '',
                    '===== Trun Execution Summary =====',
                    '']
        result = summary.split('\n')
        self.assertEqual(len(result), len(expected))
        for i, line in enumerate(result):
            self.assertEqual(line, expected[i])

    def test_batch_complete(self):
        ran_steps = set()

        class MaxBatchStep(trun.Step):
            param = trun.IntParameter(batch_method=max)

            def run(self):
                ran_steps.add(self.param)

            def complete(self):
                return any(self.param <= ran_param for ran_param in ran_steps)

        class MaxBatches(trun.WrapperStep):
            def requires(self):
                return map(MaxBatchStep, range(5))

        self.run_step(MaxBatches())
        d = self.summary_dict()
        expected_completed = {
            MaxBatchStep(0),
            MaxBatchStep(1),
            MaxBatchStep(2),
            MaxBatchStep(3),
            MaxBatchStep(4),
            MaxBatches(),
        }
        self.assertEqual(expected_completed, d['completed'])

    def test_batch_fail(self):
        class MaxBatchFailStep(trun.Step):
            param = trun.IntParameter(batch_method=max)

            def run(self):
                assert self.param < 4

            def complete(self):
                return False

        class MaxBatches(trun.WrapperStep):
            def requires(self):
                return map(MaxBatchFailStep, range(5))

        self.run_step(MaxBatches())
        d = self.summary_dict()
        expected_failed = {
            MaxBatchFailStep(0),
            MaxBatchFailStep(1),
            MaxBatchFailStep(2),
            MaxBatchFailStep(3),
            MaxBatchFailStep(4),
        }
        self.assertEqual(expected_failed, d['failed'])

    def test_check_complete_error(self):
        class Bar(trun.Step):
            def run(self):
                pass

            def complete(self):
                raise Exception
                return True

        class Foo(trun.Step):
            def requires(self):
                yield Bar()

        self.run_step(Foo())
        d = self.summary_dict()
        self.assertEqual({Foo()}, d['still_pending_not_ext'])
        self.assertEqual({Foo()}, d['upstream_scheduling_error'])
        self.assertEqual({Bar()}, d['scheduling_error'])
        self.assertFalse(d['not_run'])
        self.assertFalse(d['already_done'])
        self.assertFalse(d['completed'])
        self.assertFalse(d['failed'])
        self.assertFalse(d['upstream_failure'])
        self.assertFalse(d['upstream_missing_dependency'])
        self.assertFalse(d['run_by_other_worker'])
        self.assertFalse(d['still_pending_ext'])
        summary = self.summary()
        expected = ['',
                    '===== Trun Execution Summary =====',
                    '',
                    'Scheduled 2 steps of which:',
                    '* 1 failed scheduling:',
                    '    - 1 Bar()',
                    '* 1 were left pending, among these:',
                    "    * 1 had dependencies whose scheduling failed:",
                    '        - 1 Foo()',
                    '',
                    'Did not run any steps',
                    'This progress looks :( because there were steps whose scheduling failed',
                    '',
                    '===== Trun Execution Summary =====',
                    '']
        result = summary.split('\n')
        self.assertEqual(len(result), len(expected))
        for i, line in enumerate(result):
            self.assertEqual(line, expected[i])

    def test_not_run_error(self):
        class Bar(trun.Step):
            def complete(self):
                return True

        class Foo(trun.Step):
            def requires(self):
                yield Bar()

        def new_func(*args, **kwargs):
            return None

        with mock.patch('trun.scheduler.Scheduler.add_step', new_func):
            self.run_step(Foo())

        d = self.summary_dict()
        self.assertEqual({Foo()}, d['still_pending_not_ext'])
        self.assertEqual({Foo()}, d['not_run'])
        self.assertEqual({Bar()}, d['already_done'])
        self.assertFalse(d['upstream_scheduling_error'])
        self.assertFalse(d['scheduling_error'])
        self.assertFalse(d['completed'])
        self.assertFalse(d['failed'])
        self.assertFalse(d['upstream_failure'])
        self.assertFalse(d['upstream_missing_dependency'])
        self.assertFalse(d['run_by_other_worker'])
        self.assertFalse(d['still_pending_ext'])
        summary = self.summary()
        expected = ['',
                    '===== Trun Execution Summary =====',
                    '',
                    'Scheduled 2 steps of which:',
                    '* 1 complete ones were encountered:',
                    '    - 1 Bar()',
                    '* 1 were left pending, among these:',
                    "    * 1 was not granted run permission by the scheduler:",
                    '        - 1 Foo()',
                    '',
                    'Did not run any steps',
                    'This progress looks :| because there were steps that were not granted run permission by the scheduler',
                    '',
                    '===== Trun Execution Summary =====',
                    '']
        result = summary.split('\n')
        self.assertEqual(len(result), len(expected))
        for i, line in enumerate(result):
            self.assertEqual(line, expected[i])

    def test_deps_error(self):
        class Bar(trun.Step):
            def run(self):
                pass

            def complete(self):
                return True

        class Foo(trun.Step):
            def requires(self):
                raise Exception
                yield Bar()

        self.run_step(Foo())
        d = self.summary_dict()
        self.assertEqual({Foo()}, d['scheduling_error'])
        self.assertFalse(d['upstream_scheduling_error'])
        self.assertFalse(d['not_run'])
        self.assertFalse(d['already_done'])
        self.assertFalse(d['completed'])
        self.assertFalse(d['failed'])
        self.assertFalse(d['upstream_failure'])
        self.assertFalse(d['upstream_missing_dependency'])
        self.assertFalse(d['run_by_other_worker'])
        self.assertFalse(d['still_pending_ext'])
        summary = self.summary()
        expected = ['',
                    '===== Trun Execution Summary =====',
                    '',
                    'Scheduled 1 steps of which:',
                    '* 1 failed scheduling:',
                    '    - 1 Foo()',
                    '',
                    'Did not run any steps',
                    'This progress looks :( because there were steps whose scheduling failed',
                    '',
                    '===== Trun Execution Summary =====',
                    '']
        result = summary.split('\n')
        self.assertEqual(len(result), len(expected))
        for i, line in enumerate(result):
            self.assertEqual(line, expected[i])

    @with_config({'execution_summary': {'summary_length': '1'}})
    def test_config_summary_limit(self):
        class Bar(trun.Step):
            num = trun.IntParameter()

            def run(self):
                pass

            def complete(self):
                return True

        class Biz(Bar):
            pass

        class Bat(Bar):
            pass

        class Wut(Bar):
            pass

        class Foo(trun.Step):
            def requires(self):
                yield Bat(1)
                yield Wut(1)
                yield Biz(1)
                for i in range(4):
                    yield Bar(i)

            def complete(self):
                return False

        self.run_step(Foo())
        d = self.summary_dict()
        self.assertEqual({Bat(1), Wut(1), Biz(1), Bar(0), Bar(1), Bar(2), Bar(3)}, d['already_done'])
        self.assertEqual({Foo()}, d['completed'])
        self.assertFalse(d['failed'])
        self.assertFalse(d['upstream_failure'])
        self.assertFalse(d['upstream_missing_dependency'])
        self.assertFalse(d['run_by_other_worker'])
        self.assertFalse(d['still_pending_ext'])
        summary = self.summary()
        expected = ['',
                    '===== Trun Execution Summary =====',
                    '',
                    'Scheduled 8 steps of which:',
                    '* 7 complete ones were encountered:',
                    '    - 4 Bar(num=0...3)',
                    '    ...',
                    '* 1 ran successfully:',
                    '    - 1 Foo()',
                    '',
                    'This progress looks :) because there were no failed steps or missing dependencies',
                    '',
                    '===== Trun Execution Summary =====',
                    '']
        result = summary.split('\n')
        self.assertEqual(len(result), len(expected))
        for i, line in enumerate(result):
            self.assertEqual(line, expected[i])

    def test_upstream_not_running(self):
        class ExternalBar(trun.ExternalStep):
            num = trun.IntParameter()

            def complete(self):
                if self.num == 1:
                    return True
                return False

        class Bar(trun.Step):
            num = trun.IntParameter()

            def run(self):
                if self.num == 0:
                    raise ValueError()

        class Foo(trun.Step):
            def requires(self):
                for i in range(5):
                    yield ExternalBar(i)
                    yield Bar(i)

        self.run_step(Foo())
        d = self.summary_dict()
        self.assertEqual({ExternalBar(num=1)}, d['already_done'])
        self.assertEqual({Bar(num=1), Bar(num=2), Bar(num=3), Bar(num=4)}, d['completed'])
        self.assertEqual({Bar(num=0)}, d['failed'])
        self.assertEqual({Foo()}, d['upstream_failure'])
        self.assertEqual({Foo()}, d['upstream_missing_dependency'])
        self.assertFalse(d['run_by_other_worker'])
        self.assertEqual({ExternalBar(num=0), ExternalBar(num=2), ExternalBar(num=3), ExternalBar(num=4)}, d['still_pending_ext'])
        s = self.summary()
        self.assertIn('\n* 1 complete ones were encountered:\n    - 1 ExternalBar(num=1)\n', s)
        self.assertIn('\n* 4 ran successfully:\n    - 4 Bar(num=1...4)\n', s)
        self.assertIn('\n* 1 failed:\n    - 1 Bar(num=0)\n', s)
        self.assertIn('\n* 5 were left pending, among these:\n    * 4 were missing external dependencies:\n        - 4 ExternalBar(num=', s)
        self.assertIn('\n    * 1 had failed dependencies:\n'
                      '        - 1 Foo()\n'
                      '    * 1 had missing dependencies:\n'
                      '        - 1 Foo()\n\n'
                      'This progress looks :( because there were failed steps\n', s)
        self.assertNotIn('\n\n\n', s)

    def test_already_running(self):
        lock1 = threading.Lock()
        lock2 = threading.Lock()

        class ParentStep(RunOnceStep):

            def requires(self):
                yield LockStep()

        class LockStep(RunOnceStep):
            def run(self):
                lock2.release()
                lock1.acquire()
                self.comp = True

        lock1.acquire()
        lock2.acquire()
        other_worker = trun.worker.Worker(scheduler=self.scheduler, worker_id="other_worker")
        other_worker.add(ParentStep())
        t1 = threading.Thread(target=other_worker.run)
        t1.start()
        lock2.acquire()
        self.run_step(ParentStep())
        lock1.release()
        t1.join()
        d = self.summary_dict()
        self.assertEqual({LockStep()}, d['run_by_other_worker'])
        self.assertEqual({ParentStep()}, d['upstream_run_by_other_worker'])
        s = self.summary()
        self.assertIn('\nScheduled 2 steps of which:\n'
                      '* 2 were left pending, among these:\n'
                      '    * 1 were being run by another worker:\n'
                      '        - 1 LockStep()\n'
                      '    * 1 had dependencies that were being run by other worker:\n'
                      '        - 1 ParentStep()\n', s)
        self.assertIn('\n\nThe other workers were:\n'
                      '    - other_worker ran 1 steps\n\n'
                      'Did not run any steps\n'
                      'This progress looks :) because there were no failed '
                      'steps or missing dependencies\n', s)
        self.assertNotIn('\n\n\n', s)

    def test_already_running_2(self):
        class AlreadyRunningStep(trun.Step):
            def run(self):
                pass

        other_worker = trun.worker.Worker(scheduler=self.scheduler, worker_id="other_worker")
        other_worker.add(AlreadyRunningStep())  # This also registers this worker
        old_func = trun.scheduler.Scheduler.get_work

        def new_func(*args, **kwargs):
            new_kwargs = kwargs.copy()
            new_kwargs['worker'] = 'other_worker'
            old_func(*args, **new_kwargs)
            return old_func(*args, **kwargs)

        with mock.patch('trun.scheduler.Scheduler.get_work', new_func):
            self.run_step(AlreadyRunningStep())

        d = self.summary_dict()
        self.assertFalse(d['already_done'])
        self.assertFalse(d['completed'])
        self.assertFalse(d['not_run'])
        self.assertEqual({AlreadyRunningStep()}, d['run_by_other_worker'])

    def test_not_run(self):
        class AlreadyRunningStep(trun.Step):
            def run(self):
                pass

        other_worker = trun.worker.Worker(scheduler=self.scheduler, worker_id="other_worker")
        other_worker.add(AlreadyRunningStep())  # This also registers this worker
        old_func = trun.scheduler.Scheduler.get_work

        def new_func(*args, **kwargs):
            kwargs['current_steps'] = None
            old_func(*args, **kwargs)
            return old_func(*args, **kwargs)

        with mock.patch('trun.scheduler.Scheduler.get_work', new_func):
            self.run_step(AlreadyRunningStep())

        d = self.summary_dict()
        self.assertFalse(d['already_done'])
        self.assertFalse(d['completed'])
        self.assertFalse(d['run_by_other_worker'])
        self.assertEqual({AlreadyRunningStep()}, d['not_run'])

        s = self.summary()
        self.assertIn('\nScheduled 1 steps of which:\n'
                      '* 1 were left pending, among these:\n'
                      '    * 1 was not granted run permission by the scheduler:\n'
                      '        - 1 AlreadyRunningStep()\n', s)
        self.assertNotIn('\n\n\n', s)

    def test_somebody_else_finish_step(self):
        class SomeStep(RunOnceStep):
            pass

        other_worker = trun.worker.Worker(scheduler=self.scheduler, worker_id="other_worker")

        self.worker.add(SomeStep())
        other_worker.add(SomeStep())
        other_worker.run()
        self.worker.run()

        d = self.summary_dict()
        self.assertFalse(d['already_done'])
        self.assertFalse(d['completed'])
        self.assertFalse(d['run_by_other_worker'])
        self.assertEqual({SomeStep()}, d['not_run'])

    def test_somebody_else_disables_step(self):
        class SomeStep(trun.Step):
            def complete(self):
                return False

            def run(self):
                raise ValueError()

        other_worker = trun.worker.Worker(scheduler=self.scheduler, worker_id="other_worker")

        self.worker.add(SomeStep())
        other_worker.add(SomeStep())
        other_worker.run()  # Assuming it is disabled for a while after this
        self.worker.run()

        d = self.summary_dict()
        self.assertFalse(d['already_done'])
        self.assertFalse(d['completed'])
        self.assertFalse(d['run_by_other_worker'])
        self.assertEqual({SomeStep()}, d['not_run'])

    def test_larger_tree(self):

        class Dog(RunOnceStep):
            def requires(self):
                yield Cat(2)

        class Cat(trun.Step):
            num = trun.IntParameter()

            def __init__(self, *args, **kwargs):
                super(Cat, self).__init__(*args, **kwargs)
                self.comp = False

            def run(self):
                if self.num == 2:
                    raise ValueError()
                self.comp = True

            def complete(self):
                if self.num == 1:
                    return True
                else:
                    return self.comp

        class Bar(RunOnceStep):
            num = trun.IntParameter()

            def requires(self):
                if self.num == 0:
                    yield ExternalBar()
                    yield Cat(0)
                if self.num == 1:
                    yield Cat(0)
                    yield Cat(1)
                if self.num == 2:
                    yield Dog()

        class Foo(trun.Step):
            def requires(self):
                for i in range(3):
                    yield Bar(i)

        class ExternalBar(trun.ExternalStep):

            def complete(self):
                return False

        self.run_step(Foo())
        d = self.summary_dict()

        self.assertEqual({Cat(num=1)}, d['already_done'])
        self.assertEqual({Cat(num=0), Bar(num=1)}, d['completed'])
        self.assertEqual({Cat(num=2)}, d['failed'])
        self.assertEqual({Dog(), Bar(num=2), Foo()}, d['upstream_failure'])
        self.assertEqual({Bar(num=0), Foo()}, d['upstream_missing_dependency'])
        self.assertFalse(d['run_by_other_worker'])
        self.assertEqual({ExternalBar()}, d['still_pending_ext'])
        s = self.summary()
        self.assertNotIn('\n\n\n', s)

    def test_with_dates(self):
        """ Just test that it doesn't crash with date params """

        start = datetime.date(1998, 3, 23)

        class Bar(RunOnceStep):
            date = trun.DateParameter()

        class Foo(trun.Step):
            def requires(self):
                for i in range(10):
                    new_date = start + datetime.timedelta(days=i)
                    yield Bar(date=new_date)

        self.run_step(Foo())
        d = self.summary_dict()
        exp_set = {Bar(start + datetime.timedelta(days=i)) for i in range(10)}
        exp_set.add(Foo())
        self.assertEqual(exp_set, d['completed'])
        s = self.summary()
        self.assertIn('date=1998-0', s)
        self.assertIn('Scheduled 11 steps', s)
        self.assertIn('Trun Execution Summary', s)
        self.assertNotIn('00:00:00', s)
        self.assertNotIn('\n\n\n', s)

    def test_with_ranges_minutes(self):

        start = datetime.datetime(1998, 3, 23, 1, 50)

        class Bar(RunOnceStep):
            time = trun.DateMinuteParameter()

        class Foo(trun.Step):
            def requires(self):
                for i in range(300):
                    new_time = start + datetime.timedelta(minutes=i)
                    yield Bar(time=new_time)

        self.run_step(Foo())
        d = self.summary_dict()
        exp_set = {Bar(start + datetime.timedelta(minutes=i)) for i in range(300)}
        exp_set.add(Foo())
        self.assertEqual(exp_set, d['completed'])
        s = self.summary()
        self.assertIn('Bar(time=1998-03-23T0150...1998-03-23T0649)', s)
        self.assertNotIn('\n\n\n', s)

    def test_with_ranges_one_param(self):

        class Bar(RunOnceStep):
            num = trun.IntParameter()

        class Foo(trun.Step):
            def requires(self):
                for i in range(11):
                    yield Bar(i)

        self.run_step(Foo())
        d = self.summary_dict()
        exp_set = {Bar(i) for i in range(11)}
        exp_set.add(Foo())
        self.assertEqual(exp_set, d['completed'])
        s = self.summary()
        self.assertIn('Bar(num=0...10)', s)
        self.assertNotIn('\n\n\n', s)

    def test_with_ranges_multiple_params(self):

        class Bar(RunOnceStep):
            num1 = trun.IntParameter()
            num2 = trun.IntParameter()
            num3 = trun.IntParameter()

        class Foo(trun.Step):
            def requires(self):
                for i in range(5):
                    yield Bar(5, i, 25)

        self.run_step(Foo())
        d = self.summary_dict()
        exp_set = {Bar(5, i, 25) for i in range(5)}
        exp_set.add(Foo())
        self.assertEqual(exp_set, d['completed'])
        s = self.summary()
        self.assertIn('- 5 Bar(num1=5, num2=0...4, num3=25)', s)
        self.assertNotIn('\n\n\n', s)

    def test_with_two_steps(self):

        class Bar(RunOnceStep):
            num = trun.IntParameter()
            num2 = trun.IntParameter()

        class Foo(trun.Step):
            def requires(self):
                for i in range(2):
                    yield Bar(i, 2 * i)

        self.run_step(Foo())
        d = self.summary_dict()
        self.assertEqual({Foo(), Bar(num=0, num2=0), Bar(num=1, num2=2)}, d['completed'])

        summary = self.summary()
        result = summary.split('\n')
        expected = ['',
                    '===== Trun Execution Summary =====',
                    '',
                    'Scheduled 3 steps of which:',
                    '* 3 ran successfully:',
                    '    - 2 Bar(num=0, num2=0) and Bar(num=1, num2=2)',
                    '    - 1 Foo()',
                    '',
                    'This progress looks :) because there were no failed steps or missing dependencies',
                    '',
                    '===== Trun Execution Summary =====',
                    '']

        self.assertEqual(len(result), len(expected))
        for i, line in enumerate(result):
            self.assertEqual(line, expected[i])

    def test_really_long_param_name(self):

        class Bar(RunOnceStep):
            This_is_a_really_long_parameter_that_we_should_not_print_out_because_people_will_get_annoyed = trun.IntParameter()

        class Foo(trun.Step):
            def requires(self):
                yield Bar(0)

        self.run_step(Foo())
        s = self.summary()
        self.assertIn('Bar(...)', s)
        self.assertNotIn("Did not run any steps", s)
        self.assertNotIn('\n\n\n', s)

    def test_multiple_params_multiple_same_step_family(self):

        class Bar(RunOnceStep):
            num = trun.IntParameter()
            num2 = trun.IntParameter()

        class Foo(trun.Step):
            def requires(self):
                for i in range(4):
                    yield Bar(i, 2 * i)

        self.run_step(Foo())
        summary = self.summary()

        result = summary.split('\n')
        expected = ['',
                    '===== Trun Execution Summary =====',
                    '',
                    'Scheduled 5 steps of which:',
                    '* 5 ran successfully:',
                    '    - 4 Bar(num=0, num2=0) ...',
                    '    - 1 Foo()',
                    '',
                    'This progress looks :) because there were no failed steps or missing dependencies',
                    '',
                    '===== Trun Execution Summary =====',
                    '']

        self.assertEqual(len(result), len(expected))
        for i, line in enumerate(result):
            self.assertEqual(line, expected[i])

    def test_happy_smiley_face_normal(self):

        class Bar(RunOnceStep):
            num = trun.IntParameter()
            num2 = trun.IntParameter()

        class Foo(trun.Step):
            def requires(self):
                for i in range(4):
                    yield Bar(i, 2 * i)

        self.run_step(Foo())
        s = self.summary()
        self.assertIn('\nThis progress looks :) because there were no failed steps or missing dependencies', s)
        self.assertNotIn("Did not run any steps", s)
        self.assertNotIn('\n\n\n', s)

    def test_happy_smiley_face_other_workers(self):
        lock1 = threading.Lock()
        lock2 = threading.Lock()

        class ParentStep(RunOnceStep):

            def requires(self):
                yield LockStep()

        class LockStep(RunOnceStep):

            def run(self):
                lock2.release()
                lock1.acquire()
                self.comp = True

        lock1.acquire()
        lock2.acquire()
        other_worker = trun.worker.Worker(scheduler=self.scheduler, worker_id="other_worker")
        other_worker.add(ParentStep())
        t1 = threading.Thread(target=other_worker.run)
        t1.start()
        lock2.acquire()
        self.run_step(ParentStep())
        lock1.release()
        t1.join()
        s = self.summary()
        self.assertIn('\nThis progress looks :) because there were no failed steps or missing dependencies', s)
        self.assertNotIn('\n\n\n', s)

    def test_sad_smiley_face(self):

        class ExternalBar(trun.ExternalStep):

            def complete(self):
                return False

        class Bar(trun.Step):
            num = trun.IntParameter()

            def run(self):
                if self.num == 0:
                    raise ValueError()

        class Foo(trun.Step):
            def requires(self):
                for i in range(5):
                    yield Bar(i)
                yield ExternalBar()

        self.run_step(Foo())
        s = self.summary()
        self.assertIn('\nThis progress looks :( because there were failed steps', s)
        self.assertNotIn("Did not run any steps", s)
        self.assertNotIn('\n\n\n', s)

    def test_neutral_smiley_face(self):

        class ExternalBar(trun.ExternalStep):

            def complete(self):
                return False

        class Foo(trun.Step):
            def requires(self):
                yield ExternalBar()

        self.run_step(Foo())
        s = self.summary()
        self.assertIn('\nThis progress looks :| because there were missing external dependencies', s)
        self.assertNotIn('\n\n\n', s)

    def test_did_not_run_any_steps(self):

        class ExternalBar(trun.ExternalStep):
            num = trun.IntParameter()

            def complete(self):
                if self.num == 5:
                    return True
                return False

        class Foo(trun.Step):

            def requires(self):
                for i in range(10):
                    yield ExternalBar(i)

        self.run_step(Foo())
        d = self.summary_dict()
        self.assertEqual({ExternalBar(5)}, d['already_done'])
        self.assertEqual({ExternalBar(i) for i in range(10) if i != 5}, d['still_pending_ext'])
        self.assertEqual({Foo()}, d['upstream_missing_dependency'])
        s = self.summary()
        self.assertIn('\n\nDid not run any steps\nThis progress looks :| because there were missing external dependencies', s)
        self.assertNotIn('\n\n\n', s)

    def test_example(self):

        class MyExternal(trun.ExternalStep):

            def complete(self):
                return False

        class Boom(trun.Step):
            this_is_a_really_long_I_mean_way_too_long_and_annoying_parameter = trun.IntParameter()

            def requires(self):
                for i in range(5, 200):
                    yield Bar(i)

        class Foo(trun.Step):
            num = trun.IntParameter()
            num2 = trun.IntParameter()

            def requires(self):
                yield MyExternal()
                yield Boom(0)

        class Bar(trun.Step):
            num = trun.IntParameter()

            def complete(self):
                return True

        class DateStep(trun.Step):
            date = trun.DateParameter()
            num = trun.IntParameter()

            def requires(self):
                yield MyExternal()
                yield Boom(0)

        class EntryPoint(trun.Step):

            def requires(self):
                for i in range(10):
                    yield Foo(100, 2 * i)
                for i in range(10):
                    yield DateStep(datetime.date(1998, 3, 23) + datetime.timedelta(days=i), 5)

        self.run_step(EntryPoint())
        summary = self.summary()

        expected = ['',
                    '===== Trun Execution Summary =====',
                    '',
                    'Scheduled 218 steps of which:',
                    '* 195 complete ones were encountered:',
                    '    - 195 Bar(num=5...199)',
                    '* 1 ran successfully:',
                    '    - 1 Boom(...)',
                    '* 22 were left pending, among these:',
                    '    * 1 were missing external dependencies:',
                    '        - 1 MyExternal()',
                    '    * 21 had missing dependencies:',
                    '        - 10 DateStep(date=1998-03-23...1998-04-01, num=5)',
                    '        - 1 EntryPoint()',
                    '        - 10 Foo(num=100, num2=0) ...',
                    '',
                    'This progress looks :| because there were missing external dependencies',
                    '',
                    '===== Trun Execution Summary =====',
                    '']
        result = summary.split('\n')

        self.assertEqual(len(result), len(expected))
        for i, line in enumerate(result):
            self.assertEqual(line, expected[i])

    def test_with_datehours(self):
        """ Just test that it doesn't crash with datehour params """

        start = datetime.datetime(1998, 3, 23, 5)

        class Bar(RunOnceStep):
            datehour = trun.DateHourParameter()

        class Foo(trun.Step):
            def requires(self):
                for i in range(10):
                    new_date = start + datetime.timedelta(hours=i)
                    yield Bar(datehour=new_date)

        self.run_step(Foo())
        d = self.summary_dict()
        exp_set = {Bar(start + datetime.timedelta(hours=i)) for i in range(10)}
        exp_set.add(Foo())
        self.assertEqual(exp_set, d['completed'])
        s = self.summary()
        self.assertIn('datehour=1998-03-23T0', s)
        self.assertIn('Scheduled 11 steps', s)
        self.assertIn('Trun Execution Summary', s)
        self.assertNotIn('00:00:00', s)
        self.assertNotIn('\n\n\n', s)

    def test_with_months(self):
        """ Just test that it doesn't crash with month params """

        start = datetime.datetime(1998, 3, 23)

        class Bar(RunOnceStep):
            month = trun.MonthParameter()

        class Foo(trun.Step):
            def requires(self):
                for i in range(3):
                    new_date = start + datetime.timedelta(days=30*i)
                    yield Bar(month=new_date)

        self.run_step(Foo())
        d = self.summary_dict()
        exp_set = {Bar(start + datetime.timedelta(days=30*i)) for i in range(3)}
        exp_set.add(Foo())
        self.assertEqual(exp_set, d['completed'])
        s = self.summary()
        self.assertIn('month=1998-0', s)
        self.assertIn('Scheduled 4 steps', s)
        self.assertIn('Trun Execution Summary', s)
        self.assertNotIn('00:00:00', s)
        self.assertNotIn('\n\n\n', s)

    def test_multiple_dash_dash_workers(self):
        """
        Don't print own worker with ``--workers 2`` setting.
        """
        self.worker = trun.worker.Worker(scheduler=self.scheduler, worker_processes=2)

        class Foo(RunOnceStep):
            pass

        self.run_step(Foo())
        d = self.summary_dict()
        self.assertEqual(set(), d['run_by_other_worker'])
        s = self.summary()
        self.assertNotIn('The other workers were', s)
        self.assertIn('This progress looks :) because there were no failed ', s)
        self.assertNotIn('\n\n\n', s)

    def test_with_uncomparable_parameters(self):
        """
        Don't rely on parameters being sortable
        """
        class Color(Enum):
            red = 1
            yellow = 2

        class Bar(RunOnceStep):
            eparam = trun.EnumParameter(enum=Color)

        class Baz(RunOnceStep):
            eparam = trun.EnumParameter(enum=Color)
            another_param = trun.IntParameter()

        class Foo(trun.Step):
            def requires(self):
                yield Bar(Color.red)
                yield Bar(Color.yellow)
                yield Baz(Color.red, 5)
                yield Baz(Color.yellow, 5)

        self.run_step(Foo())
        s = self.summary()
        self.assertIn('yellow', s)

    def test_with_dict_dependency(self):
        """ Just test that it doesn't crash with dict params in dependencies """

        args = dict(start=datetime.date(1998, 3, 23), num=3)

        class Bar(RunOnceStep):
            args = trun.DictParameter()

        class Foo(trun.Step):
            def requires(self):
                for i in range(10):
                    new_dict = args.copy()
                    new_dict['start'] = str(new_dict['start'] + datetime.timedelta(days=i))
                    yield Bar(args=new_dict)

        self.run_step(Foo())
        d = self.summary_dict()
        exp_set = set()
        for i in range(10):
            new_dict = args.copy()
            new_dict['start'] = str(new_dict['start'] + datetime.timedelta(days=i))
            exp_set.add(Bar(new_dict))
        exp_set.add(Foo())
        self.assertEqual(exp_set, d['completed'])
        s = self.summary()
        self.assertIn('"num": 3', s)
        self.assertIn('"start": "1998-0', s)
        self.assertIn('Scheduled 11 steps', s)
        self.assertIn('Trun Execution Summary', s)
        self.assertNotIn('00:00:00', s)
        self.assertNotIn('\n\n\n', s)

    def test_with_dict_argument(self):
        """ Just test that it doesn't crash with dict params """

        args = dict(start=str(datetime.date(1998, 3, 23)), num=3)

        class Bar(RunOnceStep):
            args = trun.DictParameter()

        self.run_step(Bar(args=args))
        d = self.summary_dict()
        exp_set = set()
        exp_set.add(Bar(args=args))
        self.assertEqual(exp_set, d['completed'])
        s = self.summary()
        self.assertIn('"num": 3', s)
        self.assertIn('"start": "1998-0', s)
        self.assertIn('Scheduled 1 step', s)
        self.assertIn('Trun Execution Summary', s)
        self.assertNotIn('00:00:00', s)
        self.assertNotIn('\n\n\n', s)

    """
    Test that a step once crashing and then succeeding should be counted as no failure.
    """
    def test_status_with_step_retry(self):
        class Foo(trun.Step):
            run_count = 0

            def run(self):
                self.run_count += 1
                if self.run_count == 1:
                    raise ValueError()

            def complete(self):
                return self.run_count > 0

        self.run_step(Foo())
        self.run_step(Foo())
        d = self.summary_dict()
        self.assertEqual({Foo()}, d['completed'])
        self.assertEqual({Foo()}, d['ever_failed'])
        self.assertFalse(d['failed'])
        self.assertFalse(d['upstream_failure'])
        self.assertFalse(d['upstream_missing_dependency'])
        self.assertFalse(d['run_by_other_worker'])
        self.assertFalse(d['still_pending_ext'])
        s = self.summary()
        self.assertIn('Scheduled 1 step', s)
        self.assertIn('Trun Execution Summary', s)
        self.assertNotIn('ever failed', s)
        self.assertIn('\n\nThis progress looks :) because there were failed steps but they all succeeded in a retry', s)
