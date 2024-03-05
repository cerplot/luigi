"""
Simple REST server that takes commands in a JSON payload
Interface to the :py:class:`~trun.scheduler.Scheduler` class.
See :doc:`/central_scheduler` for more info.
"""
#
# Description: Added codes for visualization of how long each step takes
# running-time until it reaches the next status (failed or done)
# At "{base_url}/steplist", all completed(failed or done) steps are shown.
# At "{base_url}/steplist", a user can select one specific step to see
# how its running-time has changed over time.
# At "{base_url}/steplist/{step_name}", it visualizes a multi-bar graph
# that represents the changes of the running-time for a selected step
# up to the next status (failed or done).
# This visualization let us know how the running-time of the specific step
# has changed over time.
#

import atexit
import datetime
import json
import logging
import os
import signal
import sys
import time

import pkg_resources
import tornado.httpserver
import tornado.ioloop
import tornado.netutil
import tornado.web

from trun import Config, parameter
from trun.scheduler import Scheduler, RPC_METHODS

logger = logging.getLogger("trun.server")


class cors(Config):
    enabled = parameter.BoolParameter(
        default=False,
        description='Enables CORS support.')
    allowed_origins = parameter.ListParameter(
        default=[],
        description='A list of allowed origins. Used only if `allow_any_origin` is false.')
    allow_any_origin = parameter.BoolParameter(
        default=False,
        description='Accepts requests from any origin.')
    allow_null_origin = parameter.BoolParameter(
        default=False,
        description='Allows the request to set `null` value of the `Origin` header.')
    max_age = parameter.IntParameter(
        default=86400,
        description='Content of `Access-Control-Max-Age`.')
    allowed_methods = parameter.Parameter(
        default='GET, OPTIONS',
        description='Content of `Access-Control-Allow-Methods`.')
    allowed_headers = parameter.Parameter(
        default='Accept, Content-Type, Origin',
        description='Content of `Access-Control-Allow-Headers`.')
    exposed_headers = parameter.Parameter(
        default='',
        description='Content of `Access-Control-Expose-Headers`.')
    allow_credentials = parameter.BoolParameter(
        default=False,
        description='Indicates that the actual request can include user credentials.')

    def __init__(self, *args, **kwargs):
        super(cors, self).__init__(*args, **kwargs)
        self.allowed_origins = set(i for i in self.allowed_origins if i not in ['*', 'null'])


class RPCHandler(tornado.web.RequestHandler):
    """
    Handle remote scheduling calls using rpc.RemoteSchedulerResponder.
    """

    def __init__(self, *args, **kwargs):
        super(RPCHandler, self).__init__(*args, **kwargs)
        self._cors_config = cors()

    def initialize(self, scheduler):
        self._scheduler = scheduler

    def options(self, *args):
        if self._cors_config.enabled:
            self._handle_cors_preflight()

        self.set_status(204)
        self.finish()

    def get(self, method):
        if method not in RPC_METHODS:
            self.send_error(404)
            return
        payload = self.get_argument('data', default="{}")
        arguments = json.loads(payload)

        if hasattr(self._scheduler, method):
            result = getattr(self._scheduler, method)(**arguments)

            if self._cors_config.enabled:
                self._handle_cors()

            self.write({"response": result})  # wrap all json response in a dictionary
        else:
            self.send_error(404)

    post = get

    def _handle_cors_preflight(self):
        origin = self.request.headers.get('Origin')
        if not origin:
            return

        if origin == 'null':
            if self._cors_config.allow_null_origin:
                self.set_header('Access-Control-Allow-Origin', 'null')
                self._set_other_cors_headers()
        else:
            if self._cors_config.allow_any_origin:
                self.set_header('Access-Control-Allow-Origin', '*')
                self._set_other_cors_headers()
            elif origin in self._cors_config.allowed_origins:
                self.set_header('Access-Control-Allow-Origin', origin)
                self._set_other_cors_headers()

    def _handle_cors(self):
        origin = self.request.headers.get('Origin')
        if not origin:
            return

        if origin == 'null':
            if self._cors_config.allow_null_origin:
                self.set_header('Access-Control-Allow-Origin', 'null')
        else:
            if self._cors_config.allow_any_origin:
                self.set_header('Access-Control-Allow-Origin', '*')
            elif origin in self._cors_config.allowed_origins:
                self.set_header('Access-Control-Allow-Origin', origin)
                self.set_header('Vary', 'Origin')

    def _set_other_cors_headers(self):
        self.set_header('Access-Control-Max-Age', str(self._cors_config.max_age))
        self.set_header('Access-Control-Allow-Methods', self._cors_config.allowed_methods)
        self.set_header('Access-Control-Allow-Headers', self._cors_config.allowed_headers)
        if self._cors_config.allow_credentials:
            self.set_header('Access-Control-Allow-Credentials', 'true')
        if self._cors_config.exposed_headers:
            self.set_header('Access-Control-Expose-Headers', self._cors_config.exposed_headers)


