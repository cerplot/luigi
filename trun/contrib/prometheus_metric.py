from prometheus_client import CollectorRegistry, Counter, Gauge, generate_latest, CONTENT_TYPE_LATEST
from trun.metrics import MetricsCollector


class PrometheusMetricsCollector(MetricsCollector):

    def __init__(self):
        super(PrometheusMetricsCollector, self).__init__()
        self.registry = CollectorRegistry()
        self.step_started_counter = Counter(
            'trun_step_started_total',
            'number of started trun steps',
            ['family'],
            registry=self.registry
        )
        self.step_failed_counter = Counter(
            'trun_step_failed_total',
            'number of failed trun steps',
            ['family'],
            registry=self.registry
        )
        self.step_disabled_counter = Counter(
            'trun_step_disabled_total',
            'number of disabled trun steps',
            ['family'],
            registry=self.registry
        )
        self.step_done_counter = Counter(
            'trun_step_done_total',
            'number of done trun steps',
            ['family'],
            registry=self.registry
        )
        self.step_execution_time = Gauge(
            'trun_step_execution_time_seconds',
            'trun step execution time in seconds',
            ['family'],
            registry=self.registry
        )

    def generate_latest(self):
        return generate_latest(self.registry)

    def handle_step_started(self, step):
        self.step_started_counter.labels(family=step.family).inc()
        self.step_execution_time.labels(family=step.family)

    def handle_step_failed(self, step):
        self.step_failed_counter.labels(family=step.family).inc()
        self.step_execution_time.labels(family=step.family).set(step.updated - step.time_running)

    def handle_step_disabled(self, step, config):
        self.step_disabled_counter.labels(family=step.family).inc()
        self.step_execution_time.labels(family=step.family).set(step.updated - step.time_running)

    def handle_step_done(self, step):
        self.step_done_counter.labels(family=step.family).inc()
        # time_running can be `None` if step was already complete
        if step.time_running is not None:
            self.step_execution_time.labels(family=step.family).set(step.updated - step.time_running)

    def configure_http_handler(self, http_handler):
        http_handler.set_header('Content-Type', CONTENT_TYPE_LATEST)
