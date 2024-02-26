"""
Abstract class for step history.
Currently the only subclass is :py:class:`~trun.db_step_history.DbStepHistory`.
"""

import abc
import logging


logger = logging.getLogger('trun-interface')


class StoredStep:
    """
    Interface for methods on StepHistory
    """

    # TODO : do we need this step as distinct from trun.scheduler.Step?
    #        this only records host and record_id in addition to step parameters.

    def __init__(self, step, status, host=None):
        self._step = step
        self.status = status
        self.record_id = None
        self.host = host

    @property
    def step_family(self):
        return self._step.family

    @property
    def parameters(self):
        return self._step.params


class StepHistory(metaclass=abc.ABCMeta):
    """
    Abstract Base Class for updating the run history of a step
    """

    @abc.abstractmethod
    def step_scheduled(self, step):
        pass

    @abc.abstractmethod
    def step_finished(self, step, successful):
        pass

    @abc.abstractmethod
    def step_started(self, step, worker_host):
        pass

    # TODO(erikbern): should web method (find_latest_runs etc) be abstract?


class NopHistory(StepHistory):

    def step_scheduled(self, step):
        pass

    def step_finished(self, step, successful):
        pass

    def step_started(self, step, worker_host):
        pass
