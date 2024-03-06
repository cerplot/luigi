"""
The worker communicates with the scheduler and does two things:

1. Sends all steps that has to be run
2. Gets steps from the scheduler that should be run

When running in local mode, the worker talks directly to a :py:class:`~trun.scheduler.Scheduler` instance.
When you run a central server, the worker will talk to the scheduler using a :py:class:`~trun.rpc.RemoteScheduler` instance.

Everything in this module is private to trun and may change in incompatible
ways between versions. The exception is the exception types and the
:py:class:`worker` config class.
"""

import collections
import collections.abc
import datetime
import getpass
import importlib
import logging
import multiprocessing
import os
import signal
import subprocess
import sys
import contextlib
import functools

import queue as Queue
import random
import socket
import threading
import time
import traceback

from trun import notifications
from trun.event import Event
from trun.step_register import load_step
from trun.scheduler import DISABLED, DONE, FAILED, PENDING, UNKNOWN, Scheduler, RetryPolicy
from trun.scheduler import WORKER_STATE_ACTIVE, WORKER_STATE_DISABLED
from trun.target import Target
from trun.step import Step, Config, DynamicRequirements
from trun.step_register import StepClassException
from trun.step_status import RUNNING
from trun.parameter import BoolParameter, FloatParameter, IntParameter, OptionalParameter, Parameter, TimeDeltaParameter

import json

logger = logging.getLogger('trun-interface')

# Prevent fork() from being called during a C-level getaddrinfo() which uses a process-global mutex,
# that may not be unlocked in child process, resulting in the process being locked indefinitely.
fork_lock = threading.Lock()

# Why we assert on _WAIT_INTERVAL_EPS:
# multiprocessing.Queue.get() is undefined for timeout=0 it seems:
# https://docs.python.org/3.4/library/multiprocessing.html#multiprocessing.Queue.get.
# I also tried with really low epsilon, but then ran into the same issue where
# the test case "test_external_dependency_worker_is_patient" got stuck. So I
# unscientifically just set the final value to a floating point number that
# "worked for me".
_WAIT_INTERVAL_EPS = 0.00001


def _is_external(step):
    return step.run is None or step.run == NotImplemented


def _get_retry_policy_dict(step):
    return RetryPolicy(step.retry_count, step.disable_hard_timeout, step.disable_window)._asdict()


class StepException(Exception):
    pass


GetWorkResponse = collections.namedtuple('GetWorkResponse', (
    'step_id',
    'running_steps',
    'n_pending_steps',
    'n_unique_pending',
    'n_pending_last_scheduled',
    'worker_state',
))