class BaseStepHistoryHandler(tornado.web.RequestHandler):
    def initialize(self, scheduler):
        self._scheduler = scheduler

    def get_template_path(self):
        return pkg_resources.resource_filename(__name__, 'templates')


class AllRunHandler(BaseStepHistoryHandler):
    def get(self):
        all_steps = self._scheduler.step_history.find_all_runs()
        stepnames = [step.name for step in all_steps]
        # show all steps with their name list to be selected
        # why all steps? the duration of the event history of a selected step
        # can be more than 24 hours.
        self.render("menu.html", stepnames=stepnames)


class SelectedRunHandler(BaseStepHistoryHandler):
    def get(self, name):
        statusResults = {}
        stepResults = []
        # get all steps that has been updated
        all_steps = self._scheduler.step_history.find_all_runs()
        # get events history for all steps
        all_steps_event_history = self._scheduler.step_history.find_all_events()

        # build the dictionary steps with index: id, value: step_name
        steps = {step.id: str(step.name) for step in all_steps}

        for step in all_steps_event_history:
            # if the name of user-selected step is in steps, get its step_id
            if steps.get(step.step_id) == str(name):
                status = str(step.event_name)
                if status not in statusResults:
                    statusResults[status] = []
                # append the id, step_id, ts, y with 0, next_process with null
                # for the status(running/failed/done) of the selected step
                statusResults[status].append(({
                                                  'id': str(step.id), 'step_id': str(step.step_id),
                                                  'x': from_utc(str(step.ts)), 'y': 0, 'next_process': ''}))
                # append the id, step_name, step_id, status, datetime, timestamp
                # for the selected step
                stepResults.append({
                    'id': str(step.id), 'stepName': str(name), 'step_id': str(step.step_id),
                    'status': str(step.event_name), 'datetime': str(step.ts),
                    'timestamp': from_utc(str(step.ts))})
        statusResults = json.dumps(statusResults)
        stepResults = json.dumps(stepResults)
        statusResults = tornado.escape.xhtml_unescape(str(statusResults))
        stepResults = tornado.escape.xhtml_unescape(str(stepResults))
        self.render('history.html', name=name, statusResults=statusResults, stepResults=stepResults)


def from_utc(utcTime, fmt=None):
    """convert UTC time string to time.struct_time: change datetime.datetime to time, return time.struct_time type"""
    if fmt is None:
        try_formats = ["%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"]
    else:
        try_formats = [fmt]

    for fmt in try_formats:
        try:
            time_struct = datetime.datetime.strptime(utcTime, fmt)
        except ValueError:
            pass
        else:
            date = int(time.mktime(time_struct.timetuple()))
            return date
    else:
        raise ValueError("No UTC format matches {}".format(utcTime))


class RecentRunHandler(BaseStepHistoryHandler):
    def get(self):
        with self._scheduler.step_history._session(None) as session:
            steps = self._scheduler.step_history.find_latest_runs(session)
            self.render("recent.html", steps=steps)


class ByNameHandler(BaseStepHistoryHandler):
    def get(self, name):
        with self._scheduler.step_history._session(None) as session:
            steps = self._scheduler.step_history.find_all_by_name(name, session)
            self.render("recent.html", steps=steps)


