# -*- coding: utf-8 -*-
#
# Copyright 2016 VNG Corporation
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

from helpers import TrunTestCase
from trun.scheduler import Scheduler
from trun.worker import Worker
import trun
import threading


class WorkerKeepAliveUpstreamTest(TrunTestCase):
    """
    Tests related to how the worker stays alive after upstream status changes.

    See https://github.com/spotify/trun/pull/1789
    """
    def run(self, result=None):
        """
        Common setup code. Due to the contextmanager cant use normal setup
        """
        self.sch = Scheduler(retry_delay=0.00000001, retry_count=2)

        with Worker(scheduler=self.sch, worker_id='X', keep_alive=True, wait_interval=0.1, wait_jitter=0) as w:
            self.w = w
            super(WorkerKeepAliveUpstreamTest, self).run(result)

    def test_alive_while_has_failure(self):
        """
        One dependency disables and one fails
        """
        class Disabler(trun.Step):
            pass

        class Failer(trun.Step):
            did_run = False

            def run(self):
                self.did_run = True

        class Wrapper(trun.WrapperStep):
            def requires(self):
                return (Disabler(), Failer())

        self.w.add(Wrapper())
        disabler = Disabler().step_id
        failer = Failer().step_id
        self.sch.add_step(disabler, 'FAILED', worker='X')
        self.sch.prune()  # Make scheduler unfail the disabled step
        self.sch.add_step(disabler, 'FAILED', worker='X')  # Disable it
        self.sch.add_step(failer, 'FAILED', worker='X')  # Fail it
        try:
            t = threading.Thread(target=self.w.run)
            t.start()
            t.join(timeout=1)  # Wait 1 second
            self.assertTrue(t.is_alive())  # It shouldn't stop trying, the failed step should be retried!
            self.assertFalse(Failer.did_run)  # It should never have run, the cooldown is longer than a second.
        finally:
            self.sch.prune()  # Make it, like die. Couldn't find a more forceful way to do this.
            t.join(timeout=1)  # Wait 1 second
            assert not t.is_alive()

    def test_alive_while_has_success(self):
        """
        One dependency disables and one succeeds
        """
        # TODO: Fix copy paste mess
        class Disabler(trun.Step):
            pass

        class Succeeder(trun.Step):
            did_run = False

            def run(self):
                self.did_run = True

        class Wrapper(trun.WrapperStep):
            def requires(self):
                return (Disabler(), Succeeder())

        self.w.add(Wrapper())
        disabler = Disabler().step_id
        succeeder = Succeeder().step_id
        self.sch.add_step(disabler, 'FAILED', worker='X')
        self.sch.prune()  # Make scheduler unfail the disabled step
        self.sch.add_step(disabler, 'FAILED', worker='X')  # Disable it
        self.sch.add_step(succeeder, 'DONE', worker='X')  # Fail it
        try:
            t = threading.Thread(target=self.w.run)
            t.start()
            t.join(timeout=1)  # Wait 1 second
            self.assertFalse(t.is_alive())  # The worker should think that it should stop ...
            # ... because in this case the only work remaining depends on DISABLED steps,
            # hence it's not worth considering the wrapper step as a PENDING step to
            # keep the worker alive anymore.
            self.assertFalse(Succeeder.did_run)  # It should never have run, it succeeded already
        finally:
            self.sch.prune()  # This shouldnt be necessary in this version, but whatevs
            t.join(timeout=1)  # Wait 1 second
            assert not t.is_alive()
