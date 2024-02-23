import unittest

import trun.metrics as metrics

from trun.contrib.datadog_metric import DatadogMetricsCollector
from trun.contrib.prometheus_metric import PrometheusMetricsCollector


class TestMetricsCollectors(unittest.TestCase):
    def test_default_value(self):
        collector = metrics.MetricsCollectors.default
        output = metrics.MetricsCollectors.get(collector)

        assert type(output) is metrics.NoMetricsCollector

    def test_datadog_value(self):
        collector = metrics.MetricsCollectors.datadog
        output = metrics.MetricsCollectors.get(collector)

        assert type(output) is DatadogMetricsCollector

    def test_prometheus_value(self):
        collector = metrics.MetricsCollectors.prometheus
        output = metrics.MetricsCollectors.get(collector)

        assert type(output) is PrometheusMetricsCollector

    def test_none_value(self):
        collector = metrics.MetricsCollectors.none
        output = metrics.MetricsCollectors.get(collector)

        assert type(output) is metrics.NoMetricsCollector

    def test_other_value(self):
        collector = 'junk'

        with self.assertRaises(ValueError) as context:
            metrics.MetricsCollectors.get(collector)
            assert ("MetricsCollectors value ' junk ' isn't supported") in str(context.exception)
