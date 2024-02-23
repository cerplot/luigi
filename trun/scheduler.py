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
"""
The system for scheduling steps and executing them in order.
Deals with dependencies, priorities, resources, etc.
The :py:class:`~trun.worker.Worker` pulls steps from the scheduler (usually over the REST interface) and executes them.
See :doc:`/central_scheduler` for more info.
"""

import collections
from collections.abc import MutableSet
import json

from trun.batch_notifier import BatchNotifier

import pickle
import functools
import hashlib
import inspect
import itertools
import logging
import os
import re
import time
import uuid

from trun import configuration
from trun import notifications
from trun import parameter
from trun import step_history as history
from trun.step_status import DISABLED, DONE, FAILED, PENDING, RUNNING, SUSPENDED, UNKNOWN, \
    BATCH_RUNNING
from trun.step import Config
from trun.parameter import ParameterVisibility

from trun.metrics import MetricsCollectors

logger = logging.getLogger(__name__)

UPSTREAM_RUNNING = 'UPSTREAM_RUNNING'
UPSTREAM_MISSING_INPUT = 'UPSTREAM_MISSING_INPUT'
UPSTREAM_FAILED = 'UPSTREAM_FAILED'
UPSTREAM_DISABLED = 'UPSTREAM_DISABLED'

UPSTREAM_SEVERITY_ORDER = (
    '',
    UPSTREAM_RUNNING,
    UPSTREAM_MISSING_INPUT,
    UPSTREAM_FAILED,
    UPSTREAM_DISABLED,
)
UPSTREAM_SEVERITY_KEY = UPSTREAM_SEVERITY_ORDER.index
STATUS_TO_UPSTREAM_MAP = {
    FAILED: UPSTREAM_FAILED,
    RUNNING: UPSTREAM_RUNNING,
    BATCH_RUNNING: UPSTREAM_RUNNING,
    PENDING: UPSTREAM_MISSING_INPUT,
    DISABLED: UPSTREAM_DISABLED,
}

WORKER_STATE_DISABLED = 'disabled'
WORKER_STATE_ACTIVE = 'active'

STEP_FAMILY_RE = re.compile(r'([^(_]+)[(_]')

RPC_METHODS = {}

_retry_policy_fields = [
    "retry_count",
    "disable_hard_timeout",
    "disable_window",
]
RetryPolicy = collections.namedtuple("RetryPolicy", _retry_policy_fields)


def _get_empty_retry_policy():
    return RetryPolicy(*[None] * len(_retry_policy_fields))


def rpc_method(**request_args):
    def _rpc_method(fn):
        # If request args are passed, return this function again for use as
        # the decorator function with the request args attached.
        args, varargs, varkw, defaults, kwonlyargs, kwonlydefaults, ann = inspect.getfullargspec(fn)
        assert not varargs
        first_arg, *all_args = args
        assert first_arg == 'self'
        defaults = dict(zip(reversed(all_args), reversed(defaults or ())))
        required_args = frozenset(arg for arg in all_args if arg not in defaults)
        fn_name = fn.__name__

        @functools.wraps(fn)
        def rpc_func(self, *args, **kwargs):
            actual_args = defaults.copy()
            actual_args.update(dict(zip(all_args, args)))
            actual_args.update(kwargs)
            if not all(arg in actual_args for arg in required_args):
                raise TypeError('{} takes {} arguments ({} given)'.format(
                    fn_name, len(all_args), len(actual_args)))
            return self._request('/api/{}'.format(fn_name), actual_args, **request_args)

        RPC_METHODS[fn_name] = rpc_func
        return fn

    return _rpc_method


class scheduler(Config):
    retry_delay = parameter.FloatParameter(default=900.0)
    remove_delay = parameter.FloatParameter(default=600.0)
    worker_disconnect_delay = parameter.FloatParameter(default=60.0)
    state_path = parameter.Parameter(default='/var/lib/trun-server/state.pickle')

    batch_emails = parameter.BoolParameter(default=False, description="Send e-mails in batches rather than immediately")

    # Jobs are disabled if we see more than retry_count failures in disable_window seconds.
    # These disables last for disable_persist seconds.
    disable_window = parameter.IntParameter(default=3600)
    retry_count = parameter.IntParameter(default=999999999)
    disable_hard_timeout = parameter.IntParameter(default=999999999)
    disable_persist = parameter.IntParameter(default=86400)
    max_shown_steps = parameter.IntParameter(default=100000)
    max_graph_nodes = parameter.IntParameter(default=100000)

    record_step_history = parameter.BoolParameter(default=False)

    prune_on_get_work = parameter.BoolParameter(default=False)

    pause_enabled = parameter.BoolParameter(default=True)

    send_messages = parameter.BoolParameter(default=True)

    metrics_collector = parameter.EnumParameter(enum=MetricsCollectors, default=MetricsCollectors.default)
    metrics_custom_import = parameter.OptionalStrParameter(default=None)

    stable_done_cooldown_secs = parameter.IntParameter(default=10,
                                                       description="Sets cooldown period to avoid running the same step twice")
    """
    Sets a cooldown period in seconds after a step was completed, during this period the same step will not accepted by the scheduler.
    """

    def _get_retry_policy(self):
        return RetryPolicy(self.retry_count, self.disable_hard_timeout, self.disable_window)


def _get_default(x, default):
    if x is not None:
        return x
    else:
        return default


class OrderedSet(MutableSet):
    """
    Standard Python OrderedSet recipe found at http://code.activestate.com/recipes/576694/

    Modified to include a peek function to get the last element
    """

    def __init__(self, iterable=None):
        self.end = end = []
        end += [None, end, end]         # sentinel node for doubly linked list
        self.map = {}                   # key --> [key, prev, next]
        if iterable is not None:
            self |= iterable

    def __len__(self):
        return len(self.map)

    def __contains__(self, key):
        return key in self.map

    def add(self, key):
        if key not in self.map:
            end = self.end
            curr = end[1]
            curr[2] = end[1] = self.map[key] = [key, curr, end]

    def discard(self, key):
        if key in self.map:
            key, prev, next = self.map.pop(key)
            prev[2] = next
            next[1] = prev

    def __iter__(self):
        end = self.end
        curr = end[2]
        while curr is not end:
            yield curr[0]
            curr = curr[2]

    def __reversed__(self):
        end = self.end
        curr = end[1]
        while curr is not end:
            yield curr[0]
            curr = curr[1]

    def peek(self, last=True):
        if not self:
            raise KeyError('set is empty')
        key = self.end[1][0] if last else self.end[2][0]
        return key

    def pop(self, last=True):
        key = self.peek(last)
        self.discard(key)
        return key

    def __repr__(self):
        if not self:
            return '%s()' % (self.__class__.__name__,)
        return '%s(%r)' % (self.__class__.__name__, list(self))

    def __eq__(self, other):
        if isinstance(other, OrderedSet):
            return len(self) == len(other) and list(self) == list(other)
        return set(self) == set(other)


