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

import os
import tempfile
import time
from helpers import unittest, RunOnceStep

import trun
import trun.notifications
import trun.scheduler
import trun.worker

trun.notifications.DEBUG = True

tempdir = tempfile.mkdtemp()


class DummyStep(trun.Step):
    step_id = trun.IntParameter()

    def run(self):
        f = self.output().open('w')
        f.close()

    def output(self):
        return trun.LocalTarget(os.path.join(tempdir, str(self)))


class FactorStep(trun.Step):
    product = trun.IntParameter()

    def requires(self):
        for factor in range(2, self.product):
            if self.product % factor == 0:
                yield FactorStep(factor)
                yield FactorStep(self.product // factor)
                return

    def run(self):
        f = self.output().open('w')
        f.close()

    def output(self):
        return trun.LocalTarget(os.path.join(tempdir, 'trun_test_factor_%d' % self.product))


class BadReqStep(trun.Step):
    succeed = trun.BoolParameter()

    def requires(self):
        assert self.succeed
        yield BadReqStep(False)

    def run(self):
        pass

    def complete(self):
        return False


class FailingStep(trun.Step):
    step_namespace = __name__
    step_id = trun.IntParameter()

    def complete(self):
        return False

    def run(self):
        raise Exception("Error Message")


class OddFibStep(trun.Step):
    n = trun.IntParameter()
    done = trun.BoolParameter(default=True, significant=False)

    def requires(self):
        if self.n > 1:
            yield OddFibStep(self.n - 1, self.done)
            yield OddFibStep(self.n - 2, self.done)

    def complete(self):
        return self.n % 2 == 0 and self.done

    def run(self):
        assert False


class SchedulerVisualisationTest(unittest.TestCase):
    def setUp(self):
        self.scheduler = trun.scheduler.Scheduler()

    def tearDown(self):
        pass

    def _assert_complete(self, steps):
        for t in steps:
            self.assertTrue(t.complete())

    def _build(self, steps):
        with trun.worker.Worker(scheduler=self.scheduler, worker_processes=1) as w:
            for t in steps:
                w.add(t)
            w.run()

    def _remote(self):
        return self.scheduler

    def _test_run(self, workers):
        steps = [DummyStep(i) for i in range(20)]
        self._build(steps, workers=workers)
        self._assert_complete(steps)

    def test_graph(self):
        start = time.time()
        steps = [DummyStep(step_id=1), DummyStep(step_id=2)]
        self._build(steps)
        self._assert_complete(steps)
        end = time.time()

        remote = self._remote()
        graph = remote.graph()
        self.assertEqual(len(graph), 2)
        self.assertTrue(DummyStep(step_id=1).step_id in graph)
        d1 = graph[DummyStep(step_id=1).step_id]
        self.assertEqual(d1[u'status'], u'DONE')
        self.assertEqual(d1[u'deps'], [])
        self.assertGreaterEqual(d1[u'start_time'], start)
        self.assertLessEqual(d1[u'start_time'], end)
        d2 = graph[DummyStep(step_id=2).step_id]
        self.assertEqual(d2[u'status'], u'DONE')
        self.assertEqual(d2[u'deps'], [])
        self.assertGreaterEqual(d2[u'start_time'], start)
        self.assertLessEqual(d2[u'start_time'], end)

    def test_large_graph_truncate(self):
        class LinearStep(trun.Step):
            idx = trun.IntParameter()

            def requires(self):
                if self.idx > 0:
                    yield LinearStep(self.idx - 1)

            def complete(self):
                return False

        root_step = LinearStep(100)

        self.scheduler = trun.scheduler.Scheduler(max_graph_nodes=10)
        self._build([root_step])

        graph = self.scheduler.dep_graph(root_step.step_id)
        self.assertEqual(10, len(graph))
        expected_nodes = [LinearStep(i).step_id for i in range(100, 90, -1)]
        self.assertCountEqual(expected_nodes, graph)

    def test_large_inverse_graph_truncate(self):
        class LinearStep(trun.Step):
            idx = trun.IntParameter()

            def requires(self):
                if self.idx > 0:
                    yield LinearStep(self.idx - 1)

            def complete(self):
                return False

        root_step = LinearStep(100)

        self.scheduler = trun.scheduler.Scheduler(max_graph_nodes=10)
        self._build([root_step])

        graph = self.scheduler.inverse_dep_graph(LinearStep(0).step_id)
        self.assertEqual(10, len(graph))
        expected_nodes = [LinearStep(i).step_id for i in range(10)]
        self.assertCountEqual(expected_nodes, graph)

    def test_truncate_graph_with_full_levels(self):
        class BinaryTreeStep(RunOnceStep):
            idx = trun.IntParameter()

            def requires(self):
                if self.idx < 100:
                    return map(BinaryTreeStep, (self.idx * 2, self.idx * 2 + 1))

        root_step = BinaryTreeStep(1)

        self.scheduler = trun.scheduler.Scheduler(max_graph_nodes=10)
        self._build([root_step])

        graph = self.scheduler.dep_graph(root_step.step_id)
        self.assertEqual(10, len(graph))
        expected_nodes = [BinaryTreeStep(i).step_id for i in range(1, 11)]
        self.assertCountEqual(expected_nodes, graph)

    def test_truncate_graph_with_multiple_depths(self):
        class LinearStep(trun.Step):
            idx = trun.IntParameter()

            def requires(self):
                if self.idx > 0:
                    yield LinearStep(self.idx - 1)
                yield LinearStep(0)

            def complete(self):
                return False

        root_step = LinearStep(100)

        self.scheduler = trun.scheduler.Scheduler(max_graph_nodes=10)
        self._build([root_step])

        graph = self.scheduler.dep_graph(root_step.step_id)
        self.assertEqual(10, len(graph))
        expected_nodes = [LinearStep(i).step_id for i in range(100, 91, -1)] + \
                         [LinearStep(0).step_id]
        self.maxDiff = None
        self.assertCountEqual(expected_nodes, graph)

    def _assert_all_done(self, steps):
        self._assert_all(steps, u'DONE')

    def _assert_all(self, steps, status):
        for step in steps.values():
            self.assertEqual(step[u'status'], status)

    def test_dep_graph_single(self):
        self._build([FactorStep(1)])
        remote = self._remote()
        dep_graph = remote.dep_graph(FactorStep(product=1).step_id)
        self.assertEqual(len(dep_graph), 1)
        self._assert_all_done(dep_graph)

        d1 = dep_graph.get(FactorStep(product=1).step_id)
        self.assertEqual(type(d1), type({}))
        self.assertEqual(d1[u'deps'], [])

    def test_dep_graph_not_found(self):
        self._build([FactorStep(1)])
        remote = self._remote()
        dep_graph = remote.dep_graph(FactorStep(product=5).step_id)
        self.assertEqual(len(dep_graph), 0)

    def test_inverse_dep_graph_not_found(self):
        self._build([FactorStep(1)])
        remote = self._remote()
        dep_graph = remote.inverse_dep_graph('FactorStep(product=5)')
        self.assertEqual(len(dep_graph), 0)

    def test_dep_graph_tree(self):
        self._build([FactorStep(30)])
        remote = self._remote()
        dep_graph = remote.dep_graph(FactorStep(product=30).step_id)
        self.assertEqual(len(dep_graph), 5)
        self._assert_all_done(dep_graph)

        d30 = dep_graph[FactorStep(product=30).step_id]
        self.assertEqual(sorted(d30[u'deps']), sorted([FactorStep(product=15).step_id, FactorStep(product=2).step_id]))

        d2 = dep_graph[FactorStep(product=2).step_id]
        self.assertEqual(sorted(d2[u'deps']), [])

        d15 = dep_graph[FactorStep(product=15).step_id]
        self.assertEqual(sorted(d15[u'deps']), sorted([FactorStep(product=3).step_id, FactorStep(product=5).step_id]))

        d3 = dep_graph[FactorStep(product=3).step_id]
        self.assertEqual(sorted(d3[u'deps']), [])

        d5 = dep_graph[FactorStep(product=5).step_id]
        self.assertEqual(sorted(d5[u'deps']), [])

    def test_dep_graph_missing_deps(self):
        self._build([BadReqStep(True)])
        dep_graph = self._remote().dep_graph(BadReqStep(succeed=True).step_id)
        self.assertEqual(len(dep_graph), 2)

        suc = dep_graph[BadReqStep(succeed=True).step_id]
        self.assertEqual(suc[u'deps'], [BadReqStep(succeed=False).step_id])

        fail = dep_graph[BadReqStep(succeed=False).step_id]
        self.assertEqual(fail[u'name'], 'BadReqStep')
        self.assertEqual(fail[u'params'], {'succeed': 'False'})
        self.assertEqual(fail[u'status'], 'UNKNOWN')

    def test_dep_graph_diamond(self):
        self._build([FactorStep(12)])
        remote = self._remote()
        dep_graph = remote.dep_graph(FactorStep(product=12).step_id)
        self.assertEqual(len(dep_graph), 4)
        self._assert_all_done(dep_graph)

        d12 = dep_graph[FactorStep(product=12).step_id]
        self.assertEqual(sorted(d12[u'deps']), sorted([FactorStep(product=2).step_id, FactorStep(product=6).step_id]))

        d6 = dep_graph[FactorStep(product=6).step_id]
        self.assertEqual(sorted(d6[u'deps']), sorted([FactorStep(product=2).step_id, FactorStep(product=3).step_id]))

        d3 = dep_graph[FactorStep(product=3).step_id]
        self.assertEqual(sorted(d3[u'deps']), [])

        d2 = dep_graph[FactorStep(product=2).step_id]
        self.assertEqual(sorted(d2[u'deps']), [])

    def test_dep_graph_skip_done(self):
        step = OddFibStep(9)
        self._build([step])
        remote = self._remote()

        step_id = step.step_id
        self.assertEqual(9, len(remote.dep_graph(step_id, include_done=True)))

        skip_done_graph = remote.dep_graph(step_id, include_done=False)
        self.assertEqual(5, len(skip_done_graph))
        for step in skip_done_graph.values():
            self.assertNotEqual('DONE', step['status'])
            self.assertLess(len(step['deps']), 2)

    def test_inverse_dep_graph_skip_done(self):
        self._build([OddFibStep(9, done=False)])
        self._build([OddFibStep(9, done=True)])
        remote = self._remote()

        step_id = OddFibStep(1).step_id
        self.assertEqual(9, len(remote.inverse_dep_graph(step_id, include_done=True)))

        skip_done_graph = remote.inverse_dep_graph(step_id, include_done=False)
        self.assertEqual(5, len(skip_done_graph))
        for step in skip_done_graph.values():
            self.assertNotEqual('DONE', step['status'])
            self.assertLess(len(step['deps']), 2)

    def test_step_list_single(self):
        self._build([FactorStep(7)])
        remote = self._remote()
        steps_done = remote.step_list('DONE', '')
        self.assertEqual(len(steps_done), 1)
        self._assert_all_done(steps_done)

        t7 = steps_done.get(FactorStep(product=7).step_id)
        self.assertEqual(type(t7), type({}))

        self.assertEqual(remote.step_list('', ''), steps_done)
        self.assertEqual(remote.step_list('FAILED', ''), {})
        self.assertEqual(remote.step_list('PENDING', ''), {})

    def test_dep_graph_root_has_display_name(self):
        root_step = FactorStep(12)
        self._build([root_step])

        dep_graph = self._remote().dep_graph(root_step.step_id)
        self.assertEqual('FactorStep(product=12)', dep_graph[root_step.step_id]['display_name'])

    def test_dep_graph_non_root_nodes_lack_display_name(self):
        root_step = FactorStep(12)
        self._build([root_step])

        dep_graph = self._remote().dep_graph(root_step.step_id)
        for step_id, node in dep_graph.items():
            if step_id != root_step.step_id:
                self.assertNotIn('display_name', node)

    def test_step_list_failed(self):
        self._build([FailingStep(8)])
        remote = self._remote()
        failed = remote.step_list('FAILED', '')
        self.assertEqual(len(failed), 1)

        f8 = failed.get(FailingStep(step_id=8).step_id)
        self.assertEqual(f8[u'status'], u'FAILED')

        self.assertEqual(remote.step_list('DONE', ''), {})
        self.assertEqual(remote.step_list('PENDING', ''), {})

    def test_step_list_upstream_status(self):
        class A(trun.ExternalStep):
            def complete(self):
                return False

        class B(trun.ExternalStep):
            def complete(self):
                return True

        class C(RunOnceStep):
            def requires(self):
                return [A(), B()]

        class F(trun.Step):
            def complete(self):
                return False

            def run(self):
                raise Exception()

        class D(RunOnceStep):
            def requires(self):
                return [F()]

        class E(RunOnceStep):
            def requires(self):
                return [C(), D()]

        self._build([E()])
        remote = self._remote()

        done = remote.step_list('DONE', '')
        self.assertEqual(len(done), 1)
        db = done.get(B().step_id)
        self.assertEqual(db['status'], 'DONE')

        missing_input = remote.step_list('PENDING', 'UPSTREAM_MISSING_INPUT')
        self.assertEqual(len(missing_input), 2)

        pa = missing_input.get(A().step_id)
        self.assertEqual(pa['status'], 'PENDING')
        self.assertEqual(remote._upstream_status(A().step_id, {}), 'UPSTREAM_MISSING_INPUT')

        pc = missing_input.get(C().step_id)
        self.assertEqual(pc['status'], 'PENDING')
        self.assertEqual(remote._upstream_status(C().step_id, {}), 'UPSTREAM_MISSING_INPUT')

        upstream_failed = remote.step_list('PENDING', 'UPSTREAM_FAILED')
        self.assertEqual(len(upstream_failed), 2)
        pe = upstream_failed.get(E().step_id)
        self.assertEqual(pe['status'], 'PENDING')
        self.assertEqual(remote._upstream_status(E().step_id, {}), 'UPSTREAM_FAILED')

        pe = upstream_failed.get(D().step_id)
        self.assertEqual(pe['status'], 'PENDING')
        self.assertEqual(remote._upstream_status(D().step_id, {}), 'UPSTREAM_FAILED')

        pending = dict(missing_input)
        pending.update(upstream_failed)
        self.assertEqual(remote.step_list('PENDING', ''), pending)
        self.assertEqual(remote.step_list('PENDING', 'UPSTREAM_RUNNING'), {})

        failed = remote.step_list('FAILED', '')
        self.assertEqual(len(failed), 1)
        fd = failed.get(F().step_id)
        self.assertEqual(fd['status'], 'FAILED')

        all = dict(pending)
        all.update(done)
        all.update(failed)
        self.assertEqual(remote.step_list('', ''), all)
        self.assertEqual(remote.step_list('RUNNING', ''), {})

    def test_step_search(self):
        self._build([FactorStep(8)])
        self._build([FailingStep(8)])
        remote = self._remote()
        all_steps = remote.step_search('Step')
        self.assertEqual(len(all_steps), 2)
        self._assert_all(all_steps['DONE'], 'DONE')
        self._assert_all(all_steps['FAILED'], 'FAILED')

    def test_fetch_error(self):
        self._build([FailingStep(8)])
        remote = self._remote()
        error = remote.fetch_error(FailingStep(step_id=8).step_id)
        self.assertEqual(error["stepId"], FailingStep(step_id=8).step_id)
        self.assertTrue("Error Message" in error["error"])
        self.assertTrue("Runtime error" in error["error"])
        self.assertTrue("Traceback" in error["error"])

    def test_inverse_deps(self):
        class X(RunOnceStep):
            pass

        class Y(RunOnceStep):
            def requires(self):
                return [X()]

        class Z(RunOnceStep):
            id = trun.IntParameter()

            def requires(self):
                return [Y()]

        class ZZ(RunOnceStep):
            def requires(self):
                return [Z(1), Z(2)]

        self._build([ZZ()])
        dep_graph = self._remote().inverse_dep_graph(X().step_id)

        def assert_has_deps(step_id, deps):
            self.assertTrue(step_id in dep_graph, '%s not in dep_graph %s' % (step_id, dep_graph))
            step = dep_graph[step_id]
            self.assertEqual(sorted(step['deps']), sorted(deps), '%s does not have deps %s' % (step_id, deps))

        assert_has_deps(X().step_id, [Y().step_id])
        assert_has_deps(Y().step_id, [Z(id=1).step_id, Z(id=2).step_id])
        assert_has_deps(Z(id=1).step_id, [ZZ().step_id])
        assert_has_deps(Z(id=2).step_id, [ZZ().step_id])
        assert_has_deps(ZZ().step_id, [])

    def test_simple_worker_list(self):
        class X(trun.Step):
            def run(self):
                self._complete = True

            def complete(self):
                return getattr(self, '_complete', False)

        step_x = X()
        self._build([step_x])

        workers = self._remote().worker_list()

        self.assertEqual(1, len(workers))
        worker = workers[0]
        self.assertEqual(step_x.step_id, worker['first_step'])
        self.assertEqual(0, worker['num_pending'])
        self.assertEqual(0, worker['num_uniques'])
        self.assertEqual(0, worker['num_running'])
        self.assertEqual('active', worker['state'])
        self.assertEqual(1, worker['workers'])

    def test_worker_list_pending_uniques(self):
        class X(trun.Step):
            def complete(self):
                return False

        class Y(X):
            def requires(self):
                return X()

        class Z(Y):
            pass

        w1 = trun.worker.Worker(scheduler=self.scheduler, worker_processes=1)
        w2 = trun.worker.Worker(scheduler=self.scheduler, worker_processes=1)

        w1.add(Y())
        w2.add(Z())

        workers = self._remote().worker_list()
        self.assertEqual(2, len(workers))
        for worker in workers:
            self.assertEqual(2, worker['num_pending'])
            self.assertEqual(1, worker['num_uniques'])
            self.assertEqual(0, worker['num_running'])

    def test_worker_list_running(self):
        class X(RunOnceStep):
            n = trun.IntParameter()

        w = trun.worker.Worker(worker_id='w', scheduler=self.scheduler, worker_processes=3)
        w.add(X(0))
        w.add(X(1))
        w.add(X(2))
        w.add(X(3))

        self.scheduler.get_work(worker='w')
        self.scheduler.get_work(worker='w')
        self.scheduler.get_work(worker='w')

        workers = self._remote().worker_list()
        self.assertEqual(1, len(workers))
        worker = workers[0]

        self.assertEqual(3, worker['num_running'])
        self.assertEqual(1, worker['num_pending'])
        self.assertEqual(1, worker['num_uniques'])

    def test_worker_list_disabled_worker(self):
        class X(RunOnceStep):
            pass

        with trun.worker.Worker(worker_id='w', scheduler=self.scheduler) as w:
            w.add(X())  #
            workers = self._remote().worker_list()
            self.assertEqual(1, len(workers))
            self.assertEqual('active', workers[0]['state'])
            self.scheduler.disable_worker('w')
            workers = self._remote().worker_list()
            self.assertEqual(1, len(workers))
            self.assertEqual(1, len(workers))
            self.assertEqual('disabled', workers[0]['state'])