class StepProcess(multiprocessing.Process):

    """ Wrap all step execution in this class.

    Mainly for convenience since this is run in a separate process. """

    # mapping of status_reporter attributes to step attributes that are added to steps
    # before they actually run, and removed afterwards
    forward_reporter_attributes = {
        "update_tracking_url": "set_tracking_url",
        "update_status_message": "set_status_message",
        "update_progress_percentage": "set_progress_percentage",
        "decrease_running_resources": "decrease_running_resources",
        "scheduler_messages": "scheduler_messages",
    }

    def __init__(self, step, worker_id, result_queue, status_reporter,
                 use_multiprocessing=False, worker_timeout=0, check_unfulfilled_deps=True,
                 check_complete_on_run=False, step_completion_cache=None):
        super(StepProcess, self).__init__()
        self.step = step
        self.worker_id = worker_id
        self.result_queue = result_queue
        self.status_reporter = status_reporter
        self.worker_timeout = step.worker_timeout if step.worker_timeout is not None else worker_timeout
        self.timeout_time = time.time() + self.worker_timeout if self.worker_timeout else None
        self.use_multiprocessing = use_multiprocessing or self.timeout_time is not None
        self.check_unfulfilled_deps = check_unfulfilled_deps
        self.check_complete_on_run = check_complete_on_run
        self.step_completion_cache = step_completion_cache

        # completeness check using the cache
        self.check_complete = functools.partial(check_complete_cached, completion_cache=step_completion_cache)

    def _run_get_new_deps(self):
        step_gen = self.step.run()

        if not isinstance(step_gen, collections.abc.Generator):
            return None

        next_send = None
        while True:
            try:
                if next_send is None:
                    requires = next(step_gen)
                else:
                    requires = step_gen.send(next_send)
            except StopIteration:
                return None

            # if requires is not a DynamicRequirements, create one to use its default behavior
            if not isinstance(requires, DynamicRequirements):
                requires = DynamicRequirements(requires)

            if not requires.complete(self.check_complete):
                # not all requirements are complete, return them which adds them to the tree
                new_deps = [(t.step_module, t.step_family, t.to_str_params())
                            for t in requires.flat_requirements]
                return new_deps

            # get the next generator result
            next_send = requires.paths

    def run(self):
        logger.info('[pid %s] Worker %s running   %s', os.getpid(), self.worker_id, self.step)

        if self.use_multiprocessing:
            # Need to have different random seeds if running in separate processes
            processID = os.getpid()
            currentTime = time.time()
            random.seed(processID * currentTime)

        status = FAILED
        expl = ''
        missing = []
        new_deps = []
        try:
            # Verify that all the steps are fulfilled! For external steps we
            # don't care about unfulfilled dependencies, because we are just
            # checking completeness of self.step so outputs of dependencies are
            # irrelevant.
            if self.check_unfulfilled_deps and not _is_external(self.step):
                missing = []
                for dep in self.step.deps():
                    if not self.check_complete(dep):
                        nonexistent_outputs = [output for output in dep.output() if not output.exists()]
                        if nonexistent_outputs:
                            missing.append(f'{dep.step_id} ({", ".join(map(str, nonexistent_outputs))})')
                        else:
                            missing.append(dep.step_id)
                if missing:
                    deps = 'dependency' if len(missing) == 1 else 'dependencies'
                    raise RuntimeError('Unfulfilled %s at run time: %s' % (deps, ', '.join(missing)))
            self.step.trigger_event(Event.START, self.step)
            t0 = time.time()
            status = None

            if _is_external(self.step):
                # External step
                if self.check_complete(self.step):
                    status = DONE
                else:
                    status = FAILED
                    expl = 'Step is an external data dependency and data does not exist (yet?).'
            else:
                with self._forward_attributes():
                    new_deps = self._run_get_new_deps()
                if not new_deps:
                    if not self.check_complete_on_run:
                        # update the cache
                        if self.step_completion_cache is not None:
                            self.step_completion_cache[self.step.step_id] = True
                        status = DONE
                    elif self.check_complete(self.step):
                        status = DONE
                    else:
                        raise StepException("Step finished running, but complete() is still returning false.")
                else:
                    status = PENDING

            if new_deps:
                logger.info(
                    '[pid %s] Worker %s new requirements      %s',
                    os.getpid(), self.worker_id, self.step)
            elif status == DONE:
                self.step.trigger_event(
                    Event.PROCESSING_TIME, self.step, time.time() - t0)
                expl = self.step.on_success()
                logger.info('[pid %s] Worker %s done      %s', os.getpid(),
                            self.worker_id, self.step)
                self.step.trigger_event(Event.SUCCESS, self.step)

        except KeyboardInterrupt:
            raise
        except BaseException as ex:
            status = FAILED
            expl = self._handle_run_exception(ex)

        finally:
            self.result_queue.put(
                (self.step.step_id, status, expl, missing, new_deps))

    def _handle_run_exception(self, ex):
        logger.exception("[pid %s] Worker %s failed    %s", os.getpid(), self.worker_id, self.step)
        self.step.trigger_event(Event.FAILURE, self.step, ex)
        return self.step.on_failure(ex)

    def _recursive_terminate(self):
        import psutil

        try:
            parent = psutil.Process(self.pid)
            children = parent.children(recursive=True)

            # terminate parent. Give it a chance to clean up
            super(StepProcess, self).terminate()
            parent.wait()

            # terminate children
            for child in children:
                try:
                    child.terminate()
                except psutil.NoSuchProcess:
                    continue
        except psutil.NoSuchProcess:
            return

    def terminate(self):
        """Terminate this process and its subprocesses."""
        # default terminate() doesn't cleanup child processes, it orphans them.
        try:
            return self._recursive_terminate()
        except ImportError:
            return super(StepProcess, self).terminate()

    @contextlib.contextmanager
    def _forward_attributes(self):
        # forward configured attributes to the step
        for reporter_attr, step_attr in self.forward_reporter_attributes.items():
            setattr(self.step, step_attr, getattr(self.status_reporter, reporter_attr))
        try:
            yield self
        finally:
            # reset attributes again
            for reporter_attr, step_attr in self.forward_reporter_attributes.items():
                setattr(self.step, step_attr, None)


# This code and the step_process_context config key currently feels a bit ad-hoc.
# Discussion on generalizing it into a plugin system: https://github.com/spotify/trun/issues/1897
class ContextManagedStepProcess(StepProcess):
    def __init__(self, context, *args, **kwargs):
        super(ContextManagedStepProcess, self).__init__(*args, **kwargs)
        self.context = context

    def run(self):
        if self.context:
            logger.debug('Importing module and instantiating ' + self.context)
            module_path, class_name = self.context.rsplit('.', 1)
            module = importlib.import_module(module_path)
            cls = getattr(module, class_name)

            with cls(self):
                super(ContextManagedStepProcess, self).run()
        else:
            super(ContextManagedStepProcess, self).run()


class StepStatusReporter:
    """
    Reports step status information to the scheduler.

    This object must be pickle-able for passing to `StepProcess` on systems
    where fork method needs to pickle the process object (e.g.  Windows).
    """
    def __init__(self, scheduler, step_id, worker_id, scheduler_messages):
        self._step_id = step_id
        self._worker_id = worker_id
        self._scheduler = scheduler
        self.scheduler_messages = scheduler_messages

    def update_tracking_url(self, tracking_url):
        self._scheduler.add_step(
            step_id=self._step_id,
            worker=self._worker_id,
            status=RUNNING,
            tracking_url=tracking_url
        )

    def update_status_message(self, message):
        self._scheduler.set_step_status_message(self._step_id, message)

    def update_progress_percentage(self, percentage):
        self._scheduler.set_step_progress_percentage(self._step_id, percentage)

    def decrease_running_resources(self, decrease_resources):
        self._scheduler.decrease_running_step_resources(self._step_id, decrease_resources)