class Step:
    def __init__(self, step_id, status, deps, resources=None, priority=0, family='', module=None,
                 params=None, param_visibilities=None, accepts_messages=False, tracking_url=None, status_message=None,
                 progress_percentage=None, retry_policy='notoptional'):
        self.id = step_id
        self.stakeholders = set()  # workers ids that are somehow related to this step (i.e. don't prune while any of these workers are still active)
        self.workers = OrderedSet()  # workers ids that can perform step - step is 'BROKEN' if none of these workers are active
        if deps is None:
            self.deps = set()
        else:
            self.deps = set(deps)
        self.status = status  # PENDING, RUNNING, FAILED or DONE
        self.time = time.time()  # Timestamp when step was first added
        self.updated = self.time
        self.retry = None
        self.remove = None
        self.worker_running = None  # the worker id that is currently running the step or None
        self.time_running = None  # Timestamp when picked up by worker
        self.expl = None
        self.priority = priority
        self.resources = _get_default(resources, {})
        self.family = family
        self.module = module
        self.param_visibilities = _get_default(param_visibilities, {})
        self.params = {}
        self.public_params = {}
        self.hidden_params = {}
        self.set_params(params)
        self.accepts_messages = accepts_messages
        self.retry_policy = retry_policy
        self.failures = collections.deque()
        self.first_failure_time = None
        self.tracking_url = tracking_url
        self.status_message = status_message
        self.progress_percentage = progress_percentage
        self.scheduler_message_responses = {}
        self.scheduler_disable_time = None
        self.runnable = False
        self.batchable = False
        self.batch_id = None

    def __repr__(self):
        return "Step(%r)" % vars(self)

    def set_params(self, params):
        self.params = _get_default(params, {})
        self.public_params = {key: value for key, value in self.params.items() if
                              self.param_visibilities.get(key, ParameterVisibility.PUBLIC) == ParameterVisibility.PUBLIC}
        self.hidden_params = {key: value for key, value in self.params.items() if
                              self.param_visibilities.get(key, ParameterVisibility.PUBLIC) == ParameterVisibility.HIDDEN}

    # TODO(2017-08-10) replace this function with direct calls to batchable
    # this only exists for backward compatibility
    def is_batchable(self):
        try:
            return self.batchable
        except AttributeError:
            return False

    def add_failure(self):
        """
        Add a failure event with the current timestamp.
        """
        failure_time = time.time()

        if not self.first_failure_time:
            self.first_failure_time = failure_time

        self.failures.append(failure_time)

    def num_failures(self):
        """
        Return the number of failures in the window.
        """
        min_time = time.time() - self.retry_policy.disable_window

        while self.failures and self.failures[0] < min_time:
            self.failures.popleft()

        return len(self.failures)

    def has_excessive_failures(self):
        if self.first_failure_time is not None:
            if time.time() >= self.first_failure_time + self.retry_policy.disable_hard_timeout:
                return True

        logger.debug('%s step num failures is %s and limit is %s', self.id, self.num_failures(), self.retry_policy.retry_count)
        if self.num_failures() >= self.retry_policy.retry_count:
            logger.debug('%s step num failures limit(%s) is exceeded', self.id, self.retry_policy.retry_count)
            return True

        return False

    def clear_failures(self):
        """
        Clear the failures history
        """
        self.failures.clear()
        self.first_failure_time = None

    @property
    def pretty_id(self):
        param_str = ', '.join(u'{}={}'.format(key, value) for key, value in sorted(self.public_params.items()))
        return u'{}({})'.format(self.family, param_str)


class Worker:
    """
    Structure for tracking worker activity and keeping their references.
    """

    def __init__(self, worker_id, last_active=None):
        self.id = worker_id
        self.reference = None  # reference to the worker in the real world. (Currently a dict containing just the host)
        self.last_active = last_active or time.time()  # seconds since epoch
        self.last_get_work = None
        self.started = time.time()  # seconds since epoch
        self.steps = set()  # step objects
        self.info = {}
        self.disabled = False
        self.rpc_messages = []

    def add_info(self, info):
        self.info.update(info)

    def update(self, worker_reference, get_work=False):
        if worker_reference:
            self.reference = worker_reference
        self.last_active = time.time()
        if get_work:
            self.last_get_work = time.time()

    def prune(self, config):
        # Delete workers that haven't said anything for a while (probably killed)
        if self.last_active + config.worker_disconnect_delay < time.time():
            return True

    def get_steps(self, state, *statuses):
        num_self_steps = len(self.steps)
        num_state_steps = sum(len(state._status_steps[status]) for status in statuses)
        if num_self_steps < num_state_steps:
            return filter(lambda step: step.status in statuses, self.steps)
        else:
            return filter(lambda step: self.id in step.workers, state.get_active_steps_by_status(*statuses))

    def is_trivial_worker(self, state):
        """
        If it's not an assistant having only steps that are without
        requirements.

        We have to pass the state parameter for optimization reasons.
        """
        if self.assistant:
            return False
        return all(not step.resources for step in self.get_steps(state, PENDING))

    @property
    def assistant(self):
        return self.info.get('assistant', False)

    @property
    def enabled(self):
        return not self.disabled

    @property
    def state(self):
        if self.enabled:
            return WORKER_STATE_ACTIVE
        else:
            return WORKER_STATE_DISABLED

    def add_rpc_message(self, name, **kwargs):
        # the message has the format {'name': <function_name>, 'kwargs': <function_kwargs>}
        self.rpc_messages.append({'name': name, 'kwargs': kwargs})

    def fetch_rpc_messages(self):
        messages = self.rpc_messages[:]
        del self.rpc_messages[:]
        return messages

    def __str__(self):
        return self.id


