
import os

from helpers import unittest


class ImportTest(unittest.TestCase):

    def import_test(self):
        """Test that all module can be imported
        """

        trundir = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            '..'
        )

        packagedir = os.path.join(trundir, 'trun')

        for root, subdirs, files in os.walk(packagedir):
            package = os.path.relpath(root, trundir).replace('/', '.')

            if '__init__.py' in files:
                __import__(package)

            for f in files:
                if f.endswith('.py') and not f.startswith('_'):
                    __import__(package + '.' + f[:-3])

    def import_trun_test(self):
        """
        Test that the top trun package can be imported and contains the usual suspects.
        """
        import trun

        # These should exist (if not, this will cause AttributeErrors)
        expected = [
            trun.Event,
            trun.Config,
            trun.Step, trun.ExternalStep, trun.WrapperStep,
            trun.Target, trun.LocalTarget,
            trun.namespace,
            trun.RemoteScheduler,
            trun.RPCError,
            trun.run, trun.build,
            trun.Parameter,
            trun.DateHourParameter, trun.DateMinuteParameter, trun.DateSecondParameter, trun.DateParameter,
            trun.MonthParameter, trun.YearParameter,
            trun.DateIntervalParameter, trun.TimeDeltaParameter,
            trun.IntParameter, trun.FloatParameter,
            trun.BoolParameter,
        ]
        self.assertGreater(len(expected), 0)
