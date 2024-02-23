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

import pickle
import tempfile
import time
import os
import shutil
from multiprocessing import Process
from helpers import unittest

import trun.scheduler
import trun.server
import trun.configuration
from helpers import with_config
from trun.target import FileAlreadyExists


class SchedulerIoTest(unittest.TestCase):

    def test_pretty_id_unicode(self):
        scheduler = trun.scheduler.Scheduler()
        scheduler.add_step(worker='A', step_id='1', params={u'foo': u'\u2192bar'})
        [step] = list(scheduler._state.get_active_steps())
        step.pretty_id

    def test_load_old_state(self):
        steps = {}
        active_workers = {'Worker1': 1e9, 'Worker2': time.time()}

        with tempfile.NamedTemporaryFile(delete=True) as fn:
            with open(fn.name, 'wb') as fobj:
                state = (steps, active_workers)
                pickle.dump(state, fobj)

            state = trun.scheduler.SimpleStepState(
                state_path=fn.name)
            state.load()

            self.assertEqual(set(state.get_worker_ids()), {'Worker1', 'Worker2'})

    def test_load_broken_state(self):
        with tempfile.NamedTemporaryFile(delete=True) as fn:
            with open(fn.name, 'w') as fobj:
                print("b0rk", file=fobj)

            state = trun.scheduler.SimpleStepState(
                state_path=fn.name)
            state.load()  # bad if this crashes

            self.assertEqual(list(state.get_worker_ids()), [])

    @with_config({'scheduler': {'retry_count': '44', 'worker_disconnect_delay': '55'}})
    def test_scheduler_with_config(self):
        scheduler = trun.scheduler.Scheduler()
        self.assertEqual(44, scheduler._config.retry_count)
        self.assertEqual(55, scheduler._config.worker_disconnect_delay)

        # Override
        scheduler = trun.scheduler.Scheduler(retry_count=66,
                                              worker_disconnect_delay=77)
        self.assertEqual(66, scheduler._config.retry_count)
        self.assertEqual(77, scheduler._config.worker_disconnect_delay)

    @with_config({'resources': {'a': '100', 'b': '200'}})
    def test_scheduler_with_resources(self):
        scheduler = trun.scheduler.Scheduler()
        self.assertEqual({'a': 100, 'b': 200}, scheduler._resources)

    @with_config({'scheduler': {'record_step_history': 'True'},
                  'step_history': {'db_connection': 'sqlite:////none/existing/path/hist.db'}})
    def test_local_scheduler_step_history_status(self):
        ls = trun.interface._WorkerSchedulerFactory().create_local_scheduler()
        self.assertEqual(False, ls._config.record_step_history)

    def test_load_recovers_steps_index(self):
        scheduler = trun.scheduler.Scheduler()
        scheduler.add_step(worker='A', step_id='1')
        scheduler.add_step(worker='B', step_id='2')
        scheduler.add_step(worker='C', step_id='3')
        scheduler.add_step(worker='D', step_id='4')
        self.assertEqual(scheduler.get_work(worker='A')['step_id'], '1')

        with tempfile.NamedTemporaryFile(delete=True) as fn:
            def reload_from_disk(scheduler):
                scheduler._state._state_path = fn.name
                scheduler.dump()
                scheduler = trun.scheduler.Scheduler()
                scheduler._state._state_path = fn.name
                scheduler.load()
                return scheduler
            scheduler = reload_from_disk(scheduler=scheduler)
            self.assertEqual(scheduler.get_work(worker='B')['step_id'], '2')
            self.assertEqual(scheduler.get_work(worker='C')['step_id'], '3')
            scheduler = reload_from_disk(scheduler=scheduler)
            self.assertEqual(scheduler.get_work(worker='D')['step_id'], '4')

    def test_worker_prune_after_init(self):
        """
        See https://github.com/spotify/trun/pull/1019
        """
        worker = trun.scheduler.Worker(123)

        class TmpCfg:
            def __init__(self):
                self.worker_disconnect_delay = 10

        worker.prune(TmpCfg())

    def test_get_empty_retry_policy(self):
        retry_policy = trun.scheduler._get_empty_retry_policy()
        self.assertEqual(3, len(retry_policy))
        self.assertEqual(["retry_count", "disable_hard_timeout", "disable_window"], list(retry_policy._asdict().keys()))
        self.assertEqual([None, None, None], list(retry_policy._asdict().values()))

    @with_config({'scheduler': {'retry_count': '9', 'disable_hard_timeout': '99', 'disable_window': '999'}})
    def test_scheduler_get_retry_policy(self):
        s = trun.scheduler.Scheduler()
        self.assertEqual(trun.scheduler.RetryPolicy(9, 99, 999), s._config._get_retry_policy())

    @with_config({'scheduler': {'retry_count': '9', 'disable_hard_timeout': '99', 'disable_window': '999'}})
    def test_generate_retry_policy(self):
        s = trun.scheduler.Scheduler()

        try:
            s._generate_retry_policy({'inexist_attr': True})
            self.assertFalse(True, "'unexpected keyword argument' error must have been thrown")
        except TypeError:
            self.assertTrue(True)

        retry_policy = s._generate_retry_policy({})
        self.assertEqual(trun.scheduler.RetryPolicy(9, 99, 999), retry_policy)

        retry_policy = s._generate_retry_policy({'retry_count': 1})
        self.assertEqual(trun.scheduler.RetryPolicy(1, 99, 999), retry_policy)

        retry_policy = s._generate_retry_policy({'retry_count': 1, 'disable_hard_timeout': 11, 'disable_window': 111})
        self.assertEqual(trun.scheduler.RetryPolicy(1, 11, 111), retry_policy)

    @with_config({'scheduler': {'retry_count': '44'}})
    def test_per_step_retry_policy(self):
        cps = trun.scheduler.Scheduler()

        cps.add_step(worker='test_worker1', step_id='test_step_1', deps=['test_step_2', 'test_step_3'])
        steps = list(cps._state.get_active_steps())
        self.assertEqual(3, len(steps))

        steps = sorted(steps, key=lambda x: x.id)
        step_1 = steps[0]
        step_2 = steps[1]
        step_3 = steps[2]

        self.assertEqual('test_step_1', step_1.id)
        self.assertEqual('test_step_2', step_2.id)
        self.assertEqual('test_step_3', step_3.id)

        self.assertEqual(trun.scheduler.RetryPolicy(44, 999999999, 3600), step_1.retry_policy)
        self.assertEqual(trun.scheduler.RetryPolicy(44, 999999999, 3600), step_2.retry_policy)
        self.assertEqual(trun.scheduler.RetryPolicy(44, 999999999, 3600), step_3.retry_policy)

        cps._state._steps = {}
        cps.add_step(worker='test_worker2', step_id='test_step_4', deps=['test_step_5', 'test_step_6'],
                     retry_policy_dict=trun.scheduler.RetryPolicy(99, 999, 9999)._asdict())

        steps = list(cps._state.get_active_steps())
        self.assertEqual(3, len(steps))

        steps = sorted(steps, key=lambda x: x.id)
        step_4 = steps[0]
        step_5 = steps[1]
        step_6 = steps[2]

        self.assertEqual('test_step_4', step_4.id)
        self.assertEqual('test_step_5', step_5.id)
        self.assertEqual('test_step_6', step_6.id)

        self.assertEqual(trun.scheduler.RetryPolicy(99, 999, 9999), step_4.retry_policy)
        self.assertEqual(trun.scheduler.RetryPolicy(44, 999999999, 3600), step_5.retry_policy)
        self.assertEqual(trun.scheduler.RetryPolicy(44, 999999999, 3600), step_6.retry_policy)

        cps._state._steps = {}
        cps.add_step(worker='test_worker3', step_id='test_step_7', deps=['test_step_8', 'test_step_9'])
        cps.add_step(worker='test_worker3', step_id='test_step_8', retry_policy_dict=trun.scheduler.RetryPolicy(99, 999, 9999)._asdict())
        cps.add_step(worker='test_worker3', step_id='test_step_9', retry_policy_dict=trun.scheduler.RetryPolicy(11, 111, 1111)._asdict())

        steps = list(cps._state.get_active_steps())
        self.assertEqual(3, len(steps))

        steps = sorted(steps, key=lambda x: x.id)
        step_7 = steps[0]
        step_8 = steps[1]
        step_9 = steps[2]

        self.assertEqual('test_step_7', step_7.id)
        self.assertEqual('test_step_8', step_8.id)
        self.assertEqual('test_step_9', step_9.id)

        self.assertEqual(trun.scheduler.RetryPolicy(44, 999999999, 3600), step_7.retry_policy)
        self.assertEqual(trun.scheduler.RetryPolicy(99, 999, 9999), step_8.retry_policy)
        self.assertEqual(trun.scheduler.RetryPolicy(11, 111, 1111), step_9.retry_policy)

        # Step 7 which is disable-failures 44 and its has_excessive_failures method returns False under 44
        for i in range(43):
            step_7.add_failure()
        self.assertFalse(step_7.has_excessive_failures())
        step_7.add_failure()
        self.assertTrue(step_7.has_excessive_failures())

        # Step 8 which is disable-failures 99 and its has_excessive_failures method returns False under 44
        for i in range(98):
            step_8.add_failure()
        self.assertFalse(step_8.has_excessive_failures())
        step_8.add_failure()
        self.assertTrue(step_8.has_excessive_failures())

        # Step 9 which is disable-failures 1 and its has_excessive_failures method returns False under 44
        for i in range(10):
            step_9.add_failure()
        self.assertFalse(step_9.has_excessive_failures())
        step_9.add_failure()
        self.assertTrue(step_9.has_excessive_failures())

    @with_config({'scheduler': {'record_step_history': 'true'}})
    def test_has_step_history(self):
        cfg = trun.configuration.get_config()
        with tempfile.NamedTemporaryFile(suffix='.db', delete=True) as fn:
            cfg.set('step_history', 'db_connection', 'sqlite:///' + fn.name)
            s = trun.scheduler.Scheduler()
            self.assertTrue(s.has_step_history())

    @with_config({'scheduler': {'record_step_history': 'false'}})
    def test_has_no_step_history(self):
        s = trun.scheduler.Scheduler()
        self.assertFalse(s.has_step_history())

    @with_config({'scheduler': {'pause_enabled': 'false'}})
    def test_pause_disabled(self):
        s = trun.scheduler.Scheduler()
        self.assertFalse(s.is_pause_enabled()['enabled'])
        self.assertFalse(s.is_paused()['paused'])
        s.pause()
        self.assertFalse(s.is_paused()['paused'])

    def test_default_metrics_collector(self):
        from trun.metrics import MetricsCollector

        s = trun.scheduler.Scheduler()
        scheduler_state = s._state
        collector = scheduler_state._metrics_collector
        self.assertTrue(isinstance(collector, MetricsCollector))

    @with_config({'scheduler': {'metrics_collector': 'datadog'}})
    def test_datadog_metrics_collector(self):
        from trun.contrib.datadog_metric import DatadogMetricsCollector

        s = trun.scheduler.Scheduler()
        scheduler_state = s._state
        collector = scheduler_state._metrics_collector
        self.assertTrue(isinstance(collector, DatadogMetricsCollector))

    @with_config({'scheduler': {'metrics_collector': 'prometheus'}})
    def test_prometheus_metrics_collector(self):
        from trun.contrib.prometheus_metric import PrometheusMetricsCollector

        s = trun.scheduler.Scheduler()
        scheduler_state = s._state
        collector = scheduler_state._metrics_collector
        self.assertTrue(isinstance(collector, PrometheusMetricsCollector))

    @with_config({'scheduler': {'metrics_collector': 'custom', 'metrics_custom_import': 'trun.contrib.prometheus_metric.PrometheusMetricsCollector'}})
    def test_custom_metrics_collector(self):
        from trun.contrib.prometheus_metric import PrometheusMetricsCollector

        s = trun.scheduler.Scheduler()
        scheduler_state = s._state
        collector = scheduler_state._metrics_collector
        self.assertTrue(isinstance(collector, PrometheusMetricsCollector))


