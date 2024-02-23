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

import os
import time
import tempfile

from helpers import TrunTestCase, RunOnceStep

import trun
import trun.scheduler
import trun.worker


def fast_worker(scheduler, **kwargs):
    kwargs.setdefault("ping_interval", 0.5)
    kwargs.setdefault("force_multiprocessing", True)
    return trun.worker.Worker(scheduler=scheduler, **kwargs)


class WriteMessageToFile(trun.Step):

    path = trun.Parameter()

    accepts_messages = True

    def output(self):
        return trun.LocalTarget(self.path)

    def run(self):
        msg = ""

        time.sleep(1)
        if not self.scheduler_messages.empty():
            msg = self.scheduler_messages.get().content

        with self.output().open("w") as f:
            f.write(msg + "\n")


class SchedulerMessageTest(TrunTestCase):

    def test_scheduler_methods(self):
        sch = trun.scheduler.Scheduler(send_messages=True)
        sch.add_step(step_id="foo-step", worker="foo-worker")

        res = sch.send_scheduler_message("foo-worker", "foo-step", "message content")
        message_id = res["message_id"]
        self.assertTrue(len(message_id) > 0)
        self.assertIn("-", message_id)

        sch.add_scheduler_message_response("foo-step", message_id, "message response")
        res = sch.get_scheduler_message_response("foo-step", message_id)
        response = res["response"]
        self.assertEqual(response, "message response")

    def test_receive_messsage(self):
        sch = trun.scheduler.Scheduler(send_messages=True)
        with fast_worker(sch) as w:
            with tempfile.NamedTemporaryFile() as tmp:
                if os.path.exists(tmp.name):
                    os.remove(tmp.name)

                step = WriteMessageToFile(path=tmp.name)
                w.add(step)

                sch.send_scheduler_message(w._id, step.step_id, "test")
                w.run()

                self.assertTrue(os.path.exists(tmp.name))
                with open(tmp.name, "r") as f:
                    self.assertEqual(str(f.read()).strip(), "test")

    def test_receive_messages_disabled(self):
        sch = trun.scheduler.Scheduler(send_messages=True)
        with fast_worker(sch, force_multiprocessing=False) as w:
            class MyStep(RunOnceStep):
                def run(self):
                    self.had_queue = self.scheduler_messages is not None
                    super(MyStep, self).run()

            step = MyStep()
            w.add(step)

            sch.send_scheduler_message(w._id, step.step_id, "test")
            w.run()

            self.assertFalse(step.had_queue)

    def test_send_messages_disabled(self):
        sch = trun.scheduler.Scheduler(send_messages=False)
        with fast_worker(sch) as w:
            with tempfile.NamedTemporaryFile() as tmp:
                if os.path.exists(tmp.name):
                    os.remove(tmp.name)

                step = WriteMessageToFile(path=tmp.name)
                w.add(step)

                sch.send_scheduler_message(w._id, step.step_id, "test")
                w.run()

                self.assertTrue(os.path.exists(tmp.name))
                with open(tmp.name, "r") as f:
                    self.assertEqual(str(f.read()).strip(), "")
