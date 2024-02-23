# -*- coding: utf-8 -*-

from helpers import unittest
import mock
import time

from trun.contrib.datadog_metric import DatadogMetricsCollector
from trun.metrics import MetricsCollectors
from trun.scheduler import Scheduler

WORKER = 'myworker'


class DatadogMetricTest(unittest.TestCase):
    def setUp(self):
        self.mockDatadog()
        self.time = time.time
        self.collector = DatadogMetricsCollector()
        self.s = Scheduler(metrics_collector=MetricsCollectors.datadog)

    def tearDown(self):
        self.unMockDatadog()

        if time.time != self.time:
            time.time = self.time

    def startStep(self, scheduler=None):
        if scheduler:
            s = scheduler
        else:
            s = self.s

        s.add_step(worker=WORKER, step_id='DDStepID', family='DDStepName')
        step = s._state.get_step('DDStepID')

        step.time_running = 0
        return step

    def mockDatadog(self):
        self.create_patcher = mock.patch('datadog.api.Event.create')
        self.mock_create = self.create_patcher.start()

        self.increment_patcher = mock.patch('datadog.statsd.increment')
        self.mock_increment = self.increment_patcher.start()

        self.gauge_patcher = mock.patch('datadog.statsd.gauge')
        self.mock_gauge = self.gauge_patcher.start()

    def unMockDatadog(self):
        self.create_patcher.stop()
        self.increment_patcher.stop()
        self.gauge_patcher.stop()

    def setTime(self, t):
        time.time = lambda: t

    def test_send_event_on_step_started(self):
        step = self.startStep()
        self.collector.handle_step_started(step)

        self.mock_create.assert_called_once_with(alert_type='info',
                                                 priority='low',
                                                 tags=['step_name:DDStepName',
                                                       'step_state:STARTED',
                                                       'environment:development',
                                                       'application:trun'],
                                                 text='A step has been started in the pipeline named: DDStepName',
                                                 title='Trun: A step has been started!')

    def test_send_increment_on_step_started(self):
        step = self.startStep()
        self.collector.handle_step_started(step)

        self.mock_increment.assert_called_once_with('trun.step.started', 1, tags=['step_name:DDStepName',
                                                                                   'environment:development',
                                                                                   'application:trun'])

    def test_send_event_on_step_failed(self):
        step = self.startStep()
        self.collector.handle_step_failed(step)

        self.mock_create.assert_called_once_with(alert_type='error',
                                                 priority='normal',
                                                 tags=['step_name:DDStepName',
                                                       'step_state:FAILED',
                                                       'environment:development',
                                                       'application:trun'],
                                                 text='A step has failed in the pipeline named: DDStepName',
                                                 title='Trun: A step has failed!')

    def test_send_increment_on_step_failed(self):
        step = self.startStep()
        self.collector.handle_step_failed(step)

        self.mock_increment.assert_called_once_with('trun.step.failed', 1, tags=['step_name:DDStepName',
                                                                                  'environment:development',
                                                                                  'application:trun'])

    def test_send_event_on_step_disabled(self):
        s = Scheduler(metrics_collector=MetricsCollectors.datadog, disable_persist=10, retry_count=2, disable_window=2)
        step = self.startStep(scheduler=s)
        self.collector.handle_step_disabled(step, s._config)

        self.mock_create.assert_called_once_with(alert_type='error',
                                                 priority='normal',
                                                 tags=['step_name:DDStepName',
                                                       'step_state:DISABLED',
                                                       'environment:development',
                                                       'application:trun'],
                                                 text='A step has been disabled in the pipeline named: DDStepName. ' +
                                                      'The step has failed 2 times in the last 2 seconds' +
                                                      ', so it is being disabled for 10 seconds.',
                                                 title='Trun: A step has been disabled!')

    def test_send_increment_on_step_disabled(self):
        step = self.startStep()
        self.collector.handle_step_disabled(step, self.s._config)

        self.mock_increment.assert_called_once_with('trun.step.disabled', 1, tags=['step_name:DDStepName',
                                                                                    'environment:development',
                                                                                    'application:trun'])

    def test_send_event_on_step_done(self):
        step = self.startStep()
        self.collector.handle_step_done(step)

        self.mock_create.assert_called_once_with(alert_type='info',
                                                 priority='low',
                                                 tags=['step_name:DDStepName',
                                                       'step_state:DONE',
                                                       'environment:development',
                                                       'application:trun'],
                                                 text='A step has completed in the pipeline named: DDStepName',
                                                 title='Trun: A step has been completed!')

    def test_send_increment_on_step_done(self):
        step = self.startStep()
        self.collector.handle_step_done(step)

        self.mock_increment.assert_called_once_with('trun.step.done', 1, tags=['step_name:DDStepName',
                                                                                'environment:development',
                                                                                'application:trun'])

    def test_send_gauge_on_step_done(self):
        self.setTime(0)
        step = self.startStep()
        self.collector.handle_step_done(step)

        self.mock_gauge.assert_called_once_with('trun.step.execution_time', 0, tags=['step_name:DDStepName',
                                                                                      'environment:development',
                                                                                      'application:trun'])
