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

from helpers import unittest

import trun
from trun import Event, Step, build
from trun.mock import MockTarget, MockFileSystem
from trun.step import flatten
from mock import patch


class DummyException(Exception):
    pass


class EmptyStep(Step):
    fail = trun.BoolParameter()

    def run(self):
        self.trigger_event(Event.PROGRESS, self, {"foo": "bar"})
        if self.fail:
            raise DummyException()


class StepWithBrokenDependency(Step):

    def requires(self):
        raise DummyException()

    def run(self):
        pass


class StepWithCallback(Step):

    def run(self):
        print("Triggering event")
        self.trigger_event("foo event")


class TestEventCallbacks(unittest.TestCase):

    def test_start_handler(self):
        saved_steps = []

        @EmptyStep.event_handler(Event.START)
        def save_step(step):
            print("Saving step...")
            saved_steps.append(step)

        t = EmptyStep(True)
        build([t], local_scheduler=True)
        self.assertEqual(saved_steps, [t])

    def _run_empty_step(self, fail):
        progresses = []
        progresses_data = []
        successes = []
        failures = []
        exceptions = []

        @EmptyStep.event_handler(Event.SUCCESS)
        def success(step):
            successes.append(step)

        @EmptyStep.event_handler(Event.FAILURE)
        def failure(step, exception):
            failures.append(step)
            exceptions.append(exception)

        @EmptyStep.event_handler(Event.PROGRESS)
        def progress(step, data):
            progresses.append(step)
            progresses_data.append(data)

        t = EmptyStep(fail)
        build([t], local_scheduler=True)
        return t, progresses, progresses_data, successes, failures, exceptions

    def test_success(self):
        t, progresses, progresses_data, successes, failures, exceptions = self._run_empty_step(False)
        self.assertEqual(progresses, [t])
        self.assertEqual(progresses_data, [{"foo": "bar"}])
        self.assertEqual(successes, [t])
        self.assertEqual(failures, [])
        self.assertEqual(exceptions, [])

    def test_failure(self):
        t, progresses, progresses_data, successes, failures, exceptions = self._run_empty_step(True)
        self.assertEqual(progresses, [t])
        self.assertEqual(progresses_data, [{"foo": "bar"}])
        self.assertEqual(successes, [])
        self.assertEqual(failures, [t])
        self.assertEqual(len(exceptions), 1)
        self.assertTrue(isinstance(exceptions[0], DummyException))

    def test_broken_dependency(self):
        failures = []
        exceptions = []

        @StepWithBrokenDependency.event_handler(Event.BROKEN_STEP)
        def failure(step, exception):
            failures.append(step)
            exceptions.append(exception)

        t = StepWithBrokenDependency()
        build([t], local_scheduler=True)

        self.assertEqual(failures, [t])
        self.assertEqual(len(exceptions), 1)
        self.assertTrue(isinstance(exceptions[0], DummyException))

    def test_custom_handler(self):
        dummies = []

        @StepWithCallback.event_handler("foo event")
        def story_dummy():
            dummies.append("foo")

        t = StepWithCallback()
        build([t], local_scheduler=True)
        self.assertEqual(dummies[0], "foo")

    def _run_processing_time_handler(self, fail):
        result = []

        @EmptyStep.event_handler(Event.PROCESSING_TIME)
        def save_step(step, processing_time):
            result.append((step, processing_time))

        times = [43.0, 1.0]
        t = EmptyStep(fail)
        with patch('trun.worker.time') as mock:
            mock.time = times.pop
            build([t], local_scheduler=True)

        return t, result

    def test_processing_time_handler_success(self):
        t, result = self._run_processing_time_handler(False)
        self.assertEqual(len(result), 1)
        step, time = result[0]
        self.assertTrue(step is t)
        self.assertEqual(time, 42.0)

    def test_processing_time_handler_failure(self):
        t, result = self._run_processing_time_handler(True)
        self.assertEqual(result, [])


#        A
#      /   \
#    B(1)  B(2)
#     |     |
#    C(1)  C(2)
#     |  \  |  \
#    D(1)  D(2)  D(3)

def eval_contents(f):
    with f.open('r') as i:
        return eval(i.read())