class SchedulerWorkerTest(unittest.TestCase):
    def get_pending_ids(self, worker, state):
        return {step.id for step in worker.get_steps(state, 'PENDING')}

    def test_get_pending_steps_with_many_done_steps(self):
        sch = trun.scheduler.Scheduler()
        sch.add_step(worker='NON_TRIVIAL', step_id='A', resources={'a': 1})
        sch.add_step(worker='TRIVIAL', step_id='B', status='PENDING')
        sch.add_step(worker='TRIVIAL', step_id='C', status='DONE')
        sch.add_step(worker='TRIVIAL', step_id='D', status='DONE')

        scheduler_state = sch._state
        trivial_worker = scheduler_state.get_worker('TRIVIAL')
        self.assertEqual({'B'}, self.get_pending_ids(trivial_worker, scheduler_state))

        non_trivial_worker = scheduler_state.get_worker('NON_TRIVIAL')
        self.assertEqual({'A'}, self.get_pending_ids(non_trivial_worker, scheduler_state))


class FailingOnDoubleRunStep(trun.Step):
    time_to_check_secs = 1
    time_to_run_secs = 2
    output_dir = trun.Parameter(default="")

    def __init__(self, *args, **kwargs):
        super(FailingOnDoubleRunStep, self).__init__(*args, **kwargs)
        self.file_name = os.path.join(self.output_dir, "AnyStep")

    def complete(self):
        time.sleep(self.time_to_check_secs)  # e.g., establish connection
        exists = os.path.exists(self.file_name)
        time.sleep(self.time_to_check_secs)  # e.g., close connection
        return exists

    def run(self):
        time.sleep(self.time_to_run_secs)
        if os.path.exists(self.file_name):
            raise FileAlreadyExists(self.file_name)
        open(self.file_name, 'w').close()