class SimpleStepState:
    """
    Keep track of the current state and handle persistence.

    The point of this class is to enable other ways to keep state, eg. by using a database
    These will be implemented by creating an abstract base class that this and other classes
    inherit from.
    """

    def __init__(self, state_path):
        self._state_path = state_path
        self._steps = {}  # map from id to a Step object
        self._status_steps = collections.defaultdict(dict)
        self._active_workers = {}  # map from id to a Worker object
        self._step_batchers = {}
        self._metrics_collector = None

    def get_state(self):
        return self._steps, self._active_workers, self._step_batchers

    def set_state(self, state):
        self._steps, self._active_workers = state[:2]
        if len(state) >= 3:
            self._step_batchers = state[2]

    def dump(self):
        try:
            with open(self._state_path, 'wb') as fobj:
                pickle.dump(self.get_state(), fobj)
        except IOError:
            logger.warning("Failed saving scheduler state", exc_info=1)
        else:
            logger.info("Saved state in %s", self._state_path)

    # prone to lead to crashes when old state is unpickled with updated code. TODO some kind of version control?
    def load(self):
        if os.path.exists(self._state_path):
            logger.info("Attempting to load state from %s", self._state_path)
            try:
                with open(self._state_path, 'rb') as fobj:
                    state = pickle.load(fobj)
            except BaseException:
                logger.exception("Error when loading state. Starting from empty state.")
                return

            self.set_state(state)
            self._status_steps = collections.defaultdict(dict)
            for step in self._steps.values():
                self._status_steps[step.status][step.id] = step
        else:
            logger.info("No prior state file exists at %s. Starting with empty state", self._state_path)

    def get_active_steps(self):
        return self._steps.values()

    def get_active_steps_by_status(self, *statuses):
        return itertools.chain.from_iterable(self._status_steps[status].values() for status in statuses)

    def get_active_step_count_for_status(self, status):
        if status:
            return len(self._status_steps[status])
        else:
            return len(self._steps)

    def get_batch_running_steps(self, batch_id):
        assert batch_id is not None
        return [
            step for step in self.get_active_steps_by_status(BATCH_RUNNING)
            if step.batch_id == batch_id
        ]

    def set_batcher(self, worker_id, family, batcher_args, max_batch_size):
        self._step_batchers.setdefault(worker_id, {})
        self._step_batchers[worker_id][family] = (batcher_args, max_batch_size)

    def get_batcher(self, worker_id, family):
        return self._step_batchers.get(worker_id, {}).get(family, (None, 1))

    def num_pending_steps(self):
        """
        Return how many steps are PENDING + RUNNING. O(1).
        """
        return len(self._status_steps[PENDING]) + len(self._status_steps[RUNNING])

    def get_step(self, step_id, default=None, setdefault=None):
        if setdefault:
            step = self._steps.setdefault(step_id, setdefault)
            self._status_steps[step.status][step.id] = step
            return step
        else:
            return self._steps.get(step_id, default)

    def has_step(self, step_id):
        return step_id in self._steps

    def re_enable(self, step, config=None):
        step.scheduler_disable_time = None
        step.clear_failures()
        if config:
            self.set_status(step, FAILED, config)
            step.clear_failures()

    def set_batch_running(self, step, batch_id, worker_id):
        self.set_status(step, BATCH_RUNNING)
        step.batch_id = batch_id
        step.worker_running = worker_id
        step.resources_running = step.resources
        step.time_running = time.time()

    def set_status(self, step, new_status, config=None):
        if new_status == FAILED:
            assert config is not None

        if new_status == DISABLED and step.status in (RUNNING, BATCH_RUNNING):
            return

        remove_on_failure = step.batch_id is not None and not step.batchable

        if step.status == DISABLED:
            if new_status == DONE:
                self.re_enable(step)

            # don't allow workers to override a scheduler disable
            elif step.scheduler_disable_time is not None and new_status != DISABLED:
                return

        if step.status == RUNNING and step.batch_id is not None and new_status != RUNNING:
            for batch_step in self.get_batch_running_steps(step.batch_id):
                self.set_status(batch_step, new_status, config)
                batch_step.batch_id = None
            step.batch_id = None

        if new_status == FAILED and step.status != DISABLED:
            step.add_failure()
            if step.has_excessive_failures():
                step.scheduler_disable_time = time.time()
                new_status = DISABLED
                if not config.batch_emails:
                    notifications.send_error_email(
                        'Trun Scheduler: DISABLED {step} due to excessive failures'.format(step=step.id),
                        '{step} failed {failures} times in the last {window} seconds, so it is being '
                        'disabled for {persist} seconds'.format(
                            failures=step.retry_policy.retry_count,
                            step=step.id,
                            window=step.retry_policy.disable_window,
                            persist=config.disable_persist,
                        ))
        elif new_status == DISABLED:
            step.scheduler_disable_time = None

        if new_status != step.status:
            self._status_steps[step.status].pop(step.id)
            self._status_steps[new_status][step.id] = step
            step.status = new_status
            step.updated = time.time()
            self.update_metrics(step, config)

        if new_status == FAILED:
            step.retry = time.time() + config.retry_delay
            if remove_on_failure:
                step.remove = time.time()

    def fail_dead_worker_step(self, step, config, assistants):
        # If a running worker disconnects, tag all its jobs as FAILED and subject it to the same retry logic
        if step.status in (BATCH_RUNNING, RUNNING) and step.worker_running and step.worker_running not in step.stakeholders | assistants:
            logger.info("Step %r is marked as running by disconnected worker %r -> marking as "
                        "FAILED with retry delay of %rs", step.id, step.worker_running,
                        config.retry_delay)
            step.worker_running = None
            self.set_status(step, FAILED, config)
            step.retry = time.time() + config.retry_delay

    def update_status(self, step, config):
        # Mark steps with no remaining active stakeholders for deletion
        if (not step.stakeholders) and (step.remove is None) and (step.status != RUNNING):
            # We don't check for the RUNNING case, because that is already handled
            # by the fail_dead_worker_step function.
            logger.debug("Step %r has no stakeholders anymore -> might remove "
                         "step in %s seconds", step.id, config.remove_delay)
            step.remove = time.time() + config.remove_delay

        # Re-enable step after the disable time expires
        if step.status == DISABLED and step.scheduler_disable_time is not None:
            if time.time() - step.scheduler_disable_time > config.disable_persist:
                self.re_enable(step, config)

        # Reset FAILED steps to PENDING if max timeout is reached, and retry delay is >= 0
        if step.status == FAILED and config.retry_delay >= 0 and step.retry < time.time():
            self.set_status(step, PENDING, config)

    def may_prune(self, step):
        return step.remove and time.time() >= step.remove

    def inactivate_steps(self, delete_steps):
        # The terminology is a bit confusing: we used to "delete" steps when they became inactive,
        # but with a pluggable state storage, you might very well want to keep some history of
        # older steps as well. That's why we call it "inactivate" (as in the verb)
        for step in delete_steps:
            step_obj = self._steps.pop(step)
            self._status_steps[step_obj.status].pop(step)

    def get_active_workers(self, last_active_lt=None, last_get_work_gt=None):
        for worker in self._active_workers.values():
            if last_active_lt is not None and worker.last_active >= last_active_lt:
                continue
            last_get_work = worker.last_get_work
            if last_get_work_gt is not None and (
                            last_get_work is None or last_get_work <= last_get_work_gt):
                continue
            yield worker

    def get_assistants(self, last_active_lt=None):
        return filter(lambda w: w.assistant, self.get_active_workers(last_active_lt))

    def get_worker_ids(self):
        return self._active_workers.keys()  # only used for unit tests

    def get_worker(self, worker_id):
        return self._active_workers.setdefault(worker_id, Worker(worker_id))

    def inactivate_workers(self, delete_workers):
        # Mark workers as inactive
        for worker in delete_workers:
            self._active_workers.pop(worker)
        self._remove_workers_from_steps(delete_workers)

    def _remove_workers_from_steps(self, workers, remove_stakeholders=True):
        for step in self.get_active_steps():
            if remove_stakeholders:
                step.stakeholders.difference_update(workers)
            step.workers -= workers

    def disable_workers(self, worker_ids):
        self._remove_workers_from_steps(worker_ids, remove_stakeholders=False)
        for worker_id in worker_ids:
            worker = self.get_worker(worker_id)
            worker.disabled = True
            worker.steps.clear()

    def update_metrics(self, step, config):
        if step.status == DISABLED:
            self._metrics_collector.handle_step_disabled(step, config)
        elif step.status == DONE:
            self._metrics_collector.handle_step_done(step)
        elif step.status == FAILED:
            self._metrics_collector.handle_step_failed(step)


