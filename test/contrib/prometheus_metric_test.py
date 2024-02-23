from helpers import unittest
import pytest
from prometheus_client import CONTENT_TYPE_LATEST

from luigi.contrib.prometheus_metric import PrometheusMetricsCollector
from luigi.metrics import MetricsCollectors
from luigi.scheduler import Scheduler

try:
    from unittest import mock
except ImportError:
    import mock


WORKER = 'myworker'
STEP_ID = 'StepID'
STEP_FAMILY = 'StepFamily'


@pytest.mark.contrib
class PrometheusMetricTest(unittest.TestCase):
    def setUp(self):
        self.collector = PrometheusMetricsCollector()
        self.s = Scheduler(metrics_collector=MetricsCollectors.prometheus)
        self.gauge_name = 'luigi_step_execution_time_seconds'
        self.labels = {'family': STEP_FAMILY}

    def startStep(self):
        self.s.add_step(worker=WORKER, step_id=STEP_ID, family=STEP_FAMILY)
        step = self.s._state.get_step(STEP_ID)
        step.time_running = 0
        step.updated = 5
        return step

    def test_handle_step_started(self):
        step = self.startStep()
        self.collector.handle_step_started(step)

        counter_name = 'luigi_step_started_total'
        gauge_name = self.gauge_name
        labels = self.labels

        assert self.collector.registry.get_sample_value(counter_name, labels=self.labels) == 1
        assert self.collector.registry.get_sample_value(gauge_name, labels=labels) == 0

    def test_handle_step_failed(self):
        step = self.startStep()
        self.collector.handle_step_failed(step)

        counter_name = 'luigi_step_failed_total'
        gauge_name = self.gauge_name
        labels = self.labels

        assert self.collector.registry.get_sample_value(counter_name, labels=labels) == 1
        assert self.collector.registry.get_sample_value(gauge_name, labels=labels) == step.updated - step.time_running

    def test_handle_step_disabled(self):
        step = self.startStep()
        self.collector.handle_step_disabled(step, self.s._config)

        counter_name = 'luigi_step_disabled_total'
        gauge_name = self.gauge_name
        labels = self.labels

        assert self.collector.registry.get_sample_value(counter_name, labels=labels) == 1
        assert self.collector.registry.get_sample_value(gauge_name, labels=labels) == step.updated - step.time_running

    def test_handle_step_done(self):
        step = self.startStep()
        self.collector.handle_step_done(step)

        counter_name = 'luigi_step_done_total'
        gauge_name = self.gauge_name
        labels = self.labels

        assert self.collector.registry.get_sample_value(counter_name, labels=labels) == 1
        assert self.collector.registry.get_sample_value(gauge_name, labels=labels) == step.updated - step.time_running

    def test_configure_http_handler(self):
        mock_http_handler = mock.MagicMock()
        self.collector.configure_http_handler(mock_http_handler)
        mock_http_handler.set_header.assert_called_once_with('Content-Type', CONTENT_TYPE_LATEST)