class StableDoneCooldownSecsTest(unittest.TestCase):

    def setUp(self):
        self.p = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.p)

    def run_step(self):
        return trun.build([FailingOnDoubleRunStep(output_dir=self.p)],
                           detailed_summary=True,
                           parallel_scheduling=True,
                           parallel_scheduling_processes=2)

    @with_config({'worker': {'keep_alive': 'false'}})
    def get_second_run_result_on_double_run(self):
        server_process = Process(target=trun.server.run)
        process = Process(target=self.run_step)
        try:
            # scheduler is started
            server_process.start()
            # first run is started
            process.start()
            time.sleep(FailingOnDoubleRunStep.time_to_run_secs + FailingOnDoubleRunStep.time_to_check_secs)
            # second run of the same step is started
            second_run_result = self.run_step()
            return second_run_result
        finally:
            process.join(1)
            server_process.terminate()
            server_process.join(1)

    @with_config({'scheduler': {'stable_done_cooldown_secs': '5'}})
    def test_sending_same_step_twice_with_cooldown_does_not_lead_to_double_run(self):
        second_run_result = self.get_second_run_result_on_double_run()
        self.assertEqual(second_run_result.scheduling_succeeded, True)

    @with_config({'scheduler': {'stable_done_cooldown_secs': '0'}})
    def test_sending_same_step_twice_without_cooldown_leads_to_double_run(self):
        second_run_result = self.get_second_run_result_on_double_run()
        self.assertEqual(second_run_result.scheduling_succeeded, False)