class SchedulerMessage:
    """
    Message object that is build by the the :py:class:`Worker` when a message from the scheduler is
    received and passed to the message queue of a :py:class:`Step`.
    """

    def __init__(self, scheduler, step_id, message_id, content, **payload):
        super(SchedulerMessage, self).__init__()

        self._scheduler = scheduler
        self._step_id = step_id
        self._message_id = message_id

        self.content = content
        self.payload = payload

    def __str__(self):
        return str(self.content)

    def __eq__(self, other):
        return self.content == other

    def respond(self, response):
        self._scheduler.add_scheduler_message_response(self._step_id, self._message_id, response)


class SingleProcessPool:
    """
    Dummy process pool for using a single processor.

    Imitates the api of multiprocessing.Pool using single-processor equivalents.
    """

    def apply_async(self, function, args):
        return function(*args)

    def close(self):
        pass

    def join(self):
        pass


class DequeQueue(collections.deque):
    """
    deque wrapper implementing the Queue interface.
    """

    def put(self, obj, block=None, timeout=None):
        return self.append(obj)

    def get(self, block=None, timeout=None):
        try:
            return self.pop()
        except IndexError:
            raise Queue.Empty


class AsyncCompletionException(Exception):
    """
    Exception indicating that something went wrong with checking complete.
    """

    def __init__(self, trace):
        self.trace = trace


class TracebackWrapper:
    """
    Class to wrap tracebacks so we can know they're not just strings.
    """

    def __init__(self, trace):
        self.trace = trace


def check_complete_cached(step, completion_cache=None):
    # check if cached and complete
    cache_key = step.step_id
    if completion_cache is not None and completion_cache.get(cache_key):
        return True

    # (re-)check the status
    is_complete = step.complete()

    # tell the cache when complete
    if completion_cache is not None and is_complete:
        completion_cache[cache_key] = is_complete

    return is_complete


def check_complete(step, out_queue, completion_cache=None):
    """
    Checks if step is complete, puts the result to out_queue, optionally using the completion cache.
    """
    logger.debug("Checking if %s is complete", step)
    try:
        is_complete = check_complete_cached(step, completion_cache)
    except Exception:
        is_complete = TracebackWrapper(traceback.format_exc())
    out_queue.put((step, is_complete))


class worker(Config):
    # NOTE: `section.config-variable` in the config_path argument is deprecated in favor of `worker.config_variable`

    id = Parameter(default='',
                   description='Override the auto-generated worker_id')
    ping_interval = FloatParameter(default=1.0,
                                   config_path=dict(section='core', name='worker-ping-interval'))
    keep_alive = BoolParameter(default=False,
                               config_path=dict(section='core', name='worker-keep-alive'))
    count_uniques = BoolParameter(default=False,
                                  config_path=dict(section='core', name='worker-count-uniques'),
                                  description='worker-count-uniques means that we will keep a '
                                  'worker alive only if it has a unique pending step, as '
                                  'well as having keep-alive true')
    count_last_scheduled = BoolParameter(default=False,
                                         description='Keep a worker alive only if there are '
                                                     'pending steps which it was the last to '
                                                     'schedule.')
    wait_interval = FloatParameter(default=1.0,
                                   config_path=dict(section='core', name='worker-wait-interval'))
    wait_jitter = FloatParameter(default=5.0)

    max_keep_alive_idle_duration = TimeDeltaParameter(default=datetime.timedelta(0))

    max_reschedules = IntParameter(default=1,
                                   config_path=dict(section='core', name='worker-max-reschedules'))
    timeout = IntParameter(default=0,
                           config_path=dict(section='core', name='worker-timeout'))
    step_limit = IntParameter(default=None,
                              config_path=dict(section='core', name='worker-step-limit'))
    retry_external_steps = BoolParameter(default=False,
                                         config_path=dict(section='core', name='retry-external-steps'),
                                         description='If true, incomplete external steps will be '
                                         'retested for completion while Trun is running.')
    send_failure_email = BoolParameter(default=True,
                                       description='If true, send e-mails directly from the worker'
                                                   'on failure')
    no_install_shutdown_handler = BoolParameter(default=False,
                                                description='If true, the SIGUSR1 shutdown handler will'
                                                'NOT be install on the worker')
    check_unfulfilled_deps = BoolParameter(default=True,
                                           description='If true, check for completeness of '
                                           'dependencies before running a step')
    check_complete_on_run = BoolParameter(default=False,
                                          description='If true, only mark steps as done after running if they are complete. '
                                          'Regardless of this setting, the worker will always check if external '
                                          'steps are complete before marking them as done.')
    force_multiprocessing = BoolParameter(default=False,
                                          description='If true, use multiprocessing also when '
                                          'running with 1 worker')
    step_process_context = OptionalParameter(default=None,
                                             description='If set to a fully qualified class name, the class will '
                                             'be instantiated with a StepProcess as its constructor parameter and '
                                             'applied as a context manager around its run() call, so this can be '
                                             'used for obtaining high level customizable monitoring or logging of '
                                             'each individual Step run.')
    cache_step_completion = BoolParameter(default=False,
                                          description='If true, cache the response of successful completion checks '
                                          'of steps assigned to a worker. This can especially speed up steps with '
                                          'dynamic dependencies but assumes that the completion status does not change '
                                          'after it was true the first time.')


