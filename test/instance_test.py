
from helpers import unittest

import trun
import trun.worker
import trun.date_interval
import trun.notifications

trun.notifications.DEBUG = True


class InstanceTest(unittest.TestCase):

    def test_simple(self):
        class DummyStep(trun.Step):
            x = trun.Parameter()

        dummy_1 = DummyStep(1)
        dummy_2 = DummyStep(2)
        dummy_1b = DummyStep(1)

        self.assertNotEqual(dummy_1, dummy_2)
        self.assertEqual(dummy_1, dummy_1b)

    def test_dep(self):
        test = self

        class A(trun.Step):
            step_namespace = 'instance'  # to prevent step name conflict between tests

            def __init__(self):
                self.has_run = False
                super(A, self).__init__()

            def run(self):
                self.has_run = True

        class B(trun.Step):
            x = trun.Parameter()

            def requires(self):
                return A()  # This will end up referring to the same object

            def run(self):
                test.assertTrue(self.requires().has_run)

        trun.build([B(1), B(2)], local_scheduler=True)

    def test_external_instance_cache(self):
        class A(trun.Step):
            step_namespace = 'instance'  # to prevent step name conflict between tests
            pass

        class OtherA(trun.ExternalStep):
            step_family = "A"

        oa = OtherA()
        a = A()
        self.assertNotEqual(oa, a)

    def test_date(self):
        ''' Adding unit test because we had a problem with this '''
        class DummyStep(trun.Step):
            x = trun.DateIntervalParameter()

        dummy_1 = DummyStep(trun.date_interval.Year(2012))
        dummy_2 = DummyStep(trun.date_interval.Year(2013))
        dummy_1b = DummyStep(trun.date_interval.Year(2012))

        self.assertNotEqual(dummy_1, dummy_2)
        self.assertEqual(dummy_1, dummy_1b)

    def test_unhashable_type(self):
        # See #857
        class DummyStep(trun.Step):
            x = trun.Parameter()

        dummy = DummyStep(x={})  # NOQA