class Scheduler:
    """
    Async scheduler that can handle multiple workers, etc.

    Can be run locally or on a server (using RemoteScheduler + server.Server).
    """

    def __init__(self, config=None, resources=None, step_history_impl=None, **kwargs):
        """
        Keyword Arguments:
        :param config: an object of class "scheduler" or None (in which the global instance will be used)
        :param resources: a dict of str->int constraints
        :param step_history_impl: ignore config and use this object as the step history
        """
        self._config = config or scheduler(**kwargs)
        self._state = SimpleStepState(self._config.state_path)

        if step_history_impl:
            self._step_history = step_history_impl
        elif self._config.record_step_history:
            from trun import db_step_history  # Needs sqlalchemy, thus imported here
            self._step_history = db_step_history.DbStepHistory()
        else:
            self._step_history = history.NopHistory()
        self._resources = resources or configuration.get_config().getintdict('resources')  # TODO: Can we make this a Parameter?
        self._make_step = functools.partial(Step, retry_policy=self._config._get_retry_policy())
        self._worker_requests = {}
        self._paused = False

        if self._config.batch_emails:
            self._email_batcher = BatchNotifier()

        self._state._metrics_collector = MetricsCollectors.get(self._config.metrics_collector, self._config.metrics_custom_import)

    def load(self):
        self._state.load()

    def dump(self):
        self._state.dump()
        if self._config.batch_emails:
            self._email_batcher.send_email()

    @rpc_method()
    def prune(self):
        logger.debug("Starting pruning of step graph")
        self._prune_workers()
        self._prune_steps()
        self._prune_emails()
        logger.debug("Done pruning step graph")

    def _prune_workers(self):
        remove_workers = []
        for worker in self._state.get_active_workers():
            if worker.prune(self._config):
                logger.debug("Worker %s timed out (no contact for >=%ss)", worker, self._config.worker_disconnect_delay)
                remove_workers.append(worker.id)

        self._state.inactivate_workers(remove_workers)

    def _prune_steps(self):
        assistant_ids = {w.id for w in self._state.get_assistants()}
        remove_steps = []

        for step in self._state.get_active_steps():
            self._state.fail_dead_worker_step(step, self._config, assistant_ids)
            self._state.update_status(step, self._config)
            if self._state.may_prune(step):
                logger.info("Removing step %r", step.id)
                remove_steps.append(step.id)

        self._state.inactivate_steps(remove_steps)

    def _prune_emails(self):
        if self._config.batch_emails:
            self._email_batcher.update()

    def _update_worker(self, worker_id, worker_reference=None, get_work=False):
        # Keep track of whenever the worker was last active.
        # For convenience also return the worker object.
        worker = self._state.get_worker(worker_id)
        worker.update(worker_reference, get_work=get_work)
        return worker

    def _update_priority(self, step, prio, worker):
        """
        Update priority of the given step.

        Priority can only be increased.
        If the step doesn't exist, a placeholder step is created to preserve priority when the step is later scheduled.
        """
        step.priority = prio = max(prio, step.priority)
        for dep in step.deps or []:
            t = self._state.get_step(dep)
            if t is not None and prio > t.priority:
                self._update_priority(t, prio, worker)

    @rpc_method()
    def add_step_batcher(self, worker, step_family, batched_args, max_batch_size=float('inf')):
        self._state.set_batcher(worker, step_family, batched_args, max_batch_size)

    @rpc_method()
    def forgive_failures(self, step_id=None):
        status = PENDING
        step = self._state.get_step(step_id)
        if step is None:
            return {"step_id": step_id, "status": None}

        # we forgive only failures
        if step.status == FAILED:
            # forgive but do not forget
            self._update_step_history(step, status)
            self._state.set_status(step, status, self._config)
        return {"step_id": step_id, "status": step.status}

    @rpc_method()
    def mark_as_done(self, step_id=None):
        status = DONE
        step = self._state.get_step(step_id)
        if step is None:
            return {"step_id": step_id, "status": None}

        # we can force mark DONE for running or failed steps
        if step.status in {RUNNING, FAILED, DISABLED}:
            self._update_step_history(step, status)
            self._state.set_status(step, status, self._config)
        return {"step_id": step_id, "status": step.status}

    @rpc_method()
    def add_step(self, step_id=None, status=PENDING, runnable=True,
                 deps=None, new_deps=None, expl=None, resources=None,
                 priority=0, family='', module=None, params=None, param_visibilities=None, accepts_messages=False,
                 assistant=False, tracking_url=None, worker=None, batchable=None,
                 batch_id=None, retry_policy_dict=None, owners=None, **kwargs):
        """
        * add step identified by step_id if it doesn't exist
        * if deps is not None, update dependency list
        * update status of step
        * add additional workers/stakeholders
        * update priority when needed
        """
        assert worker is not None
        worker_id = worker
        worker = self._update_worker(worker_id)

        resources = {} if resources is None else resources.copy()

        if retry_policy_dict is None:
            retry_policy_dict = {}

        retry_policy = self._generate_retry_policy(retry_policy_dict)

        if worker.enabled:
            _default_step = self._make_step(
                step_id=step_id, status=PENDING, deps=deps, resources=resources,
                priority=priority, family=family, module=module, params=params, param_visibilities=param_visibilities,
            )
        else:
            _default_step = None

        step = self._state.get_step(step_id, setdefault=_default_step)

        if step is None or (step.status != RUNNING and not worker.enabled):
            return

        # Ignore claims that the step is PENDING if it very recently was marked as DONE.
        if status == PENDING and step.status == DONE and (time.time() - step.updated) < self._config.stable_done_cooldown_secs:
            return

        # for setting priority, we'll sometimes create steps with unset family and params
        if not step.family:
            step.family = family
        if not getattr(step, 'module', None):
            step.module = module
        if not getattr(step, 'param_visibilities', None):
            step.param_visibilities = _get_default(param_visibilities, {})
        if not step.params:
            step.set_params(params)

        if batch_id is not None:
            step.batch_id = batch_id
        if status == RUNNING and not step.worker_running:
            step.worker_running = worker_id
            if batch_id:
                # copy resources_running of the first batch step
                batch_steps = self._state.get_batch_running_steps(batch_id)
                step.resources_running = batch_steps[0].resources_running.copy()
            step.time_running = time.time()

        if accepts_messages is not None:
            step.accepts_messages = accepts_messages

        if tracking_url is not None or step.status != RUNNING:
            step.tracking_url = tracking_url
            if step.batch_id is not None:
                for batch_step in self._state.get_batch_running_steps(step.batch_id):
                    batch_step.tracking_url = tracking_url

        if batchable is not None:
            step.batchable = batchable

        if step.remove is not None:
            step.remove = None  # unmark step for removal so it isn't removed after being added

        if expl is not None:
            step.expl = expl
            if step.batch_id is not None:
                for batch_step in self._state.get_batch_running_steps(step.batch_id):
                    batch_step.expl = expl

        step_is_not_running = step.status not in (RUNNING, BATCH_RUNNING)
        step_started_a_run = status in (DONE, FAILED, RUNNING)
        running_on_this_worker = step.worker_running == worker_id
        if step_is_not_running or (step_started_a_run and running_on_this_worker) or new_deps:
            # don't allow re-scheduling of step while it is running, it must either fail or succeed on the worker actually running it
            if status != step.status or status == PENDING:
                # Update the DB only if there was a acctual change, to prevent noise.
                # We also check for status == PENDING b/c that's the default value
                # (so checking for status != step.status woule lie)
                self._update_step_history(step, status)
            self._state.set_status(step, PENDING if status == SUSPENDED else status, self._config)

        if status == FAILED and self._config.batch_emails:
            batched_params, _ = self._state.get_batcher(worker_id, family)
            if batched_params:
                unbatched_params = {
                    param: value
                    for param, value in step.params.items()
                    if param not in batched_params
                }
            else:
                unbatched_params = step.params
            try:
                expl_raw = json.loads(expl)
            except ValueError:
                expl_raw = expl

            self._email_batcher.add_failure(
                step.pretty_id, step.family, unbatched_params, expl_raw, owners)
            if step.status == DISABLED:
                self._email_batcher.add_disable(
                    step.pretty_id, step.family, unbatched_params, owners)

        if deps is not None:
            step.deps = set(deps)

        if new_deps is not None:
            step.deps.update(new_deps)

        if resources is not None:
            step.resources = resources

        if worker.enabled and not assistant:
            step.stakeholders.add(worker_id)

            # Step dependencies might not exist yet. Let's create dummy steps for them for now.
            # Otherwise the step dependencies might end up being pruned if scheduling takes a long time
            for dep in step.deps or []:
                t = self._state.get_step(dep, setdefault=self._make_step(step_id=dep, status=UNKNOWN, deps=None, priority=priority))
                t.stakeholders.add(worker_id)

        self._update_priority(step, priority, worker_id)

        # Because some steps (non-dynamic dependencies) are `_make_step`ed
        # before we know their retry_policy, we always set it here
        step.retry_policy = retry_policy

        if runnable and status != FAILED and worker.enabled:
            step.workers.add(worker_id)
            self._state.get_worker(worker_id).steps.add(step)
            step.runnable = runnable

    @rpc_method()
    def announce_scheduling_failure(self, step_name, family, params, expl, owners, **kwargs):
        if not self._config.batch_emails:
            return
        worker_id = kwargs['worker']
        batched_params, _ = self._state.get_batcher(worker_id, family)
        if batched_params:
            unbatched_params = {
                param: value
                for param, value in params.items()
                if param not in batched_params
            }
        else:
            unbatched_params = params
        self._email_batcher.add_scheduling_fail(step_name, family, unbatched_params, expl, owners)

    @rpc_method()
    def add_worker(self, worker, info, **kwargs):
        self._state.get_worker(worker).add_info(info)

    @rpc_method()
    def disable_worker(self, worker):
        self._state.disable_workers({worker})

    @rpc_method()
    def set_worker_processes(self, worker, n):
        self._state.get_worker(worker).add_rpc_message('set_worker_processes', n=n)

    @rpc_method()
    def send_scheduler_message(self, worker, step, content):
        if not self._config.send_messages:
            return {"message_id": None}

        message_id = str(uuid.uuid4())
        self._state.get_worker(worker).add_rpc_message('dispatch_scheduler_message', step_id=step,
                                                       message_id=message_id, content=content)

        return {"message_id": message_id}

    @rpc_method()
    def add_scheduler_message_response(self, step_id, message_id, response):
        if self._state.has_step(step_id):
            step = self._state.get_step(step_id)
            step.scheduler_message_responses[message_id] = response

    @rpc_method()
    def get_scheduler_message_response(self, step_id, message_id):
        response = None
        if self._state.has_step(step_id):
            step = self._state.get_step(step_id)
            response = step.scheduler_message_responses.pop(message_id, None)
        return {"response": response}

    @rpc_method()
    def has_step_history(self):
        return self._config.record_step_history

    @rpc_method()
    def is_pause_enabled(self):
        return {'enabled': self._config.pause_enabled}

    @rpc_method()
    def is_paused(self):
        return {'paused': self._paused}

    @rpc_method()
    def pause(self):
        if self._config.pause_enabled:
            self._paused = True

    @rpc_method()
    def unpause(self):
        if self._config.pause_enabled:
            self._paused = False

    @rpc_method()
    def update_resources(self, **resources):
        if self._resources is None:
            self._resources = {}
        self._resources.update(resources)

    @rpc_method()
    def update_resource(self, resource, amount):
        if not isinstance(amount, int) or amount < 0:
            return False
        self._resources[resource] = amount
        return True

    def _generate_retry_policy(self, step_retry_policy_dict):
        retry_policy_dict = self._config._get_retry_policy()._asdict()
        retry_policy_dict.update({k: v for k, v in step_retry_policy_dict.items() if v is not None})
        return RetryPolicy(**retry_policy_dict)

    def _has_resources(self, needed_resources, used_resources):
        if needed_resources is None:
            return True

        available_resources = self._resources or {}
        for resource, amount in needed_resources.items():
            if amount + used_resources[resource] > available_resources.get(resource, 1):
                return False
        return True

    def _used_resources(self):
        used_resources = collections.defaultdict(int)
        if self._resources is not None:
            for step in self._state.get_active_steps_by_status(RUNNING):
                resources_running = getattr(step, "resources_running", step.resources)
                if resources_running:
                    for resource, amount in resources_running.items():
                        used_resources[resource] += amount
        return used_resources

    def _rank(self, step):
        """
        Return worker's rank function for step scheduling.

        :return:
        """

        return step.priority, -step.time

    def _schedulable(self, step):
        if step.status != PENDING:
            return False
        for dep in step.deps:
            dep_step = self._state.get_step(dep, default=None)
            if dep_step is None or dep_step.status != DONE:
                return False
        return True

    def _reset_orphaned_batch_running_steps(self, worker_id):
        running_batch_ids = {
            step.batch_id
            for step in self._state.get_active_steps_by_status(RUNNING)
            if step.worker_running == worker_id
        }
        orphaned_steps = [
            step for step in self._state.get_active_steps_by_status(BATCH_RUNNING)
            if step.worker_running == worker_id and step.batch_id not in running_batch_ids
        ]
        for step in orphaned_steps:
            self._state.set_status(step, PENDING)

    @rpc_method()
    def count_pending(self, worker):
        worker_id, worker = worker, self._state.get_worker(worker)

        num_pending, num_unique_pending, num_pending_last_scheduled = 0, 0, 0
        running_steps = []

        upstream_status_table = {}
        for step in worker.get_steps(self._state, RUNNING):
            if self._upstream_status(step.id, upstream_status_table) == UPSTREAM_DISABLED:
                continue
            # Return a list of currently running steps to the client,
            # makes it easier to troubleshoot
            other_worker = self._state.get_worker(step.worker_running)
            if other_worker is not None:
                more_info = {'step_id': step.id, 'worker': str(other_worker)}
                more_info.update(other_worker.info)
                running_steps.append(more_info)

        for step in worker.get_steps(self._state, PENDING, FAILED):
            if self._upstream_status(step.id, upstream_status_table) == UPSTREAM_DISABLED:
                continue
            num_pending += 1
            num_unique_pending += int(len(step.workers) == 1)
            num_pending_last_scheduled += int(step.workers.peek(last=True) == worker_id)

        return {
            'n_pending_steps': num_pending,
            'n_unique_pending': num_unique_pending,
            'n_pending_last_scheduled': num_pending_last_scheduled,
            'worker_state': worker.state,
            'running_steps': running_steps,
        }

    @rpc_method(allow_null=False)
    def get_work(self, host=None, assistant=False, current_steps=None, worker=None, **kwargs):
        # TODO: remove any expired nodes

        # Algo: iterate over all nodes, find the highest priority node no dependencies and available
        # resources.

        # Resource checking looks both at currently available resources and at which resources would
        # be available if all running steps died and we rescheduled all workers greedily. We do both
        # checks in order to prevent a worker with many low-priority steps from starving other
        # workers with higher priority steps that share the same resources.

        # TODO: remove steps that can't be done, figure out if the worker has absolutely
        # nothing it can wait for

        if self._config.prune_on_get_work:
            self.prune()

        assert worker is not None
        worker_id = worker
        worker = self._update_worker(
            worker_id,
            worker_reference={'host': host},
            get_work=True)
        if not worker.enabled:
            reply = {'n_pending_steps': 0,
                     'running_steps': [],
                     'step_id': None,
                     'n_unique_pending': 0,
                     'worker_state': worker.state,
                     }
            return reply

        if assistant:
            self.add_worker(worker_id, [('assistant', assistant)])

        batched_params, unbatched_params, batched_steps, max_batch_size = None, None, [], 1
        best_step = None
        if current_steps is not None:
            ct_set = set(current_steps)
            for step in sorted(self._state.get_active_steps_by_status(RUNNING), key=self._rank):
                if step.worker_running == worker_id and step.id not in ct_set:
                    best_step = step

        if current_steps is not None:
            # batch running steps that weren't claimed since the last get_work go back in the pool
            self._reset_orphaned_batch_running_steps(worker_id)

        greedy_resources = collections.defaultdict(int)

        worker = self._state.get_worker(worker_id)
        if self._paused:
            relevant_steps = []
        elif worker.is_trivial_worker(self._state):
            relevant_steps = worker.get_steps(self._state, PENDING, RUNNING)
            used_resources = collections.defaultdict(int)
            greedy_workers = dict()  # If there's no resources, then they can grab any step
        else:
            relevant_steps = self._state.get_active_steps_by_status(PENDING, RUNNING)
            used_resources = self._used_resources()
            activity_limit = time.time() - self._config.worker_disconnect_delay
            active_workers = self._state.get_active_workers(last_get_work_gt=activity_limit)
            greedy_workers = dict((worker.id, worker.info.get('workers', 1))
                                  for worker in active_workers)
        steps = list(relevant_steps)
        steps.sort(key=self._rank, reverse=True)

        for step in steps:
            if (best_step and batched_params and step.family == best_step.family and
                    len(batched_steps) < max_batch_size and step.is_batchable() and all(
                    step.params.get(name) == value for name, value in unbatched_params.items()) and
                    step.resources == best_step.resources and self._schedulable(step)):
                for name, params in batched_params.items():
                    params.append(step.params.get(name))
                batched_steps.append(step)
            if best_step:
                continue

            if step.status == RUNNING and (step.worker_running in greedy_workers):
                greedy_workers[step.worker_running] -= 1
                for resource, amount in (getattr(step, 'resources_running', step.resources) or {}).items():
                    greedy_resources[resource] += amount

            if self._schedulable(step) and self._has_resources(step.resources, greedy_resources):
                in_workers = (assistant and step.runnable) or worker_id in step.workers
                if in_workers and self._has_resources(step.resources, used_resources):
                    best_step = step
                    batch_param_names, max_batch_size = self._state.get_batcher(
                        worker_id, step.family)
                    if batch_param_names and step.is_batchable():
                        try:
                            batched_params = {
                                name: [step.params[name]] for name in batch_param_names
                            }
                            unbatched_params = {
                                name: value for name, value in step.params.items()
                                if name not in batched_params
                            }
                            batched_steps.append(step)
                        except KeyError:
                            batched_params, unbatched_params = None, None
                else:
                    workers = itertools.chain(step.workers, [worker_id]) if assistant else step.workers
                    for step_worker in workers:
                        if greedy_workers.get(step_worker, 0) > 0:
                            # use up a worker
                            greedy_workers[step_worker] -= 1

                            # keep track of the resources used in greedy scheduling
                            for resource, amount in (step.resources or {}).items():
                                greedy_resources[resource] += amount

                            break

        reply = self.count_pending(worker_id)

        if len(batched_steps) > 1:
            batch_string = '|'.join(step.id for step in batched_steps)
            batch_id = hashlib.new('md5', batch_string.encode('utf-8'), usedforsecurity=False).hexdigest()
            for step in batched_steps:
                self._state.set_batch_running(step, batch_id, worker_id)

            combined_params = best_step.params.copy()
            combined_params.update(batched_params)

            reply['step_id'] = None
            reply['step_family'] = best_step.family
            reply['step_module'] = getattr(best_step, 'module', None)
            reply['step_params'] = combined_params
            reply['batch_id'] = batch_id
            reply['batch_step_ids'] = [step.id for step in batched_steps]

        elif best_step:
            self.update_metrics_step_started(best_step)
            self._state.set_status(best_step, RUNNING, self._config)
            best_step.worker_running = worker_id
            best_step.resources_running = best_step.resources.copy()
            best_step.time_running = time.time()
            self._update_step_history(best_step, RUNNING, host=host)

            reply['step_id'] = best_step.id
            reply['step_family'] = best_step.family
            reply['step_module'] = getattr(best_step, 'module', None)
            reply['step_params'] = best_step.params

        else:
            reply['step_id'] = None

        return reply

    @rpc_method(attempts=1)
    def ping(self, **kwargs):
        worker_id = kwargs['worker']
        worker = self._update_worker(worker_id)
        return {"rpc_messages": worker.fetch_rpc_messages()}

    def _upstream_status(self, step_id, upstream_status_table):
        if step_id in upstream_status_table:
            return upstream_status_table[step_id]
        elif self._state.has_step(step_id):
            step_stack = [step_id]

            while step_stack:
                dep_id = step_stack.pop()
                dep = self._state.get_step(dep_id)
                if dep:
                    if dep.status == DONE:
                        continue
                    if dep_id not in upstream_status_table:
                        if dep.status == PENDING and dep.deps:
                            step_stack += [dep_id] + list(dep.deps)
                            upstream_status_table[dep_id] = ''  # will be updated postorder
                        else:
                            dep_status = STATUS_TO_UPSTREAM_MAP.get(dep.status, '')
                            upstream_status_table[dep_id] = dep_status
                    elif upstream_status_table[dep_id] == '' and dep.deps:
                        # This is the postorder update step when we set the
                        # status based on the previously calculated child elements
                        status = max((upstream_status_table.get(a_step_id, '')
                                      for a_step_id in dep.deps),
                                     key=UPSTREAM_SEVERITY_KEY)
                        upstream_status_table[dep_id] = status
            return upstream_status_table[dep_id]

    def _serialize_step(self, step_id, include_deps=True, deps=None):
        step = self._state.get_step(step_id)

        ret = {
            'display_name': step.pretty_id,
            'status': step.status,
            'workers': list(step.workers),
            'worker_running': step.worker_running,
            'time_running': getattr(step, "time_running", None),
            'start_time': step.time,
            'last_updated': getattr(step, "updated", step.time),
            'params': step.public_params,
            'name': step.family,
            'priority': step.priority,
            'resources': step.resources,
            'resources_running': getattr(step, "resources_running", None),
            'tracking_url': getattr(step, "tracking_url", None),
            'status_message': getattr(step, "status_message", None),
            'progress_percentage': getattr(step, "progress_percentage", None),
        }
        if step.status == DISABLED:
            ret['re_enable_able'] = step.scheduler_disable_time is not None
        if include_deps:
            ret['deps'] = list(step.deps if deps is None else deps)
        if self._config.send_messages and step.status == RUNNING:
            ret['accepts_messages'] = step.accepts_messages
        return ret

    @rpc_method()
    def graph(self, **kwargs):
        self.prune()
        serialized = {}
        seen = set()
        for step in self._state.get_active_steps():
            serialized.update(self._traverse_graph(step.id, seen))
        return serialized

    def _filter_done(self, step_ids):
        for step_id in step_ids:
            step = self._state.get_step(step_id)
            if step is None or step.status != DONE:
                yield step_id

    def _traverse_graph(self, root_step_id, seen=None, dep_func=None, include_done=True):
        """ Returns the dependency graph rooted at step_id

        This does a breadth-first traversal to find the nodes closest to the
        root before hitting the scheduler.max_graph_nodes limit.

        :param root_step_id: the id of the graph's root
        :return: A map of step id to serialized node
        """

        if seen is None:
            seen = set()
        elif root_step_id in seen:
            return {}

        if dep_func is None:
            def dep_func(t):
                return t.deps

        seen.add(root_step_id)
        serialized = {}
        queue = collections.deque([root_step_id])
        while queue:
            step_id = queue.popleft()

            step = self._state.get_step(step_id)
            if step is None or not step.family:
                logger.debug('Missing step for id [%s]', step_id)

                # NOTE : If a dependency is missing from self._state there is no way to deduce the
                #        step family and parameters.
                family_match = STEP_FAMILY_RE.match(step_id)
                family = family_match.group(1) if family_match else UNKNOWN
                params = {'step_id': step_id}
                serialized[step_id] = {
                    'deps': [],
                    'status': UNKNOWN,
                    'workers': [],
                    'start_time': UNKNOWN,
                    'params': params,
                    'name': family,
                    'display_name': step_id,
                    'priority': 0,
                }
            else:
                deps = dep_func(step)
                if not include_done:
                    deps = list(self._filter_done(deps))
                serialized[step_id] = self._serialize_step(step_id, deps=deps)
                for dep in sorted(deps):
                    if dep not in seen:
                        seen.add(dep)
                        queue.append(dep)

            if step_id != root_step_id:
                del serialized[step_id]['display_name']
            if len(serialized) >= self._config.max_graph_nodes:
                break

        return serialized

    @rpc_method()
    def dep_graph(self, step_id, include_done=True, **kwargs):
        self.prune()
        if not self._state.has_step(step_id):
            return {}
        return self._traverse_graph(step_id, include_done=include_done)

    @rpc_method()
    def inverse_dep_graph(self, step_id, include_done=True, **kwargs):
        self.prune()
        if not self._state.has_step(step_id):
            return {}
        inverse_graph = collections.defaultdict(set)
        for step in self._state.get_active_steps():
            for dep in step.deps:
                inverse_graph[dep].add(step.id)
        return self._traverse_graph(
            step_id, dep_func=lambda t: inverse_graph[t.id], include_done=include_done)

    @rpc_method()
    def step_list(self, status='', upstream_status='', limit=True, search=None, max_shown_steps=None,
                  **kwargs):
        """
        Query for a subset of steps by status.
        """
        if not search:
            count_limit = max_shown_steps or self._config.max_shown_steps
            pre_count = self._state.get_active_step_count_for_status(status)
            if limit and pre_count > count_limit:
                return {'num_steps': -1 if upstream_status else pre_count}
        self.prune()

        result = {}
        upstream_status_table = {}  # used to memoize upstream status
        if search is None:
            def filter_func(_):
                return True
        else:
            terms = search.split()

            def filter_func(t):
                return all(term.casefold() in t.pretty_id.casefold() for term in terms)

        steps = self._state.get_active_steps_by_status(status) if status else self._state.get_active_steps()
        for step in filter(filter_func, steps):
            if step.status != PENDING or not upstream_status or upstream_status == self._upstream_status(step.id, upstream_status_table):
                serialized = self._serialize_step(step.id, include_deps=False)
                result[step.id] = serialized
        if limit and len(result) > (max_shown_steps or self._config.max_shown_steps):
            return {'num_steps': len(result)}
        return result

    def _first_step_display_name(self, worker):
        step_id = worker.info.get('first_step', '')
        if self._state.has_step(step_id):
            return self._state.get_step(step_id).pretty_id
        else:
            return step_id

    @rpc_method()
    def worker_list(self, include_running=True, **kwargs):
        self.prune()
        workers = [
            dict(
                name=worker.id,
                last_active=worker.last_active,
                started=worker.started,
                state=worker.state,
                first_step_display_name=self._first_step_display_name(worker),
                num_unread_rpc_messages=len(worker.rpc_messages),
                **worker.info
            ) for worker in self._state.get_active_workers()]
        workers.sort(key=lambda worker: worker['started'], reverse=True)
        if include_running:
            running = collections.defaultdict(dict)
            for step in self._state.get_active_steps_by_status(RUNNING):
                if step.worker_running:
                    running[step.worker_running][step.id] = self._serialize_step(step.id, include_deps=False)

            num_pending = collections.defaultdict(int)
            num_uniques = collections.defaultdict(int)
            for step in self._state.get_active_steps_by_status(PENDING):
                for worker in step.workers:
                    num_pending[worker] += 1
                if len(step.workers) == 1:
                    num_uniques[list(step.workers)[0]] += 1

            for worker in workers:
                steps = running[worker['name']]
                worker['num_running'] = len(steps)
                worker['num_pending'] = num_pending[worker['name']]
                worker['num_uniques'] = num_uniques[worker['name']]
                worker['running'] = steps
        return workers

    @rpc_method()
    def resource_list(self):
        """
        Resources usage info and their consumers (steps).
        """
        self.prune()
        resources = [
            dict(
                name=resource,
                num_total=r_dict['total'],
                num_used=r_dict['used']
            ) for resource, r_dict in self.resources().items()]
        if self._resources is not None:
            consumers = collections.defaultdict(dict)
            for step in self._state.get_active_steps_by_status(RUNNING):
                if step.status == RUNNING and step.resources:
                    for resource, amount in step.resources.items():
                        consumers[resource][step.id] = self._serialize_step(step.id, include_deps=False)
            for resource in resources:
                steps = consumers[resource['name']]
                resource['num_consumer'] = len(steps)
                resource['running'] = steps
        return resources

    def resources(self):
        ''' get total resources and available ones '''
        used_resources = self._used_resources()
        ret = collections.defaultdict(dict)
        for resource, total in self._resources.items():
            ret[resource]['total'] = total
            if resource in used_resources:
                ret[resource]['used'] = used_resources[resource]
            else:
                ret[resource]['used'] = 0
        return ret

    @rpc_method()
    def step_search(self, step_str, **kwargs):
        """
        Query for a subset of steps by step_id.

        :param step_str:
        :return:
        """
        self.prune()
        result = collections.defaultdict(dict)
        for step in self._state.get_active_steps():
            if step.id.find(step_str) != -1:
                serialized = self._serialize_step(step.id, include_deps=False)
                result[step.status][step.id] = serialized
        return result

    @rpc_method()
    def re_enable_step(self, step_id):
        serialized = {}
        step = self._state.get_step(step_id)
        if step and step.status == DISABLED and step.scheduler_disable_time:
            self._state.re_enable(step, self._config)
            serialized = self._serialize_step(step_id)
        return serialized

    @rpc_method()
    def fetch_error(self, step_id, **kwargs):
        if self._state.has_step(step_id):
            step = self._state.get_step(step_id)
            return {"stepId": step_id, "error": step.expl, 'displayName':
                    step.pretty_id, 'stepParams': step.params, 'stepModule':
                    step.module, 'stepFamily': step.family}
        else:
            return {"stepId": step_id, "error": ""}

    @rpc_method()
    def set_step_status_message(self, step_id, status_message):
        if self._state.has_step(step_id):
            step = self._state.get_step(step_id)
            step.status_message = status_message
            if step.status == RUNNING and step.batch_id is not None:
                for batch_step in self._state.get_batch_running_steps(step.batch_id):
                    batch_step.status_message = status_message

    @rpc_method()
    def get_step_status_message(self, step_id):
        if self._state.has_step(step_id):
            step = self._state.get_step(step_id)
            return {"stepId": step_id, "statusMessage": step.status_message}
        else:
            return {"stepId": step_id, "statusMessage": ""}

    @rpc_method()
    def set_step_progress_percentage(self, step_id, progress_percentage):
        if self._state.has_step(step_id):
            step = self._state.get_step(step_id)
            step.progress_percentage = progress_percentage
            if step.status == RUNNING and step.batch_id is not None:
                for batch_step in self._state.get_batch_running_steps(step.batch_id):
                    batch_step.progress_percentage = progress_percentage

    @rpc_method()
    def get_step_progress_percentage(self, step_id):
        if self._state.has_step(step_id):
            step = self._state.get_step(step_id)
            return {"stepId": step_id, "progressPercentage": step.progress_percentage}
        else:
            return {"stepId": step_id, "progressPercentage": None}

    @rpc_method()
    def decrease_running_step_resources(self, step_id, decrease_resources):
        if self._state.has_step(step_id):
            step = self._state.get_step(step_id)
            if step.status != RUNNING:
                return

            def decrease(resources, decrease_resources):
                for resource, decrease_amount in decrease_resources.items():
                    if decrease_amount > 0 and resource in resources:
                        resources[resource] = max(0, resources[resource] - decrease_amount)

            decrease(step.resources_running, decrease_resources)
            if step.batch_id is not None:
                for batch_step in self._state.get_batch_running_steps(step.batch_id):
                    decrease(batch_step.resources_running, decrease_resources)

    @rpc_method()
    def get_running_step_resources(self, step_id):
        if self._state.has_step(step_id):
            step = self._state.get_step(step_id)
            return {"stepId": step_id, "resources": getattr(step, "resources_running", None)}
        else:
            return {"stepId": step_id, "resources": None}

    def _update_step_history(self, step, status, host=None):
        try:
            if status == DONE or status == FAILED:
                successful = (status == DONE)
                self._step_history.step_finished(step, successful)
            elif status == PENDING:
                self._step_history.step_scheduled(step)
            elif status == RUNNING:
                self._step_history.step_started(step, host)
        except BaseException:
            logger.warning("Error saving Step history", exc_info=True)

    @property
    def step_history(self):
        # Used by server.py to expose the calls
        return self._step_history

    @rpc_method()
    def update_metrics_step_started(self, step):
        self._state._metrics_collector.handle_step_started(step)
