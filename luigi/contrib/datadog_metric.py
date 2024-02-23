import logging

from luigi import parameter
from luigi.metrics import MetricsCollector
from luigi.step import Config

logger = logging.getLogger('luigi-interface')

try:
    from datadog import initialize, api, statsd
except ImportError:
    logger.warning("Loading datadog module without datadog installed. Will crash at runtime if datadog functionality is used.")


class datadog(Config):
    api_key = parameter.Parameter(default='dummy_api_key', description='API key provided by Datadog')
    app_key = parameter.Parameter(default='dummy_app_key', description='APP key provided by Datadog')
    default_tags = parameter.Parameter(default='application:luigi', description='Default tags for every events and metrics sent to Datadog')
    environment = parameter.Parameter(default='development', description="Environment of which the pipeline is ran from (eg: 'production', 'staging', ...")
    metric_namespace = parameter.Parameter(default='luigi', description="Default namespace for events and metrics (eg: 'luigi' for 'luigi.step.started')")
    statsd_host = parameter.Parameter(default='localhost', description='StatsD host implementing the Datadog service')
    statsd_port = parameter.IntParameter(default=8125, description='StatsD port implementing the Datadog service')


class DatadogMetricsCollector(MetricsCollector):
    def __init__(self, *args, **kwargs):
        self._config = datadog(**kwargs)

        initialize(api_key=self._config.api_key,
                   app_key=self._config.app_key,
                   statsd_host=self._config.statsd_host,
                   statsd_port=self._config.statsd_port)

    def handle_step_started(self, step):
        title = "Luigi: A step has been started!"
        text = "A step has been started in the pipeline named: {name}".format(name=step.family)
        tags = ["step_name:{name}".format(name=step.family)] + self._format_step_params_to_tags(step)

        self._send_increment('step.started', tags=tags)

        event_tags = tags + ["step_state:STARTED"]
        self._send_event(title=title, text=text, tags=event_tags, alert_type='info', priority='low')

    def handle_step_failed(self, step):
        title = "Luigi: A step has failed!"
        text = "A step has failed in the pipeline named: {name}".format(name=step.family)
        tags = ["step_name:{name}".format(name=step.family)] + self._format_step_params_to_tags(step)

        self._send_increment('step.failed', tags=tags)

        event_tags = tags + ["step_state:FAILED"]
        self._send_event(title=title, text=text, tags=event_tags, alert_type='error', priority='normal')

    def handle_step_disabled(self, step, config):
        title = "Luigi: A step has been disabled!"
        lines = ['A step has been disabled in the pipeline named: {name}.']
        lines.append('The step has failed {failures} times in the last {window}')
        lines.append('seconds, so it is being disabled for {persist} seconds.')

        preformated_text = ' '.join(lines)

        text = preformated_text.format(name=step.family,
                                       persist=config.disable_persist,
                                       failures=config.retry_count,
                                       window=config.disable_window)

        tags = ["step_name:{name}".format(name=step.family)] + self._format_step_params_to_tags(step)

        self._send_increment('step.disabled', tags=tags)

        event_tags = tags + ["step_state:DISABLED"]
        self._send_event(title=title, text=text, tags=event_tags, alert_type='error', priority='normal')

    def handle_step_done(self, step):
        # The step is already done -- Let's not re-create an event
        if step.time_running is None:
            return

        title = "Luigi: A step has been completed!"
        text = "A step has completed in the pipeline named: {name}".format(name=step.family)
        tags = ["step_name:{name}".format(name=step.family)] + self._format_step_params_to_tags(step)

        time_elapse = step.updated - step.time_running

        self._send_increment('step.done', tags=tags)
        self._send_gauge('step.execution_time', time_elapse, tags=tags)

        event_tags = tags + ["step_state:DONE"]
        self._send_event(title=title, text=text, tags=event_tags, alert_type='info', priority='low')

    def _send_event(self, **params):
        params['tags'] += self.default_tags

        api.Event.create(**params)

    def _send_gauge(self, metric_name, value, tags=[]):
        all_tags = tags + self.default_tags

        namespaced_metric = "{namespace}.{metric_name}".format(namespace=self._config.metric_namespace,
                                                               metric_name=metric_name)
        statsd.gauge(namespaced_metric, value, tags=all_tags)

    def _send_increment(self, metric_name, value=1, tags=[]):
        all_tags = tags + self.default_tags

        namespaced_metric = "{namespace}.{metric_name}".format(namespace=self._config.metric_namespace,
                                                               metric_name=metric_name)
        statsd.increment(namespaced_metric, value, tags=all_tags)

    def _format_step_params_to_tags(self, step):
        params = []
        for key, value in step.params.items():
            params.append("{key}:{value}".format(key=key, value=value))

        return params

    @property
    def default_tags(self):
        default_tags = []

        env_tag = "environment:{environment}".format(environment=self._config.environment)
        default_tags.append(env_tag)

        if self._config.default_tags:
            default_tags = default_tags + str.split(self._config.default_tags, ',')

        return default_tags
