

import unittest
import trun
from trun.contrib.external_daily_snapshot import ExternalDailySnapshot
from trun.mock import MockTarget
import datetime


class DataDump(ExternalDailySnapshot):
    param = trun.Parameter()
    a = trun.Parameter(default='zebra')
    aa = trun.Parameter(default='Congo')

    def output(self):
        return MockTarget('data-%s-%s-%s-%s' % (self.param, self.a, self.aa, self.date))


class ExternalDailySnapshotTest(unittest.TestCase):
    def test_latest(self):
        MockTarget('data-xyz-zebra-Congo-2012-01-01').open('w').close()
        d = DataDump.latest(date=datetime.date(2012, 1, 10), param='xyz')
        self.assertEquals(d.date, datetime.date(2012, 1, 1))

    def test_latest_not_exists(self):
        MockTarget('data-abc-zebra-Congo-2012-01-01').open('w').close()
        d = DataDump.latest(date=datetime.date(2012, 1, 11), param='abc', lookback=5)
        self.assertEquals(d.date, datetime.date(2012, 1, 7))

    def test_deterministic(self):
        MockTarget('data-pqr-zebra-Congo-2012-01-01').open('w').close()
        d = DataDump.latest(date=datetime.date(2012, 1, 10), param='pqr', a='zebra', aa='Congo')
        self.assertEquals(d.date, datetime.date(2012, 1, 1))

        MockTarget('data-pqr-zebra-Congo-2012-01-05').open('w').close()
        d = DataDump.latest(date=datetime.date(2012, 1, 10), param='pqr', aa='Congo', a='zebra')
        self.assertEquals(d.date, datetime.date(2012, 1, 1))  # Should still be the same
