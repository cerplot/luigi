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
Abstract class for step history.
Currently the only subclass is :py:class:`~luigi.db_step_history.DbStepHistory`.
"""

import abc
import logging


logger = logging.getLogger('luigi-interface')


class StoredStep:
    """
    Interface for methods on StepHistory
    """

    # TODO : do we need this step as distinct from luigi.scheduler.Step?
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