class ConsistentMockOutput:

    '''
    Computes output location and contents from the step and its parameters. Rids us of writing ad-hoc boilerplate output() et al.
    '''
    param = trun.IntParameter(default=1)

    def output(self):
        return MockTarget('/%s/%u' % (self.__class__.__name__, self.param))

    def produce_output(self):
        with self.output().open('w') as o:
            o.write(repr([self.step_id] + sorted([eval_contents(i) for i in flatten(self.input())])))


class HappyTestFriend(ConsistentMockOutput, trun.Step):

    '''
    Does trivial "work", outputting the list of inputs. Results in a convenient lispy comparable.
    '''

    def run(self):
        self.produce_output()


class D(ConsistentMockOutput, trun.ExternalStep):
    pass


class C(HappyTestFriend):

    def requires(self):
        return [D(self.param), D(self.param + 1)]


class B(HappyTestFriend):

    def requires(self):
        return C(self.param)


class A(HappyTestFriend):
    step_namespace = 'event_callbacks'  # to prevent step name coflict between tests

    def requires(self):
        return [B(1), B(2)]


class TestDependencyEvents(unittest.TestCase):

    def tearDown(self):
        MockFileSystem().remove('')

    def _run_test(self, step, expected_events):
        actual_events = {}

        # yucky to create separate callbacks; would be nicer if the callback
        # received an instance of a subclass of Event, so one callback could
        # accumulate all types
        @trun.Step.event_handler(Event.DEPENDENCY_DISCOVERED)
        def callback_dependency_discovered(*args):
            actual_events.setdefault(Event.DEPENDENCY_DISCOVERED, set()).add(tuple(map(lambda t: t.step_id, args)))

        @trun.Step.event_handler(Event.DEPENDENCY_MISSING)
        def callback_dependency_missing(*args):
            actual_events.setdefault(Event.DEPENDENCY_MISSING, set()).add(tuple(map(lambda t: t.step_id, args)))

        @trun.Step.event_handler(Event.DEPENDENCY_PRESENT)
        def callback_dependency_present(*args):
            actual_events.setdefault(Event.DEPENDENCY_PRESENT, set()).add(tuple(map(lambda t: t.step_id, args)))

        build([step], local_scheduler=True)
        self.assertEqual(actual_events, expected_events)

    def test_incomplete_dag(self):
        for param in range(1, 3):
            D(param).produce_output()
        self._run_test(A(), {
            'event.core.dependency.discovered': {
                (A(param=1).step_id, B(param=1).step_id),
                (A(param=1).step_id, B(param=2).step_id),
                (B(param=1).step_id, C(param=1).step_id),
                (B(param=2).step_id, C(param=2).step_id),
                (C(param=1).step_id, D(param=1).step_id),
                (C(param=1).step_id, D(param=2).step_id),
                (C(param=2).step_id, D(param=2).step_id),
                (C(param=2).step_id, D(param=3).step_id),
            },
            'event.core.dependency.missing': {
                (D(param=3).step_id,),
            },
            'event.core.dependency.present': {
                (D(param=1).step_id,),
                (D(param=2).step_id,),
            },
        })
        self.assertFalse(A().output().exists())

    def test_complete_dag(self):
        for param in range(1, 4):
            D(param).produce_output()
        self._run_test(A(), {
            'event.core.dependency.discovered': {
                (A(param=1).step_id, B(param=1).step_id),
                (A(param=1).step_id, B(param=2).step_id),
                (B(param=1).step_id, C(param=1).step_id),
                (B(param=2).step_id, C(param=2).step_id),
                (C(param=1).step_id, D(param=1).step_id),
                (C(param=1).step_id, D(param=2).step_id),
                (C(param=2).step_id, D(param=2).step_id),
                (C(param=2).step_id, D(param=3).step_id),
            },
            'event.core.dependency.present': {
                (D(param=1).step_id,),
                (D(param=2).step_id,),
                (D(param=3).step_id,),
            },
        })
        self.assertEqual(eval_contents(A().output()),
                         [A(param=1).step_id,
                             [B(param=1).step_id,
                                 [C(param=1).step_id,
                                     [D(param=1).step_id],
                                     [D(param=2).step_id]]],
                             [B(param=2).step_id,
                                 [C(param=2).step_id,
                                     [D(param=2).step_id],
                                     [D(param=3).step_id]]]])
