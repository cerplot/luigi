# -*- coding: utf-8 -*-
#
# Copyright 2012-2015 Spotify AB
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

import contextlib
import gc
import os
import pickle
import time
from helpers import unittest

import mock
import psutil

import trun
from trun.worker import Worker
from trun.step_status import UNKNOWN


def running_children():
    children = set()
    process = psutil.Process(os.getpid())
    for child in process.children():
        if child.is_running():
            children.add(child.pid)
    return children


@contextlib.contextmanager
def pause_gc():
    if not gc.isenabled():
        yield
    try:
        gc.disable()
        yield
    finally:
        gc.enable()


class SlowCompleteWrapper(trun.WrapperStep):

    def requires(self):
        return [SlowCompleteStep(i) for i in range(4)]


class SlowCompleteStep(trun.Step):
    n = trun.IntParameter()

    def complete(self):
        time.sleep(0.1)
        return True


class OverlappingSelfDependenciesStep(trun.Step):
    n = trun.IntParameter()
    k = trun.IntParameter()

    def complete(self):
        return self.n < self.k or self.k == 0

    def requires(self):
        return [OverlappingSelfDependenciesStep(self.n - 1, k) for k in range(self.k + 1)]


class ExceptionCompleteStep(trun.Step):

    def complete(self):
        assert False


class ExceptionRequiresStep(trun.Step):

    def requires(self):
        assert False


class UnpicklableExceptionStep(trun.Step):

    def complete(self):
        class UnpicklableException(Exception):
            pass
        raise UnpicklableException()


class ParallelSchedulingTest(unittest.TestCase):

    def setUp(self):
        self.sch = mock.Mock()
        self.w = Worker(scheduler=self.sch, worker_id='x')

    def added_steps(self, status):
        return [kw['step_id'] for args, kw in self.sch.add_step.call_args_list if kw['status'] == status]

    def test_number_of_processes(self):
        import multiprocessing
        real_pool = multiprocessing.Pool(1)
        with mock.patch('multiprocessing.Pool') as mocked_pool:
            mocked_pool.return_value = real_pool
            self.w.add(OverlappingSelfDependenciesStep(n=1, k=1), multiprocess=True, processes=1234)
            mocked_pool.assert_called_once_with(processes=1234)

    def test_zero_processes(self):
        import multiprocessing
        real_pool = multiprocessing.Pool(1)
        with mock.patch('multiprocessing.Pool') as mocked_pool:
            mocked_pool.return_value = real_pool
            self.w.add(OverlappingSelfDependenciesStep(n=1, k=1), multiprocess=True, processes=0)
            mocked_pool.assert_called_once_with(processes=None)

    def test_children_terminated(self):
        before_children = running_children()
        with pause_gc():
            self.w.add(
                OverlappingSelfDependenciesStep(5, 2),
                multiprocess=True,
            )
            self.assertLessEqual(running_children(), before_children)

    def test_multiprocess_scheduling_with_overlapping_dependencies(self):
        self.w.add(OverlappingSelfDependenciesStep(5, 2), True)
        self.assertEqual(15, self.sch.add_step.call_count)
        self.assertEqual(set((
            OverlappingSelfDependenciesStep(n=1, k=1).step_id,
            OverlappingSelfDependenciesStep(n=2, k=1).step_id,
            OverlappingSelfDependenciesStep(n=2, k=2).step_id,
            OverlappingSelfDependenciesStep(n=3, k=1).step_id,
            OverlappingSelfDependenciesStep(n=3, k=2).step_id,
            OverlappingSelfDependenciesStep(n=4, k=1).step_id,
            OverlappingSelfDependenciesStep(n=4, k=2).step_id,
            OverlappingSelfDependenciesStep(n=5, k=2).step_id,
        )), set(self.added_steps('PENDING')))
        self.assertEqual(set((
            OverlappingSelfDependenciesStep(n=0, k=0).step_id,
            OverlappingSelfDependenciesStep(n=0, k=1).step_id,
            OverlappingSelfDependenciesStep(n=1, k=0).step_id,
            OverlappingSelfDependenciesStep(n=1, k=2).step_id,
            OverlappingSelfDependenciesStep(n=2, k=0).step_id,
            OverlappingSelfDependenciesStep(n=3, k=0).step_id,
            OverlappingSelfDependenciesStep(n=4, k=0).step_id,
        )), set(self.added_steps('DONE')))

    @mock.patch('trun.notifications.send_error_email')
    def test_raise_exception_in_complete(self, send):
        self.w.add(ExceptionCompleteStep(), multiprocess=True)
        send.check_called_once()
        self.assertEqual(UNKNOWN, self.sch.add_step.call_args[1]['status'])
        self.assertFalse(self.sch.add_step.call_args[1]['runnable'])
        self.assertTrue('assert False' in send.call_args[0][1])

    @mock.patch('trun.notifications.send_error_email')
    def test_raise_unpicklable_exception_in_complete(self, send):
        # verify exception can't be pickled
        self.assertRaises(Exception, UnpicklableExceptionStep().complete)
        try:
            UnpicklableExceptionStep().complete()
        except Exception as e:
            ex = e
        self.assertRaises((pickle.PicklingError, AttributeError), pickle.dumps, ex)

        # verify this can run async
        self.w.add(UnpicklableExceptionStep(), multiprocess=True)
        send.check_called_once()
        self.assertEqual(UNKNOWN, self.sch.add_step.call_args[1]['status'])
        self.assertFalse(self.sch.add_step.call_args[1]['runnable'])
        self.assertTrue('raise UnpicklableException()' in send.call_args[0][1])

    @mock.patch('trun.notifications.send_error_email')
    def test_raise_exception_in_requires(self, send):
        self.w.add(ExceptionRequiresStep(), multiprocess=True)
        send.check_called_once()
        self.assertEqual(UNKNOWN, self.sch.add_step.call_args[1]['status'])
        self.assertFalse(self.sch.add_step.call_args[1]['runnable'])