class ByIdHandler(BaseStepHistoryHandler):
    def get(self, id):
        with self._scheduler.step_history._session(None) as session:
            step = self._scheduler.step_history.find_step_by_id(id, session)
            self.render("show.html", step=step)


class ByParamsHandler(BaseStepHistoryHandler):
    def get(self, name):
        payload = self.get_argument('data', default="{}")
        arguments = json.loads(payload)
        with self._scheduler.step_history._session(None) as session:
            steps = self._scheduler.step_history.find_all_by_parameters(name, session=session, **arguments)
            self.render("recent.html", steps=steps)


class RootPathHandler(BaseStepHistoryHandler):
    def get(self):
        # we omit the leading slash in case the visualizer is behind a different
        # path (as in a reverse proxy setup)
        #
        # For example, if trun is behind my.app.com/my/trun/, we want / to
        # redirect relative (so it goes to my.app.com/my/trun/static/visualizer/index.html)
        # instead of absolute (which would be my.app.com/static/visualizer/index.html)
        self.redirect("static/visualiser/index.html")

    def head(self):
        """HEAD endpoint for health checking the scheduler"""
        self.set_status(204)
        self.finish()


class MetricsHandler(tornado.web.RequestHandler):
    def initialize(self, scheduler):
        self._scheduler = scheduler

    def get(self):
        metrics_collector = self._scheduler._state._metrics_collector
        metrics = metrics_collector.generate_latest()
        if metrics:
            metrics_collector.configure_http_handler(self)
            self.write(metrics)


def app(scheduler):
    settings = {"static_path": os.path.join(os.path.dirname(__file__), "static"),
                "unescape": tornado.escape.xhtml_unescape,
                "compress_response": True,
                }
    handlers = [
        (r'/api/(.*)', RPCHandler, {"scheduler": scheduler}),
        (r'/', RootPathHandler, {'scheduler': scheduler}),
        (r'/steplist', AllRunHandler, {'scheduler': scheduler}),
        (r'/steplist/(.*?)', SelectedRunHandler, {'scheduler': scheduler}),
        (r'/history', RecentRunHandler, {'scheduler': scheduler}),
        (r'/history/by_name/(.*?)', ByNameHandler, {'scheduler': scheduler}),
        (r'/history/by_id/(.*?)', ByIdHandler, {'scheduler': scheduler}),
        (r'/history/by_params/(.*?)', ByParamsHandler, {'scheduler': scheduler}),
        (r'/metrics', MetricsHandler, {'scheduler': scheduler})
    ]
    api_app = tornado.web.Application(handlers, **settings)
    return api_app


def _init_api(scheduler, api_port=None, address=None, unix_socket=None):
    api_app = app(scheduler)
    if unix_socket is not None:
        api_sockets = [tornado.netutil.bind_unix_socket(unix_socket)]
    else:
        api_sockets = tornado.netutil.bind_sockets(api_port, address=address)
    server = tornado.httpserver.HTTPServer(api_app)
    server.add_sockets(api_sockets)

    # Return the bound socket names.  Useful for connecting client in test scenarios.
    return [s.getsockname() for s in api_sockets]


def run(api_port=8082, address=None, unix_socket=None, scheduler=None):
    """
    Runs one instance of the API server.
    """
    if scheduler is None:
        scheduler = Scheduler()

    # load scheduler state
    scheduler.load()

    _init_api(
        scheduler=scheduler,
        api_port=api_port,
        address=address,
        unix_socket=unix_socket,
    )

    # prune work DAG every 60 seconds
    pruner = tornado.ioloop.PeriodicCallback(scheduler.prune, 60000)
    pruner.start()

    def shutdown_handler(signum, frame):
        exit_handler()
        sys.exit(0)

    @atexit.register
    def exit_handler():
        logger.info("Scheduler instance shutting down")
        scheduler.dump()
        stop()

    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)
    if os.name == 'nt':
        signal.signal(signal.SIGBREAK, shutdown_handler)
    else:
        signal.signal(signal.SIGQUIT, shutdown_handler)

    logger.info("Scheduler starting up")

    tornado.ioloop.IOLoop.instance().start()


def stop():
    tornado.ioloop.IOLoop.instance().stop()


if __name__ == "__main__":
    run()