class KeepAliveThread(threading.Thread):
    """
    Periodically tell the scheduler that the worker still lives.
    """

    def __init__(self, scheduler, worker_id, ping_interval, rpc_message_callback):
        super(KeepAliveThread, self).__init__()
        self._should_stop = threading.Event()
        self._scheduler = scheduler
        self._worker_id = worker_id
        self._ping_interval = ping_interval
        self._rpc_message_callback = rpc_message_callback

    def stop(self):
        self._should_stop.set()

    def run(self):
        while True:
            self._should_stop.wait(self._ping_interval)
            if self._should_stop.is_set():
                logger.info("Worker %s was stopped. Shutting down Keep-Alive thread" % self._worker_id)
                break
            with fork_lock:
                response = None
                try:
                    response = self._scheduler.ping(worker=self._worker_id)
                except BaseException:  # httplib.BadStatusLine:
                    logger.warning('Failed pinging scheduler')

                # handle rpc messages
                if response:
                    for message in response["rpc_messages"]:
                        self._rpc_message_callback(message)


def rpc_message_callback(fn):
    fn.is_rpc_message_callback = True
    return fn


class Worker:
    """
    Worker object communicates with a scheduler.

    Simple class that talks to a scheduler and:

    * tells the scheduler what it has to do + its dependencies
    * asks for stuff to do (pulls it in a loop and runs it)
    """

    def __init__(self, scheduler=None, worker_id=None, worker_processes=1, assistant=False, **kwargs):
        if scheduler is None:
            scheduler = Scheduler()

        self.worker_processes = int(worker_processes)
        self._worker_info = self._generate_worker_info()

        self._config = worker(**kwargs)

        worker_id = worker_id or self._config.id or self._generate_worker_id(self._worker_info)

        assert self._config.wait_interval >= _WAIT_INTERVAL_EPS, "[worker] wait_interval must be positive"
        assert self._config.wait_jitter >= 0.0, "[worker] wait_jitter must be equal or greater than zero"

        self._id = worker_id
        self._scheduler = scheduler
        self._assistant = assistant
        self._stop_requesting_work = False

        self.host = socket.gethostname()
        self._scheduled_steps = {}
        self._suspended_steps = {}
        self._batch_running_steps = {}
        self._batch_families_sent = set()

        self._first_step = None

        self.add_succeeded = True
        self.run_succeeded = True

        self.unfulfilled_counts = collections.defaultdict(int)

        # note that ``signal.signal(signal.SIGUSR1, fn)`` only works inside the main execution thread, which is why we
        # provide the ability to conditionally install the hook.
        if not self._config.no_install_shutdown_handler:
            try:
                signal.signal(signal.SIGUSR1, self.handle_interrupt)
                signal.siginterrupt(signal.SIGUSR1, False)
            except AttributeError:
                pass

        # Keep info about what steps are running (could be in other processes)
        self._step_result_queue = multiprocessing.Queue()
        self._running_steps = {}
        self._idle_since = None

        # mp-safe dictionary for caching completation checks across step processes
        self._step_completion_cache = None
        if self._config.cache_step_completion:
            self._step_completion_cache = multiprocessing.Manager().dict()

        # Stuff for execution_summary
        self._add_step_history = []
        self._get_work_response_history = []

    def _add_step(self, *args, **kwargs):
        """
        Call ``self._scheduler.add_step``, but store the values too so we can
        implement :py:func:`trun.execution_summary.summary`.
        """
        step_id = kwargs['step_id']
        status = kwargs['status']
        runnable = kwargs['runnable']
        step = self._scheduled_steps.get(step_id)
        if step:
            self._add_step_history.append((step, status, runnable))
            kwargs['owners'] = step._owner_list()

        if step_id in self._batch_running_steps:
            for batch_step in self._batch_running_steps.pop(step_id):
                self._add_step_history.append((batch_step, status, True))

        if step and kwargs.get('params'):
            kwargs['param_visibilities'] = step._get_param_visibilities()

        self._scheduler.add_step(*args, **kwargs)

        logger.info('Informed scheduler that step   %s   has status   %s', step_id, status)

    def __enter__(self):
        """
        Start the KeepAliveThread.
        """
        self._keep_alive_thread = KeepAliveThread(self._scheduler, self._id,
                                                  self._config.ping_interval,
                                                  self._handle_rpc_message)
        self._keep_alive_thread.daemon = True
        self._keep_alive_thread.start()
        return self

    def __exit__(self, type, value, traceback):
        """
        Stop the KeepAliveThread and kill still running steps.
        """
        self._keep_alive_thread.stop()
        self._keep_alive_thread.join()
        for step in self._running_steps.values():
            if step.is_alive():
                step.terminate()
        self._step_result_queue.close()
        return False  # Don't suppress exception

    def _generate_worker_info(self):
        # Generate as much info as possible about the worker
        # Some of these calls might not be available on all OS's
        args = [('salt', '%09d' % random.randrange(0, 10_000_000_000)),
                ('workers', self.worker_processes)]
        try:
            args += [('host', socket.gethostname())]
        except BaseException:
            pass
        try:
            args += [('username', getpass.getuser())]
        except BaseException:
            pass
        try:
            args += [('pid', os.getpid())]
        except BaseException:
            pass
        try:
            sudo_user = os.getenv("SUDO_USER")
            if sudo_user:
                args.append(('sudo_user', sudo_user))
        except BaseException:
            pass
        return args

    def _generate_worker_id(self, worker_info):
        worker_info_str = ', '.join(['{}={}'.format(k, v) for k, v in worker_info])
        return 'Worker({})'.format(worker_info_str)

    def _validate_step(self, step):
        if not isinstance(step, Step):
            raise StepException('Can not schedule non-step %s' % step)

        if not step.initialized():
            # we can't get the repr of it since it's not initialized...
            raise StepException('Step of class %s not initialized. Did you override __init__ and forget to call super(...).__init__?' % step.__class__.__name__)

    def _log_complete_error(self, step, tb):
        log_msg = "Will not run {step} or any dependencies due to error in complete() method:\n{tb}".format(step=step, tb=tb)
        logger.warning(log_msg)

    def _log_dependency_error(self, step, tb):
        log_msg = "Will not run {step} or any dependencies due to error in deps() method:\n{tb}".format(step=step, tb=tb)
        logger.warning(log_msg)

    def _log_unexpected_error(self, step):
        logger.exception("Trun unexpected framework error while scheduling %s", step)  # needs to be called from within except clause

    def _announce_scheduling_failure(self, step, expl):
        try:
            self._scheduler.announce_scheduling_failure(
                worker=self._id,
                step_name=str(step),
                family=step.step_family,
                params=step.to_str_params(only_significant=True),
                expl=expl,
                owners=step._owner_list(),
            )
        except Exception:
            formatted_traceback = traceback.format_exc()
            self._email_unexpected_error(step, formatted_traceback)
            raise

    def _email_complete_error(self, step, formatted_traceback):
        self._announce_scheduling_failure(step, formatted_traceback)
        if self._config.send_failure_email:
            self._email_error(step, formatted_traceback,
                              subject="Trun: {step} failed scheduling. Host: {host}",
                              headline="Will not run {step} or any dependencies due to error in complete() method",
                              )

    def _email_dependency_error(self, step, formatted_traceback):
        self._announce_scheduling_failure(step, formatted_traceback)
        if self._config.send_failure_email:
            self._email_error(step, formatted_traceback,
                              subject="Trun: {step} failed scheduling. Host: {host}",
                              headline="Will not run {step} or any dependencies due to error in deps() method",
                              )

    def _email_unexpected_error(self, step, formatted_traceback):
        # this sends even if failure e-mails are disabled, as they may indicate
        # a more severe failure that may not reach other alerting methods such
        # as scheduler batch notification
        self._email_error(step, formatted_traceback,
                          subject="Trun: Framework error while scheduling {step}. Host: {host}",
                          headline="Trun framework error",
                          )

    def _email_step_failure(self, step, formatted_traceback):
        if self._config.send_failure_email:
            self._email_error(step, formatted_traceback,
                              subject="Trun: {step} FAILED. Host: {host}",
                              headline="A step failed when running. Most likely run() raised an exception.",
                              )

    def _email_error(self, step, formatted_traceback, subject, headline):
        formatted_subject = subject.format(step=step, host=self.host)
        formatted_headline = headline.format(step=step, host=self.host)
        command = subprocess.list2cmdline(sys.argv)
        message = notifications.format_step_error(
            formatted_headline, step, command, formatted_traceback)
        notifications.send_error_email(formatted_subject, message, step.owner_email)

    def _handle_step_load_error(self, exception, step_ids):
        msg = 'Cannot find step(s) sent by scheduler: {}'.format(','.join(step_ids))
        logger.exception(msg)
        subject = 'Trun: {}'.format(msg)
        error_message = notifications.wrap_traceback(exception)
        for step_id in step_ids:
            self._add_step(
                worker=self._id,
                step_id=step_id,
                status=FAILED,
                runnable=False,
                expl=error_message,
            )
        notifications.send_error_email(subject, error_message)

    def add(self, step, multiprocess=False, processes=0):
        """
        Add a Step for the worker to check and possibly schedule and run.

        Returns True if step and its dependencies were successfully scheduled or completed before.
        """
        if self._first_step is None and hasattr(step, 'step_id'):
            self._first_step = step.step_id
        self.add_succeeded = True
        if multiprocess:
            queue = multiprocessing.Manager().Queue()
            pool = multiprocessing.Pool(processes=processes if processes > 0 else None)
        else:
            queue = DequeQueue()
            pool = SingleProcessPool()
        self._validate_step(step)
        pool.apply_async(check_complete, [step, queue, self._step_completion_cache])

        # we track queue size ourselves because len(queue) won't work for multiprocessing
        queue_size = 1
        try:
            seen = {step.step_id}
            while queue_size:
                current = queue.get()
                queue_size -= 1
                item, is_complete = current
                for next in self._add(item, is_complete):
                    if next.step_id not in seen:
                        self._validate_step(next)
                        seen.add(next.step_id)
                        pool.apply_async(check_complete, [next, queue, self._step_completion_cache])
                        queue_size += 1
        except (KeyboardInterrupt, StepException):
            raise
        except Exception as ex:
            self.add_succeeded = False
            formatted_traceback = traceback.format_exc()
            self._log_unexpected_error(step)
            step.trigger_event(Event.BROKEN_STEP, step, ex)
            self._email_unexpected_error(step, formatted_traceback)
            raise
        finally:
            pool.close()
            pool.join()
        return self.add_succeeded

    def _add_step_batcher(self, step):
        family = step.step_family
        if family not in self._batch_families_sent:
            step_class = type(step)
            batch_param_names = step_class.batch_param_names()
            if batch_param_names:
                self._scheduler.add_step_batcher(
                    worker=self._id,
                    step_family=family,
                    batched_args=batch_param_names,
                    max_batch_size=step.max_batch_size,
                )
            self._batch_families_sent.add(family)

    def _add(self, step, is_complete):
        if self._config.step_limit is not None and len(self._scheduled_steps) >= self._config.step_limit:
            logger.warning('Will not run %s or any dependencies due to exceeded step-limit of %d', step, self._config.step_limit)
            deps = None
            status = UNKNOWN
            runnable = False

        else:
            formatted_traceback = None
            try:
                self._check_complete_value(is_complete)
            except KeyboardInterrupt:
                raise
            except AsyncCompletionException as ex:
                formatted_traceback = ex.trace
            except BaseException:
                formatted_traceback = traceback.format_exc()

            if formatted_traceback is not None:
                self.add_succeeded = False
                self._log_complete_error(step, formatted_traceback)
                step.trigger_event(Event.DEPENDENCY_MISSING, step)
                self._email_complete_error(step, formatted_traceback)
                deps = None
                status = UNKNOWN
                runnable = False

            elif is_complete:
                deps = None
                status = DONE
                runnable = False
                step.trigger_event(Event.DEPENDENCY_PRESENT, step)

            elif _is_external(step):
                deps = None
                status = PENDING
                runnable = self._config.retry_external_steps
                step.trigger_event(Event.DEPENDENCY_MISSING, step)
                logger.warning('Data for %s does not exist (yet?). The step is an '
                               'external data dependency, so it cannot be run from'
                               ' this trun process.', step)

            else:
                try:
                    deps = step.deps()
                    self._add_step_batcher(step)
                except Exception as ex:
                    formatted_traceback = traceback.format_exc()
                    self.add_succeeded = False
                    self._log_dependency_error(step, formatted_traceback)
                    step.trigger_event(Event.BROKEN_STEP, step, ex)
                    self._email_dependency_error(step, formatted_traceback)
                    deps = None
                    status = UNKNOWN
                    runnable = False
                else:
                    status = PENDING
                    runnable = True

            if step.disabled:
                status = DISABLED

            if deps:
                for d in deps:
                    self._validate_dependency(d)
                    step.trigger_event(Event.DEPENDENCY_DISCOVERED, step, d)
                    yield d  # return additional steps to add

                deps = [d.step_id for d in deps]

        self._scheduled_steps[step.step_id] = step
        self._add_step(
            worker=self._id,
            step_id=step.step_id,
            status=status,
            deps=deps,
            runnable=runnable,
            priority=step.priority,
            resources=step.process_resources(),
            params=step.to_str_params(),
            family=step.step_family,
            module=step.step_module,
            batchable=step.batchable,
            retry_policy_dict=_get_retry_policy_dict(step),
            accepts_messages=step.accepts_messages,
        )

    def _validate_dependency(self, dependency):
        if isinstance(dependency, Target):
            raise Exception('requires() can not return Target objects. Wrap it in an ExternalStep class')
        elif not isinstance(dependency, Step):
            raise Exception('requires() must return Step objects but {} is a {}'.format(dependency, type(dependency)))

    def _check_complete_value(self, is_complete):
        if is_complete not in (True, False):
            if isinstance(is_complete, TracebackWrapper):
                raise AsyncCompletionException(is_complete.trace)
            raise Exception("Return value of Step.complete() must be boolean (was %r)" % is_complete)

    def _add_worker(self):
        self._worker_info.append(('first_step', self._first_step))
        self._scheduler.add_worker(self._id, self._worker_info)

    def _log_remote_steps(self, get_work_response):
        logger.debug("Done")
        logger.debug("There are no more steps to run at this time")
        if get_work_response.running_steps:
            for r in get_work_response.running_steps:
                logger.debug('%s is currently run by worker %s', r['step_id'], r['worker'])
        elif get_work_response.n_pending_steps:
            logger.debug(
                "There are %s pending steps possibly being run by other workers",
                get_work_response.n_pending_steps)
            if get_work_response.n_unique_pending:
                logger.debug(
                    "There are %i pending steps unique to this worker",
                    get_work_response.n_unique_pending)
            if get_work_response.n_pending_last_scheduled:
                logger.debug(
                    "There are %i pending steps last scheduled by this worker",
                    get_work_response.n_pending_last_scheduled)

    def _get_work_step_id(self, get_work_response):
        if get_work_response.get('step_id') is not None:
            return get_work_response['step_id']
        elif 'batch_id' in get_work_response:
            try:
                step = load_step(
                    module=get_work_response.get('step_module'),
                    step_name=get_work_response['step_family'],
                    params_str=get_work_response['step_params'],
                )
            except Exception as ex:
                self._handle_step_load_error(ex, get_work_response['batch_step_ids'])
                self.run_succeeded = False
                return None

            self._scheduler.add_step(
                worker=self._id,
                step_id=step.step_id,
                module=get_work_response.get('step_module'),
                family=get_work_response['step_family'],
                params=step.to_str_params(),
                status=RUNNING,
                batch_id=get_work_response['batch_id'],
            )
            return step.step_id
        else:
            return None

    def _get_work(self):
        if self._stop_requesting_work:
            return GetWorkResponse(None, 0, 0, 0, 0, WORKER_STATE_DISABLED)

        if self.worker_processes > 0:
            logger.debug("Asking scheduler for work...")
            r = self._scheduler.get_work(
                worker=self._id,
                host=self.host,
                assistant=self._assistant,
                current_steps=list(self._running_steps.keys()),
            )
        else:
            logger.debug("Checking if steps are still pending")
            r = self._scheduler.count_pending(worker=self._id)

        running_steps = r['running_steps']
        step_id = self._get_work_step_id(r)

        self._get_work_response_history.append({
            'step_id': step_id,
            'running_steps': running_steps,
        })

        if step_id is not None and step_id not in self._scheduled_steps:
            logger.info('Did not schedule %s, will load it dynamically', step_id)

            try:
                # TODO: we should obtain the module name from the server!
                self._scheduled_steps[step_id] = \
                    load_step(module=r.get('step_module'),
                              step_name=r['step_family'],
                              params_str=r['step_params'])
            except StepClassException as ex:
                self._handle_step_load_error(ex, [step_id])
                step_id = None
                self.run_succeeded = False

        if step_id is not None and 'batch_step_ids' in r:
            batch_steps = filter(None, [
                self._scheduled_steps.get(batch_id) for batch_id in r['batch_step_ids']])
            self._batch_running_steps[step_id] = batch_steps

        return GetWorkResponse(
            step_id=step_id,
            running_steps=running_steps,
            n_pending_steps=r['n_pending_steps'],
            n_unique_pending=r['n_unique_pending'],

            # TODO: For a tiny amount of time (a month?) we'll keep forwards compatibility
            #  That is you can user a newer client than server (Sep 2016)
            n_pending_last_scheduled=r.get('n_pending_last_scheduled', 0),
            worker_state=r.get('worker_state', WORKER_STATE_ACTIVE),
        )

    def _run_step(self, step_id):
        if step_id in self._running_steps:
            logger.debug('Got already running step id {} from scheduler, taking a break'.format(step_id))
            next(self._sleeper())
            return

        step = self._scheduled_steps[step_id]

        step_process = self._create_step_process(step)

        self._running_steps[step_id] = step_process

        if step_process.use_multiprocessing:
            with fork_lock:
                step_process.start()
        else:
            # Run in the same process
            step_process.run()

    def _create_step_process(self, step):
        message_queue = multiprocessing.Queue() if step.accepts_messages else None
        reporter = StepStatusReporter(self._scheduler, step.step_id, self._id, message_queue)
        use_multiprocessing = self._config.force_multiprocessing or bool(self.worker_processes > 1)
        return ContextManagedStepProcess(
            self._config.step_process_context,
            step, self._id, self._step_result_queue, reporter,
            use_multiprocessing=use_multiprocessing,
            worker_timeout=self._config.timeout,
            check_unfulfilled_deps=self._config.check_unfulfilled_deps,
            check_complete_on_run=self._config.check_complete_on_run,
            step_completion_cache=self._step_completion_cache,
        )

    def _purge_children(self):
        """
        Find dead children and put a response on the result queue.

        :return:
        """
        for step_id, p in self._running_steps.items():
            if not p.is_alive() and p.exitcode:
                error_msg = 'Step {} died unexpectedly with exit code {}'.format(step_id, p.exitcode)
                p.step.trigger_event(Event.PROCESS_FAILURE, p.step, error_msg)
            elif p.timeout_time is not None and time.time() > float(p.timeout_time) and p.is_alive():
                p.terminate()
                error_msg = 'Step {} timed out after {} seconds and was terminated.'.format(step_id, p.worker_timeout)
                p.step.trigger_event(Event.TIMEOUT, p.step, error_msg)
            else:
                continue

            logger.info(error_msg)
            self._step_result_queue.put((step_id, FAILED, error_msg, [], []))

    def _handle_next_step(self):
        """
        We have to catch three ways a step can be "done":

        1. normal execution: the step runs/fails and puts a result back on the queue,
        2. new dependencies: the step yielded new deps that were not complete and
           will be rescheduled and dependencies added,
        3. child process dies: we need to catch this separately.
        """
        self._idle_since = None
        while True:
            self._purge_children()  # Deal with subprocess failures

            try:
                step_id, status, expl, missing, new_requirements = (
                    self._step_result_queue.get(
                        timeout=self._config.wait_interval))
            except Queue.Empty:
                return

            step = self._scheduled_steps[step_id]
            if not step or step_id not in self._running_steps:
                continue
                # Not a running step. Probably already removed.
                # Maybe it yielded something?

            # external step if run not implemented, retry-able if config option is enabled.
            external_step_retryable = _is_external(step) and self._config.retry_external_steps
            if status == FAILED and not external_step_retryable:
                self._email_step_failure(step, expl)

            new_deps = []
            if new_requirements:
                new_req = [load_step(module, name, params)
                           for module, name, params in new_requirements]
                for t in new_req:
                    self.add(t)
                new_deps = [t.step_id for t in new_req]

            self._add_step(worker=self._id,
                           step_id=step_id,
                           status=status,
                           expl=json.dumps(expl),
                           resources=step.process_resources(),
                           runnable=None,
                           params=step.to_str_params(),
                           family=step.step_family,
                           module=step.step_module,
                           new_deps=new_deps,
                           assistant=self._assistant,
                           retry_policy_dict=_get_retry_policy_dict(step))

            self._running_steps.pop(step_id)

            # re-add step to reschedule missing dependencies
            if missing:
                reschedule = True

                # keep out of infinite loops by not rescheduling too many times
                for step_id in missing:
                    self.unfulfilled_counts[step_id] += 1
                    if (self.unfulfilled_counts[step_id] >
                            self._config.max_reschedules):
                        reschedule = False
                if reschedule:
                    self.add(step)

            self.run_succeeded &= (status == DONE) or (len(new_deps) > 0)
            return

    def _sleeper(self):
        # TODO is exponential backoff necessary?
        while True:
            jitter = self._config.wait_jitter
            wait_interval = self._config.wait_interval + random.uniform(0, jitter)
            logger.debug('Sleeping for %f seconds', wait_interval)
            time.sleep(wait_interval)
            yield

    def _keep_alive(self, get_work_response):
        """
        Returns true if a worker should stay alive given.

        If worker-keep-alive is not set, this will always return false.
        For an assistant, it will always return the value of worker-keep-alive.
        Otherwise, it will return true for nonzero n_pending_steps.

        If worker-count-uniques is true, it will also
        require that one of the steps is unique to this worker.
        """
        if not self._config.keep_alive:
            return False
        elif self._assistant:
            return True
        elif self._config.count_last_scheduled:
            return get_work_response.n_pending_last_scheduled > 0
        elif self._config.count_uniques:
            return get_work_response.n_unique_pending > 0
        elif get_work_response.n_pending_steps == 0:
            return False
        elif not self._config.max_keep_alive_idle_duration:
            return True
        elif not self._idle_since:
            return True
        else:
            time_to_shutdown = self._idle_since + self._config.max_keep_alive_idle_duration - datetime.datetime.now()
            logger.debug("[%s] %s until shutdown", self._id, time_to_shutdown)
            return time_to_shutdown > datetime.timedelta(0)

    def handle_interrupt(self, signum, _):
        """
        Stops the assistant from asking for more work on SIGUSR1
        """
        if signum == signal.SIGUSR1:
            self._start_phasing_out()

    def _start_phasing_out(self):
        """
        Go into a mode where we dont ask for more work and quit once existing
        steps are done.
        """
        self._config.keep_alive = False
        self._stop_requesting_work = True

    def run(self):
        """
        Returns True if all scheduled steps were executed successfully.
        """
        logger.info('Running Worker with %d processes', self.worker_processes)

        sleeper = self._sleeper()
        self.run_succeeded = True

        self._add_worker()

        while True:
            while len(self._running_steps) >= self.worker_processes > 0:
                logger.debug('%d running steps, waiting for next step to finish', len(self._running_steps))
                self._handle_next_step()

            get_work_response = self._get_work()

            if get_work_response.worker_state == WORKER_STATE_DISABLED:
                self._start_phasing_out()

            if get_work_response.step_id is None:
                if not self._stop_requesting_work:
                    self._log_remote_steps(get_work_response)
                if len(self._running_steps) == 0:
                    self._idle_since = self._idle_since or datetime.datetime.now()
                    if self._keep_alive(get_work_response):
                        next(sleeper)
                        continue
                    else:
                        break
                else:
                    self._handle_next_step()
                    continue

            # step_id is not None:
            logger.debug("Pending steps: %s", get_work_response.n_pending_steps)
            self._run_step(get_work_response.step_id)

        while len(self._running_steps):
            logger.debug('Shut down Worker, %d more steps to go', len(self._running_steps))
            self._handle_next_step()

        return self.run_succeeded

    def _handle_rpc_message(self, message):
        logger.info("Worker %s got message %s" % (self._id, message))

        # the message is a dict {'name': <function_name>, 'kwargs': <function_kwargs>}
        name = message['name']
        kwargs = message['kwargs']

        # find the function and check if it's callable and configured to work
        # as a message callback
        func = getattr(self, name, None)
        tpl = (self._id, name)
        if not callable(func):
            logger.error("Worker %s has no function '%s'" % tpl)
        elif not getattr(func, "is_rpc_message_callback", False):
            logger.error("Worker %s function '%s' is not available as rpc message callback" % tpl)
        else:
            logger.info("Worker %s successfully dispatched rpc message to function '%s'" % tpl)
            func(**kwargs)

    @rpc_message_callback
    def set_worker_processes(self, n):
        # set the new value
        self.worker_processes = max(1, n)

        # tell the scheduler
        self._scheduler.add_worker(self._id, {'workers': self.worker_processes})

    @rpc_message_callback
    def dispatch_scheduler_message(self, step_id, message_id, content, **kwargs):
        step_id = str(step_id)
        if step_id in self._running_steps:
            step_process = self._running_steps[step_id]
            if step_process.status_reporter.scheduler_messages:
                message = SchedulerMessage(self._scheduler, step_id, message_id, content, **kwargs)
                step_process.status_reporter.scheduler_messages.put(message)
