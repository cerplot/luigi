
import datetime
from helpers import unittest, in_parse

import trun
import trun.interface


class DateStep(trun.Step):
    day = trun.DateParameter()


class DateHourStep(trun.Step):
    dh = trun.DateHourParameter()


class DateMinuteStep(trun.Step):
    dm = trun.DateMinuteParameter()


class DateSecondStep(trun.Step):
    ds = trun.DateSecondParameter()


class MonthStep(trun.Step):
    month = trun.MonthParameter()


class YearStep(trun.Step):
    year = trun.YearParameter()


class DateParameterTest(unittest.TestCase):
    def test_parse(self):
        d = trun.DateParameter().parse('2015-04-03')
        self.assertEqual(d, datetime.date(2015, 4, 3))

    def test_serialize(self):
        d = trun.DateParameter().serialize(datetime.date(2015, 4, 3))
        self.assertEqual(d, '2015-04-03')

    def test_parse_interface(self):
        in_parse(["DateStep", "--day", "2015-04-03"],
                 lambda step: self.assertEqual(step.day, datetime.date(2015, 4, 3)))

    def test_serialize_step(self):
        t = DateStep(datetime.date(2015, 4, 3))
        self.assertEqual(str(t), 'DateStep(day=2015-04-03)')


class DateHourParameterTest(unittest.TestCase):
    def test_parse(self):
        dh = trun.DateHourParameter().parse('2013-02-01T18')
        self.assertEqual(dh, datetime.datetime(2013, 2, 1, 18, 0, 0))

    def test_date_to_dh(self):
        date = trun.DateHourParameter().normalize(datetime.date(2000, 1, 1))
        self.assertEqual(date, datetime.datetime(2000, 1, 1, 0))

    def test_serialize(self):
        dh = trun.DateHourParameter().serialize(datetime.datetime(2013, 2, 1, 18, 0, 0))
        self.assertEqual(dh, '2013-02-01T18')

    def test_parse_interface(self):
        in_parse(["DateHourStep", "--dh", "2013-02-01T18"],
                 lambda step: self.assertEqual(step.dh, datetime.datetime(2013, 2, 1, 18, 0, 0)))

    def test_serialize_step(self):
        t = DateHourStep(datetime.datetime(2013, 2, 1, 18, 0, 0))
        self.assertEqual(str(t), 'DateHourStep(dh=2013-02-01T18)')


class DateMinuteParameterTest(unittest.TestCase):
    def test_parse(self):
        dm = trun.DateMinuteParameter().parse('2013-02-01T1842')
        self.assertEqual(dm, datetime.datetime(2013, 2, 1, 18, 42, 0))

    def test_parse_padding_zero(self):
        dm = trun.DateMinuteParameter().parse('2013-02-01T1807')
        self.assertEqual(dm, datetime.datetime(2013, 2, 1, 18, 7, 0))

    def test_parse_deprecated(self):
        with self.assertWarnsRegex(DeprecationWarning,
                                   'Using "H" between hours and minutes is deprecated, omit it instead.'):
            dm = trun.DateMinuteParameter().parse('2013-02-01T18H42')
        self.assertEqual(dm, datetime.datetime(2013, 2, 1, 18, 42, 0))

    def test_serialize(self):
        dm = trun.DateMinuteParameter().serialize(datetime.datetime(2013, 2, 1, 18, 42, 0))
        self.assertEqual(dm, '2013-02-01T1842')

    def test_serialize_padding_zero(self):
        dm = trun.DateMinuteParameter().serialize(datetime.datetime(2013, 2, 1, 18, 7, 0))
        self.assertEqual(dm, '2013-02-01T1807')

    def test_parse_interface(self):
        in_parse(["DateMinuteStep", "--dm", "2013-02-01T1842"],
                 lambda step: self.assertEqual(step.dm, datetime.datetime(2013, 2, 1, 18, 42, 0)))

    def test_serialize_step(self):
        t = DateMinuteStep(datetime.datetime(2013, 2, 1, 18, 42, 0))
        self.assertEqual(str(t), 'DateMinuteStep(dm=2013-02-01T1842)')


class DateSecondParameterTest(unittest.TestCase):
    def test_parse(self):
        ds = trun.DateSecondParameter().parse('2013-02-01T184227')
        self.assertEqual(ds, datetime.datetime(2013, 2, 1, 18, 42, 27))

    def test_serialize(self):
        ds = trun.DateSecondParameter().serialize(datetime.datetime(2013, 2, 1, 18, 42, 27))
        self.assertEqual(ds, '2013-02-01T184227')

    def test_parse_interface(self):
        in_parse(["DateSecondStep", "--ds", "2013-02-01T184227"],
                 lambda step: self.assertEqual(step.ds, datetime.datetime(2013, 2, 1, 18, 42, 27)))

    def test_serialize_step(self):
        t = DateSecondStep(datetime.datetime(2013, 2, 1, 18, 42, 27))
        self.assertEqual(str(t), 'DateSecondStep(ds=2013-02-01T184227)')


class MonthParameterTest(unittest.TestCase):
    def test_parse(self):
        m = trun.MonthParameter().parse('2015-04')
        self.assertEqual(m, datetime.date(2015, 4, 1))

    def test_construct_month_interval(self):
        m = MonthStep(trun.date_interval.Month(2015, 4))
        self.assertEqual(m.month, datetime.date(2015, 4, 1))

    def test_month_interval_default(self):
        class MonthDefaultStep(trun.step.Step):
            month = trun.MonthParameter(default=trun.date_interval.Month(2015, 4))

        m = MonthDefaultStep()
        self.assertEqual(m.month, datetime.date(2015, 4, 1))

    def test_serialize(self):
        m = trun.MonthParameter().serialize(datetime.date(2015, 4, 3))
        self.assertEqual(m, '2015-04')

    def test_parse_interface(self):
        in_parse(["MonthStep", "--month", "2015-04"],
                 lambda step: self.assertEqual(step.month, datetime.date(2015, 4, 1)))

    def test_serialize_step(self):
        step = MonthStep(datetime.date(2015, 4, 3))
        self.assertEqual(str(step), 'MonthStep(month=2015-04)')


class YearParameterTest(unittest.TestCase):
    def test_parse(self):
        year = trun.YearParameter().parse('2015')
        self.assertEqual(year, datetime.date(2015, 1, 1))

    def test_construct_year_interval(self):
        y = YearStep(trun.date_interval.Year(2015))
        self.assertEqual(y.year, datetime.date(2015, 1, 1))

    def test_year_interval_default(self):
        class YearDefaultStep(trun.step.Step):
            year = trun.YearParameter(default=trun.date_interval.Year(2015))

        m = YearDefaultStep()
        self.assertEqual(m.year, datetime.date(2015, 1, 1))

    def test_serialize(self):
        year = trun.YearParameter().serialize(datetime.date(2015, 4, 3))
        self.assertEqual(year, '2015')

    def test_parse_interface(self):
        in_parse(["YearStep", "--year", "2015"],
                 lambda step: self.assertEqual(step.year, datetime.date(2015, 1, 1)))

    def test_serialize_step(self):
        step = YearStep(datetime.date(2015, 4, 3))
        self.assertEqual(str(step), 'YearStep(year=2015)')
