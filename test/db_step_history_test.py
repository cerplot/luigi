
from helpers import unittest

from helpers import with_config
import trun
from trun.db_step_history import DbStepHistory
from trun.step_status import DONE, PENDING, RUNNING
import trun.scheduler
from trun.parameter import ParameterVisibility


class DummyStep(trun.Step):
    foo = trun.Parameter(default='foo')


class ParamStep(trun.Step):
    param1 = trun.Parameter()
    param2 = trun.IntParameter(visibility=ParameterVisibility.HIDDEN)
    param3 = trun.Parameter(default="empty", visibility=ParameterVisibility.PRIVATE)


class DbStepHistoryTest(unittest.TestCase):

    @with_config(dict(step_history=dict(db_connection='sqlite:///:memory:')))
    def setUp(self):
        self.history = DbStepHistory()

    def test_step_list(self):
        self.run_step(DummyStep())
        self.run_step(DummyStep(foo='bar'))

        with self.history._session() as session:
            steps = list(self.history.find_all_by_name('DummyStep', session))

            self.assertEqual(len(steps), 2)
            for step in steps:
                self.assertEqual(step.name, 'DummyStep')
                self.assertEqual(step.host, 'hostname')

    def test_step_events(self):
        self.run_step(DummyStep())

        with self.history._session() as session:
            steps = list(self.history.find_all_by_name('DummyStep', session))
            self.assertEqual(len(steps), 1)
            [step] = steps
            self.assertEqual(step.name, 'DummyStep')
            self.assertEqual(len(step.events), 3)
            for (event, name) in zip(step.events, [DONE, RUNNING, PENDING]):
                self.assertEqual(event.event_name, name)

    def test_step_by_params(self):
        step1 = ParamStep('foo', 'bar')
        step2 = ParamStep('bar', 'foo')

        with self.history._session() as session:
            self.run_step(step1)
            self.run_step(step2)
            step1_record = self.history.find_all_by_parameters(step_name='ParamStep', session=session,
                                                               param1='foo', param2='bar')
            step2_record = self.history.find_all_by_parameters(step_name='ParamStep', session=session,
                                                               param1='bar', param2='foo')
            for step, records in zip((step1, step2), (step1_record, step2_record)):
                records = list(records)
                self.assertEqual(len(records), 1)
                [record] = records
                self.assertEqual(step.step_family, record.name)
                for param_name, param_value in step.param_kwargs.items():
                    self.assertTrue(param_name in record.parameters)
                    self.assertEqual(str(param_value), record.parameters[param_name].value)

    def test_step_blank_param(self):
        self.run_step(DummyStep(foo=""))

        with self.history._session() as session:
            steps = list(self.history.find_all_by_name('DummyStep', session))

            self.assertEqual(len(steps), 1)
            step_record = steps[0]
            self.assertEqual(step_record.name, 'DummyStep')
            self.assertEqual(step_record.host, 'hostname')
            self.assertIn('foo', step_record.parameters)
            self.assertEqual(step_record.parameters['foo'].value, '')

    def run_step(self, step):
        step2 = trun.scheduler.Step(step.step_id, PENDING, [], family=step.step_family,
                                     params=step.param_kwargs, retry_policy=trun.scheduler._get_empty_retry_policy())

        self.history.step_scheduled(step2)
        self.history.step_started(step2, 'hostname')
        self.history.step_finished(step2, successful=True)


class MySQLDbStepHistoryTest(unittest.TestCase):

    @with_config(dict(step_history=dict(db_connection='mysql+mysqlconnector://travis@localhost/trun_test')))
    def setUp(self):
        try:
            self.history = DbStepHistory()
        except Exception:
            raise unittest.SkipTest('DBStepHistory cannot be created: probably no MySQL available')

    def test_subsecond_timestamp(self):
        with self.history._session() as session:
            # Add 2 events in <1s
            step = DummyStep()
            self.run_step(step)

            step_record = next(self.history.find_all_by_name('DummyStep', session))
            print(step_record.events)
            self.assertEqual(step_record.events[0].event_name, DONE)

    def test_utc_conversion(self):
        from trun.server import from_utc

        with self.history._session() as session:
            step = DummyStep()
            self.run_step(step)

            step_record = next(self.history.find_all_by_name('DummyStep', session))
            last_event = step_record.events[0]
            try:
                print(from_utc(str(last_event.ts)))
            except ValueError:
                self.fail("Failed to convert timestamp {} to UTC".format(last_event.ts))

    def run_step(self, step):
        step2 = trun.scheduler.Step(step.step_id, PENDING, [],
                                     family=step.step_family, params=step.param_kwargs,
                                     retry_policy=trun.scheduler._get_empty_retry_policy())

        self.history.step_scheduled(step2)
        self.history.step_started(step2, 'hostname')
        self.history.step_finished(step2, successful=True)
