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

import datetime
import fnmatch
from helpers import unittest, LuigiTestCase

import luigi
import mock
from luigi.mock import MockTarget, MockFileSystem
from luigi.tools.range import (RangeDaily, RangeDailyBase, RangeEvent,
                               RangeHourly, RangeHourlyBase,
                               RangeByMinutes, RangeByMinutesBase,
                               _constrain_glob, _get_filesystems_and_globs, RangeMonthly)


class CommonDateMinuteStep(luigi.Step):
    dh = luigi.DateMinuteParameter()

    def output(self):
        return MockTarget(self.dh.strftime('/n2000y01a05n/%Y_%m-_-%daww/21mm%H%Mdara21/ooo'))


class CommonDateHourStep(luigi.Step):
    dh = luigi.DateHourParameter()

    def output(self):
        return MockTarget(self.dh.strftime('/n2000y01a05n/%Y_%m-_-%daww/21mm%Hdara21/ooo'))


class CommonDateStep(luigi.Step):
    d = luigi.DateParameter()

    def output(self):
        return MockTarget(self.d.strftime('/n2000y01a05n/%Y_%m-_-%daww/21mm01dara21/ooo'))


class CommonMonthStep(luigi.Step):
    m = luigi.MonthParameter()

    def output(self):
        return MockTarget(self.m.strftime('/n2000y01a05n/%Y_%maww/21mm01dara21/ooo'))


step_a_paths = [
    'StepA/2014-03-20/18',
    'StepA/2014-03-20/21',
    'StepA/2014-03-20/23',
    'StepA/2014-03-21/00',
    'StepA/2014-03-21/00.attempt.1',
    'StepA/2014-03-21/00.attempt.2',
    'StepA/2014-03-21/01',
    'StepA/2014-03-21/02',
    'StepA/2014-03-21/03.attempt-temp-2014-03-21T13-22-58.165969',
    'StepA/2014-03-21/03.attempt.1',
    'StepA/2014-03-21/03.attempt.2',
    'StepA/2014-03-21/03.attempt.3',
    'StepA/2014-03-21/03.attempt.latest',
    'StepA/2014-03-21/04.attempt-temp-2014-03-21T13-23-09.078249',
    'StepA/2014-03-21/12',
    'StepA/2014-03-23/12',
]

step_b_paths = [
    'StepB/no/worries2014-03-20/23',
    'StepB/no/worries2014-03-21/01',
    'StepB/no/worries2014-03-21/03',
    'StepB/no/worries2014-03-21/04.attempt-yadayada',
    'StepB/no/worries2014-03-21/05',
]

mock_contents = step_a_paths + step_b_paths


expected_a = [
    'StepA(dh=2014-03-20T17)',
    'StepA(dh=2014-03-20T19)',
    'StepA(dh=2014-03-20T20)',
]

# expected_reverse = [
# ]

expected_wrapper = [
    'CommonWrapperStep(dh=2014-03-21T00)',
    'CommonWrapperStep(dh=2014-03-21T02)',
    'CommonWrapperStep(dh=2014-03-21T03)',
    'CommonWrapperStep(dh=2014-03-21T04)',
    'CommonWrapperStep(dh=2014-03-21T05)',
]


class StepA(luigi.Step):
    dh = luigi.DateHourParameter()

    def output(self):
        return MockTarget(self.dh.strftime('StepA/%Y-%m-%d/%H'))


class StepB(luigi.Step):
    dh = luigi.DateHourParameter()
    complicator = luigi.Parameter()

    def output(self):
        return MockTarget(self.dh.strftime('StepB/%%s%Y-%m-%d/%H') % self.complicator)


class StepC(luigi.Step):
    dh = luigi.DateHourParameter()

    def output(self):
        return MockTarget(self.dh.strftime('not/a/real/path/%Y-%m-%d/%H'))


class CommonWrapperStep(luigi.WrapperStep):
    dh = luigi.DateHourParameter()

    def requires(self):
        yield StepA(dh=self.dh)
        yield StepB(dh=self.dh, complicator='no/worries')  # str(self.dh) would complicate beyond working


class StepMinutesA(luigi.Step):
    dm = luigi.DateMinuteParameter()

    def output(self):
        return MockTarget(self.dm.strftime('StepA/%Y-%m-%d/%H%M'))


class StepMinutesB(luigi.Step):
    dm = luigi.DateMinuteParameter()
    complicator = luigi.Parameter()

    def output(self):
        return MockTarget(self.dm.strftime('StepB/%%s%Y-%m-%d/%H%M') % self.complicator)


class StepMinutesC(luigi.Step):
    dm = luigi.DateMinuteParameter()

    def output(self):
        return MockTarget(self.dm.strftime('not/a/real/path/%Y-%m-%d/%H%M'))


class CommonWrapperStepMinutes(luigi.WrapperStep):
    dm = luigi.DateMinuteParameter()

    def requires(self):
        yield StepMinutesA(dm=self.dm)
        yield StepMinutesB(dm=self.dm, complicator='no/worries')  # str(self.dh) would complicate beyond working


def mock_listdir(contents):
    def contents_listdir(_, glob):
        for path in fnmatch.filter(contents, glob + '*'):
            yield path

    return contents_listdir


def mock_exists_always_true(_, _2):
    yield True


def mock_exists_always_false(_, _2):
    yield False


class ConstrainGlobTest(unittest.TestCase):

    def test_limit(self):
        glob = '/[0-9][0-9][0-9][0-9]/[0-9][0-9]/[0-9][0-9]/[0-9][0-9]'
        paths = [(datetime.datetime(2013, 12, 31, 5) + datetime.timedelta(hours=h)).strftime('/%Y/%m/%d/%H') for h in range(40)]
        self.assertEqual(sorted(_constrain_glob(glob, paths)), [
            '/2013/12/31/[0-2][0-9]',
            '/2014/01/01/[0-2][0-9]',
        ])
        paths.pop(26)
        self.assertEqual(sorted(_constrain_glob(glob, paths, 6)), [
            '/2013/12/31/0[5-9]',
            '/2013/12/31/1[0-9]',
            '/2013/12/31/2[0-3]',
            '/2014/01/01/0[012345689]',
            '/2014/01/01/1[0-9]',
            '/2014/01/01/2[0]',
        ])
        self.assertEqual(sorted(_constrain_glob(glob, paths[:7], 10)), [
            '/2013/12/31/05',
            '/2013/12/31/06',
            '/2013/12/31/07',
            '/2013/12/31/08',
            '/2013/12/31/09',
            '/2013/12/31/10',
            '/2013/12/31/11',
        ])

    def test_no_wildcards(self):
        glob = '/2014/01'
        paths = '/2014/01'
        self.assertEqual(_constrain_glob(glob, paths), [
            '/2014/01',
        ])


def datetime_to_epoch(dt):
    td = dt - datetime.datetime(1970, 1, 1)
    return td.days * 86400 + td.seconds + td.microseconds / 1E6


class RangeDailyBaseTest(unittest.TestCase):
    maxDiff = None

    def setUp(self):
        # yucky to create separate callbacks; would be nicer if the callback
        # received an instance of a subclass of Event, so one callback could
        # accumulate all types
        @RangeDailyBase.event_handler(RangeEvent.DELAY)
        def callback_delay(*args):
            self.events.setdefault(RangeEvent.DELAY, []).append(args)

        @RangeDailyBase.event_handler(RangeEvent.COMPLETE_COUNT)
        def callback_complete_count(*args):
            self.events.setdefault(RangeEvent.COMPLETE_COUNT, []).append(args)

        @RangeDailyBase.event_handler(RangeEvent.COMPLETE_FRACTION)
        def callback_complete_fraction(*args):
            self.events.setdefault(RangeEvent.COMPLETE_FRACTION, []).append(args)

        self.events = {}

    def test_consistent_formatting(self):
        step = RangeDailyBase(of=CommonDateStep,
                              start=datetime.date(2016, 1, 1))
        self.assertEqual(step._format_range([datetime.datetime(2016, 1, 2, 13), datetime.datetime(2016, 2, 29, 23)]), '[2016-01-02, 2016-02-29]')

    def _empty_subcase(self, kwargs, expected_events):
        calls = []

        class RangeDailyDerived(RangeDailyBase):
            def missing_datetimes(self, step_cls, finite_datetimes):
                args = [self, step_cls, finite_datetimes]
                calls.append(args)
                return args[-1][:5]

        step = RangeDailyDerived(of=CommonDateStep,
                                 **kwargs)
        self.assertEqual(step.requires(), [])
        self.assertEqual(calls, [])
        self.assertEqual(step.requires(), [])
        self.assertEqual(calls, [])  # subsequent requires() should return the cached result, never call missing_datetimes
        self.assertEqual(self.events, expected_events)
        self.assertTrue(step.complete())

    def test_stop_before_days_back(self):
        # nothing to do because stop is earlier
        self._empty_subcase(
            {
                'now': datetime_to_epoch(datetime.datetime(2015, 1, 1, 4)),
                'stop': datetime.date(2014, 3, 20),
                'days_back': 4,
                'days_forward': 20,
                'reverse': True,
            },
            {
                'event.tools.range.delay': [
                    ('CommonDateStep', 0),
                ],
                'event.tools.range.complete.count': [
                    ('CommonDateStep', 0),
                ],
                'event.tools.range.complete.fraction': [
                    ('CommonDateStep', 1.),
                ],
            }
        )

    def _nonempty_subcase(self, kwargs, expected_finite_datetimes_range, expected_requires, expected_events):
        calls = []

        class RangeDailyDerived(RangeDailyBase):
            def missing_datetimes(self, finite_datetimes):
                # I only changed tests for number of arguments at this one
                # place to test both old and new behavior
                calls.append((self, finite_datetimes))
                return finite_datetimes[:7]

        step = RangeDailyDerived(of=CommonDateStep,
                                 **kwargs)
        self.assertEqual(list(map(str, step.requires())), expected_requires)
        self.assertEqual((min(calls[0][1]), max(calls[0][1])), expected_finite_datetimes_range)
        self.assertEqual(list(map(str, step.requires())), expected_requires)
        self.assertEqual(len(calls), 1)  # subsequent requires() should return the cached result, not call missing_datetimes again
        self.assertEqual(self.events, expected_events)
        self.assertFalse(step.complete())

    def test_start_long_before_long_days_back_and_with_long_days_forward(self):
        self._nonempty_subcase(
            {
                'now': datetime_to_epoch(datetime.datetime(2017, 10, 22, 12, 4, 29)),
                'start': datetime.date(2011, 3, 20),
                'stop': datetime.date(2025, 1, 29),
                'step_limit': 4,
                'days_back': 3 * 365,
                'days_forward': 3 * 365,
            },
            (datetime.datetime(2014, 10, 24), datetime.datetime(2020, 10, 21)),
            [
                'CommonDateStep(d=2014-10-24)',
                'CommonDateStep(d=2014-10-25)',
                'CommonDateStep(d=2014-10-26)',
                'CommonDateStep(d=2014-10-27)',
            ],
            {
                'event.tools.range.delay': [
                    ('CommonDateStep', 3750),
                ],
                'event.tools.range.complete.count': [
                    ('CommonDateStep', 5057),
                ],
                'event.tools.range.complete.fraction': [
                    ('CommonDateStep', 5057. / (5057 + 7)),
                ],
            }
        )


class RangeHourlyBaseTest(unittest.TestCase):
    maxDiff = None

    def setUp(self):
        # yucky to create separate callbacks; would be nicer if the callback
        # received an instance of a subclass of Event, so one callback could
        # accumulate all types
        @RangeHourlyBase.event_handler(RangeEvent.DELAY)
        def callback_delay(*args):
            self.events.setdefault(RangeEvent.DELAY, []).append(args)

        @RangeHourlyBase.event_handler(RangeEvent.COMPLETE_COUNT)
        def callback_complete_count(*args):
            self.events.setdefault(RangeEvent.COMPLETE_COUNT, []).append(args)

        @RangeHourlyBase.event_handler(RangeEvent.COMPLETE_FRACTION)
        def callback_complete_fraction(*args):
            self.events.setdefault(RangeEvent.COMPLETE_FRACTION, []).append(args)

        self.events = {}

    def test_consistent_formatting(self):
        step = RangeHourlyBase(of=CommonDateHourStep,
                               start=datetime.datetime(2016, 1, 1))
        self.assertEqual(step._format_range([datetime.datetime(2016, 1, 2, 13), datetime.datetime(2016, 2, 29, 23)]), '[2016-01-02T13, 2016-02-29T23]')

    def _empty_subcase(self, kwargs, expected_events):
        calls = []

        class RangeHourlyDerived(RangeHourlyBase):
            def missing_datetimes(a, b, c):
                args = [a, b, c]
                calls.append(args)
                return args[-1][:5]

        step = RangeHourlyDerived(of=CommonDateHourStep,
                                  **kwargs)
        self.assertEqual(step.requires(), [])
        self.assertEqual(calls, [])
        self.assertEqual(step.requires(), [])
        self.assertEqual(calls, [])  # subsequent requires() should return the cached result, never call missing_datetimes
        self.assertEqual(self.events, expected_events)
        self.assertTrue(step.complete())

    def test_start_after_hours_forward(self):
        # nothing to do because start is later
        self._empty_subcase(
            {
                'now': datetime_to_epoch(datetime.datetime(2000, 1, 1, 4)),
                'start': datetime.datetime(2014, 3, 20, 17),
                'hours_back': 4,
                'hours_forward': 20,
            },
            {
                'event.tools.range.delay': [
                    ('CommonDateHourStep', 0),
                ],
                'event.tools.range.complete.count': [
                    ('CommonDateHourStep', 0),
                ],
                'event.tools.range.complete.fraction': [
                    ('CommonDateHourStep', 1.),
                ],
            }
        )

    def _nonempty_subcase(self, kwargs, expected_finite_datetimes_range, expected_requires, expected_events):
        calls = []

        class RangeHourlyDerived(RangeHourlyBase):
            def missing_datetimes(a, b, c):
                args = [a, b, c]
                calls.append(args)
                return args[-1][:7]

        step = RangeHourlyDerived(of=CommonDateHourStep,
                                  **kwargs)
        self.assertEqual(list(map(str, step.requires())), expected_requires)
        self.assertEqual(calls[0][1], CommonDateHourStep)
        self.assertEqual((min(calls[0][2]), max(calls[0][2])), expected_finite_datetimes_range)
        self.assertEqual(list(map(str, step.requires())), expected_requires)
        self.assertEqual(len(calls), 1)  # subsequent requires() should return the cached result, not call missing_datetimes again
        self.assertEqual(self.events, expected_events)
        self.assertFalse(step.complete())

    def test_start_long_before_hours_back(self):
        self._nonempty_subcase(
            {
                'now': datetime_to_epoch(datetime.datetime(2000, 1, 1, 4)),
                'start': datetime.datetime(1960, 3, 2, 1),
                'hours_back': 5,
                'hours_forward': 20,
            },
            (datetime.datetime(1999, 12, 31, 23), datetime.datetime(2000, 1, 1, 23)),
            [
                'CommonDateHourStep(dh=1999-12-31T23)',
                'CommonDateHourStep(dh=2000-01-01T00)',
                'CommonDateHourStep(dh=2000-01-01T01)',
                'CommonDateHourStep(dh=2000-01-01T02)',
                'CommonDateHourStep(dh=2000-01-01T03)',
                'CommonDateHourStep(dh=2000-01-01T04)',
                'CommonDateHourStep(dh=2000-01-01T05)',
            ],
            {
                'event.tools.range.delay': [
                    ('CommonDateHourStep', 25),  # because of short hours_back we're oblivious to those 40 preceding years
                ],
                'event.tools.range.complete.count': [
                    ('CommonDateHourStep', 349192),
                ],
                'event.tools.range.complete.fraction': [
                    ('CommonDateHourStep', 349192. / (349192 + 7)),
                ],
            }
        )

    def test_start_after_long_hours_back(self):
        self._nonempty_subcase(
            {
                'now': datetime_to_epoch(datetime.datetime(2014, 10, 22, 12, 4, 29)),
                'start': datetime.datetime(2014, 3, 20, 17),
                'step_limit': 4,
                'hours_back': 365 * 24,
            },
            (datetime.datetime(2014, 3, 20, 17), datetime.datetime(2014, 10, 22, 12)),
            [
                'CommonDateHourStep(dh=2014-03-20T17)',
                'CommonDateHourStep(dh=2014-03-20T18)',
                'CommonDateHourStep(dh=2014-03-20T19)',
                'CommonDateHourStep(dh=2014-03-20T20)',
            ],
            {
                'event.tools.range.delay': [
                    ('CommonDateHourStep', 5180),
                ],
                'event.tools.range.complete.count': [
                    ('CommonDateHourStep', 5173),
                ],
                'event.tools.range.complete.fraction': [
                    ('CommonDateHourStep', 5173. / (5173 + 7)),
                ],
            }
        )

    def test_start_long_before_long_hours_back_and_with_long_hours_forward(self):
        self._nonempty_subcase(
            {
                'now': datetime_to_epoch(datetime.datetime(2017, 10, 22, 12, 4, 29)),
                'start': datetime.datetime(2011, 3, 20, 17),
                'step_limit': 4,
                'hours_back': 3 * 365 * 24,
                'hours_forward': 3 * 365 * 24,
            },
            (datetime.datetime(2014, 10, 23, 13), datetime.datetime(2020, 10, 21, 12)),
            [
                'CommonDateHourStep(dh=2014-10-23T13)',
                'CommonDateHourStep(dh=2014-10-23T14)',
                'CommonDateHourStep(dh=2014-10-23T15)',
                'CommonDateHourStep(dh=2014-10-23T16)',
            ],
            {
                'event.tools.range.delay': [
                    ('CommonDateHourStep', 52560),
                ],
                'event.tools.range.complete.count': [
                    ('CommonDateHourStep', 84061),
                ],
                'event.tools.range.complete.fraction': [
                    ('CommonDateHourStep', 84061. / (84061 + 7)),
                ],
            }
        )


class RangeByMinutesBaseTest(unittest.TestCase):
    maxDiff = None

    def setUp(self):
        # yucky to create separate callbacks; would be nicer if the callback
        # received an instance of a subclass of Event, so one callback could
        # accumulate all types
        @RangeByMinutesBase.event_handler(RangeEvent.DELAY)
        def callback_delay(*args):
            self.events.setdefault(RangeEvent.DELAY, []).append(args)

        @RangeByMinutesBase.event_handler(RangeEvent.COMPLETE_COUNT)
        def callback_complete_count(*args):
            self.events.setdefault(RangeEvent.COMPLETE_COUNT, []).append(args)

        @RangeByMinutesBase.event_handler(RangeEvent.COMPLETE_FRACTION)
        def callback_complete_fraction(*args):
            self.events.setdefault(RangeEvent.COMPLETE_FRACTION, []).append(args)

        self.events = {}

    def test_consistent_formatting(self):
        step = RangeByMinutesBase(of=CommonDateMinuteStep,
                                  start=datetime.datetime(2016, 1, 1, 13),
                                  minutes_interval=5)
        self.assertEqual(step._format_range(
            [datetime.datetime(2016, 1, 2, 13, 10), datetime.datetime(2016, 2, 29, 23, 20)]),
            '[2016-01-02T1310, 2016-02-29T2320]')

    def _empty_subcase(self, kwargs, expected_events):
        calls = []

        class RangeByMinutesDerived(RangeByMinutesBase):
            def missing_datetimes(a, b, c):
                args = [a, b, c]
                calls.append(args)
                return args[-1][:5]

        step = RangeByMinutesDerived(of=CommonDateMinuteStep, **kwargs)
        self.assertEqual(step.requires(), [])
        self.assertEqual(calls, [])
        self.assertEqual(step.requires(), [])
        self.assertEqual(calls, [])  # subsequent requires() should return the cached result, never call missing_datetimes
        self.assertEqual(self.events, expected_events)
        self.assertTrue(step.complete())

    def test_start_after_minutes_forward(self):
        # nothing to do because start is later
        self._empty_subcase(
            {
                'now': datetime_to_epoch(datetime.datetime(2000, 1, 1, 4)),
                'start': datetime.datetime(2014, 3, 20, 17, 10),
                'minutes_back': 4,
                'minutes_forward': 20,
                'minutes_interval': 5,
            },
            {
                'event.tools.range.delay': [
                    ('CommonDateMinuteStep', 0),
                ],
                'event.tools.range.complete.count': [
                    ('CommonDateMinuteStep', 0),
                ],
                'event.tools.range.complete.fraction': [
                    ('CommonDateMinuteStep', 1.),
                ],
            }
        )

    def _nonempty_subcase(self, kwargs, expected_finite_datetimes_range, expected_requires, expected_events):
        calls = []

        class RangeByMinutesDerived(RangeByMinutesBase):
            def missing_datetimes(a, b, c):
                args = [a, b, c]
                calls.append(args)
                return args[-1][:7]

        step = RangeByMinutesDerived(of=CommonDateMinuteStep, **kwargs)
        self.assertEqual(list(map(str, step.requires())), expected_requires)
        self.assertEqual(calls[0][1], CommonDateMinuteStep)
        self.assertEqual((min(calls[0][2]), max(calls[0][2])), expected_finite_datetimes_range)
        self.assertEqual(list(map(str, step.requires())), expected_requires)
        self.assertEqual(len(calls), 1)  # subsequent requires() should return the cached result, not call missing_datetimes again
        self.assertEqual(self.events, expected_events)
        self.assertFalse(step.complete())

    def test_negative_interval(self):
        class SomeByMinutesStep(luigi.Step):
            d = luigi.DateMinuteParameter()

            def output(self):
                return MockTarget(self.d.strftime('/data/2014/p/v/z/%Y_/_%m-_-%doctor/20/%HZ%MOOO'))

        step = RangeByMinutes(now=datetime_to_epoch(datetime.datetime(2016, 4, 1)),
                              of=SomeByMinutesStep,
                              start=datetime.datetime(2014, 3, 20, 17),
                              minutes_interval=-1)
        self.assertRaises(luigi.parameter.ParameterException, step.requires)

    def test_non_dividing_interval(self):
        class SomeByMinutesStep(luigi.Step):
            d = luigi.DateMinuteParameter()

            def output(self):
                return MockTarget(self.d.strftime('/data/2014/p/v/z/%Y_/_%m-_-%doctor/20/%HZ%MOOO'))

        step = RangeByMinutes(now=datetime_to_epoch(datetime.datetime(2016, 4, 1)),
                              of=SomeByMinutesStep,
                              start=datetime.datetime(2014, 3, 20, 17),
                              minutes_interval=8)
        self.assertRaises(luigi.parameter.ParameterException, step.requires)

    def test_start_and_minutes_period(self):
        self._nonempty_subcase(
            {
                'now': datetime_to_epoch(datetime.datetime(2016, 9, 1, 12, 0, 0)),
                'start': datetime.datetime(2016, 9, 1, 11, 0, 0),
                'minutes_back': 24 * 60,
                'minutes_forward': 0,
                'minutes_interval': 3,
            },
            (datetime.datetime(2016, 9, 1, 11, 0), datetime.datetime(2016, 9, 1, 11, 57, 0)),
            [
                'CommonDateMinuteStep(dh=2016-09-01T1100)',
                'CommonDateMinuteStep(dh=2016-09-01T1103)',
                'CommonDateMinuteStep(dh=2016-09-01T1106)',
                'CommonDateMinuteStep(dh=2016-09-01T1109)',
                'CommonDateMinuteStep(dh=2016-09-01T1112)',
                'CommonDateMinuteStep(dh=2016-09-01T1115)',
                'CommonDateMinuteStep(dh=2016-09-01T1118)',
            ],
            {
                'event.tools.range.delay': [
                    ('CommonDateMinuteStep', 20),  # First missing is the 20th
                ],
                'event.tools.range.complete.count': [
                    ('CommonDateMinuteStep', 13),  # 20 intervals - 7 missing
                ],
                'event.tools.range.complete.fraction': [
                    ('CommonDateMinuteStep', 13. / (13 + 7)),  # (expected - missing) / expected
                ],
            }
        )

    def test_start_long_before_minutes_back(self):
        self._nonempty_subcase(
            {
                'now': datetime_to_epoch(datetime.datetime(2000, 1, 1, 0, 3, 0)),
                'start': datetime.datetime(1960, 1, 1, 0, 0, 0),
                'minutes_back': 5,
                'minutes_forward': 20,
                'minutes_interval': 5,
            },
            (datetime.datetime(2000, 1, 1, 0, 0), datetime.datetime(2000, 1, 1, 0, 20, 0)),
            [
                'CommonDateMinuteStep(dh=2000-01-01T0000)',
                'CommonDateMinuteStep(dh=2000-01-01T0005)',
                'CommonDateMinuteStep(dh=2000-01-01T0010)',
                'CommonDateMinuteStep(dh=2000-01-01T0015)',
                'CommonDateMinuteStep(dh=2000-01-01T0020)',
            ],
            {
                'event.tools.range.delay': [
                    ('CommonDateMinuteStep', 5),  # because of short minutes_back we're oblivious to those 40 preceding years
                ],
                'event.tools.range.complete.count': [
                    ('CommonDateMinuteStep', 4207680),  # expected intervals - missing.
                ],
                'event.tools.range.complete.fraction': [
                    ('CommonDateMinuteStep', 4207680. / 4207685),  # (expected - missing) / expected
                ],
            }
        )

    def test_start_after_long_minutes_back(self):
        self._nonempty_subcase(
            {
                'now': datetime_to_epoch(datetime.datetime(2014, 3, 20, 18, 4, 29)),
                'start': datetime.datetime(2014, 3, 20, 17, 10),
                'step_limit': 4,
                'minutes_back': 365 * 24 * 60,
                'minutes_interval': 5,
            },
            (datetime.datetime(2014, 3, 20, 17, 10, 0), datetime.datetime(2014, 3, 20, 18, 0, 0)),
            [
                'CommonDateMinuteStep(dh=2014-03-20T1710)',
                'CommonDateMinuteStep(dh=2014-03-20T1715)',
                'CommonDateMinuteStep(dh=2014-03-20T1720)',
                'CommonDateMinuteStep(dh=2014-03-20T1725)',
            ],
            {
                'event.tools.range.delay': [
                    ('CommonDateMinuteStep', 11),
                ],
                'event.tools.range.complete.count': [
                    ('CommonDateMinuteStep', 4),
                ],
                'event.tools.range.complete.fraction': [
                    ('CommonDateMinuteStep', 4. / 11),
                ],
            }
        )

    def test_start_long_before_long_minutes_back_and_with_long_minutes_forward(self):
        self._nonempty_subcase(
            {
                'now': datetime_to_epoch(datetime.datetime(2017, 3, 22, 20, 4, 29)),
                'start': datetime.datetime(2011, 3, 20, 17, 10, 0),
                'step_limit': 4,
                'minutes_back': 365 * 24 * 60,
                'minutes_forward': 365 * 24 * 60,
                'minutes_interval': 5,
            },
            (datetime.datetime(2016, 3, 22, 20, 5), datetime.datetime(2018, 3, 22, 20, 0)),
            [
                'CommonDateMinuteStep(dh=2016-03-22T2005)',
                'CommonDateMinuteStep(dh=2016-03-22T2010)',
                'CommonDateMinuteStep(dh=2016-03-22T2015)',
                'CommonDateMinuteStep(dh=2016-03-22T2020)',
            ],
            {
                'event.tools.range.delay': [
                    ('CommonDateMinuteStep', 210240),
                ],
                'event.tools.range.complete.count': [
                    ('CommonDateMinuteStep', 737020),
                ],
                'event.tools.range.complete.fraction': [
                    ('CommonDateMinuteStep', 737020. / (737020 + 7)),
                ],
            }
        )


class FilesystemInferenceTest(unittest.TestCase):

    def _test_filesystems_and_globs(self, datetime_to_step, datetime_to_re, expected):
        actual = list(_get_filesystems_and_globs(datetime_to_step, datetime_to_re))
        self.assertEqual(len(actual), len(expected))
        for (actual_filesystem, actual_glob), (expected_filesystem, expected_glob) in zip(actual, expected):
            self.assertTrue(isinstance(actual_filesystem, expected_filesystem))
            self.assertEqual(actual_glob, expected_glob)

    def test_date_glob_successfully_inferred(self):
        self._test_filesystems_and_globs(
            lambda d: CommonDateStep(d),
            lambda d: d.strftime('(%Y).*(%m).*(%d)'),
            [
                (MockFileSystem, '/n2000y01a05n/[0-9][0-9][0-9][0-9]_[0-9][0-9]-_-[0-9][0-9]aww/21mm01dara21'),
            ]
        )

    def test_datehour_glob_successfully_inferred(self):
        self._test_filesystems_and_globs(
            lambda d: CommonDateHourStep(d),
            lambda d: d.strftime('(%Y).*(%m).*(%d).*(%H)'),
            [
                (MockFileSystem, '/n2000y01a05n/[0-9][0-9][0-9][0-9]_[0-9][0-9]-_-[0-9][0-9]aww/21mm[0-9][0-9]dara21'),
            ]
        )

    def test_dateminute_glob_successfully_inferred(self):
        self._test_filesystems_and_globs(
            lambda d: CommonDateMinuteStep(d),
            lambda d: d.strftime('(%Y).*(%m).*(%d).*(%H).*(%M)'),
            [
                (MockFileSystem, '/n2000y01a05n/[0-9][0-9][0-9][0-9]_[0-9][0-9]-_-[0-9][0-9]aww/21mm[0-9][0-9][0-9][0-9]dara21'),
            ]
        )

    def test_wrapped_datehour_globs_successfully_inferred(self):
        self._test_filesystems_and_globs(
            lambda d: CommonWrapperStep(d),
            lambda d: d.strftime('(%Y).*(%m).*(%d).*(%H)'),
            [
                (MockFileSystem, 'StepA/[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'),
                (MockFileSystem, 'StepB/no/worries[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'),
            ]
        )

    def test_inconsistent_output_datehour_glob_not_inferred(self):
        class InconsistentlyOutputtingDateHourStep(luigi.Step):
            dh = luigi.DateHourParameter()

            def output(self):
                base = self.dh.strftime('/even/%Y%m%d%H')
                if self.dh.hour % 2 == 0:
                    return MockTarget(base)
                else:
                    return {
                        'spi': MockTarget(base + '/something.spi'),
                        'spl': MockTarget(base + '/something.spl'),
                    }

        def test_raise_not_implemented():
            list(_get_filesystems_and_globs(
                lambda d: InconsistentlyOutputtingDateHourStep(d),
                lambda d: d.strftime('(%Y).*(%m).*(%d).*(%H)')))

        self.assertRaises(NotImplementedError, test_raise_not_implemented)

    def test_wrapped_inconsistent_datehour_globs_not_inferred(self):
        class InconsistentlyParameterizedWrapperStep(luigi.WrapperStep):
            dh = luigi.DateHourParameter()

            def requires(self):
                yield StepA(dh=self.dh - datetime.timedelta(days=1))
                yield StepB(dh=self.dh, complicator='no/worries')

        def test_raise_not_implemented():
            list(_get_filesystems_and_globs(
                lambda d: InconsistentlyParameterizedWrapperStep(d),
                lambda d: d.strftime('(%Y).*(%m).*(%d).*(%H)')))

        self.assertRaises(NotImplementedError, test_raise_not_implemented)


class RangeMonthlyTest(unittest.TestCase):

    def setUp(self):
        # yucky to create separate callbacks; would be nicer if the callback
        # received an instance of a subclass of Event, so one callback could
        # accumulate all types
        @RangeMonthly.event_handler(RangeEvent.DELAY)
        def callback_delay(*args):
            self.events.setdefault(RangeEvent.DELAY, []).append(args)

        @RangeMonthly.event_handler(RangeEvent.COMPLETE_COUNT)
        def callback_complete_count(*args):
            self.events.setdefault(RangeEvent.COMPLETE_COUNT, []).append(args)

        @RangeMonthly.event_handler(RangeEvent.COMPLETE_FRACTION)
        def callback_complete_fraction(*args):
            self.events.setdefault(RangeEvent.COMPLETE_FRACTION, []).append(args)

        self.events = {}

    def _empty_subcase(self, kwargs, expected_events):
        calls = []

        class RangeMonthlyDerived(RangeMonthly):
            def missing_datetimes(self, step_cls, finite_datetimes):
                args = [self, step_cls, finite_datetimes]
                calls.append(args)
                return args[-1][:5]

        step = RangeMonthlyDerived(of=CommonMonthStep, **kwargs)
        self.assertEqual(step.requires(), [])
        self.assertEqual(calls, [])
        self.assertEqual(step.requires(), [])
        self.assertEqual(calls, [])  # subsequent requires() should return the cached result, never call missing_datetimes
        self.assertEqual(self.events, expected_events)
        self.assertTrue(step.complete())

    def test_stop_before_months_back(self):
        # nothing to do because stop is earlier
        self._empty_subcase(
            {
                'now': datetime_to_epoch(datetime.datetime(2017, 1, 3)),
                'stop': datetime.date(2016, 3, 20),
                'months_back': 4,
                'months_forward': 20,
                'reverse': True,
            },
            {
                'event.tools.range.delay': [
                    ('CommonMonthStep', 0),
                ],
                'event.tools.range.complete.count': [
                    ('CommonMonthStep', 0),
                ],
                'event.tools.range.complete.fraction': [
                    ('CommonMonthStep', 1.),
                ],
            }
        )

    def test_start_after_months_forward(self):
        # nothing to do because start is later
        self._empty_subcase(
            {
                'now': datetime_to_epoch(datetime.datetime(2000, 1, 1)),
                'start': datetime.datetime(2014, 3, 20),
                'months_back': 4,
                'months_forward': 20,
            },
            {
                'event.tools.range.delay': [
                    ('CommonMonthStep', 0),
                ],
                'event.tools.range.complete.count': [
                    ('CommonMonthStep', 0),
                ],
                'event.tools.range.complete.fraction': [
                    ('CommonMonthStep', 1.),
                ],
            }
        )

    def _nonempty_subcase(self, kwargs, expected_finite_datetimes_range, expected_requires, expected_events):
        calls = []

        class RangeDailyDerived(RangeMonthly):
            def missing_datetimes(self, finite_datetimes):
                calls.append((self, finite_datetimes))
                return finite_datetimes[:7]

        step = RangeDailyDerived(of=CommonMonthStep, **kwargs)
        self.assertEqual(list(map(str, step.requires())), expected_requires)
        self.assertEqual((min(calls[0][1]), max(calls[0][1])), expected_finite_datetimes_range)
        self.assertEqual(list(map(str, step.requires())), expected_requires)
        self.assertEqual(len(calls), 1)  # subsequent requires() should return the cached result, not call missing_datetimes again
        self.assertEqual(self.events, expected_events)
        self.assertFalse(step.complete())

    def test_start_long_before_months_back(self):
        total = (2000 - 1960) * 12 + 20 - 2
        self._nonempty_subcase(
            {
                'now': datetime_to_epoch(datetime.datetime(2000, 1, 1)),
                'start': datetime.datetime(1960, 3, 2, 1),
                'months_back': 5,
                'months_forward': 20,
            },
            (datetime.datetime(1999, 8, 1), datetime.datetime(2001, 8, 1)),
            [
                'CommonMonthStep(m=1999-08)',
                'CommonMonthStep(m=1999-09)',
                'CommonMonthStep(m=1999-10)',
                'CommonMonthStep(m=1999-11)',
                'CommonMonthStep(m=1999-12)',
                'CommonMonthStep(m=2000-01)',
                'CommonMonthStep(m=2000-02)',
            ],
            {
                'event.tools.range.delay': [
                    ('CommonMonthStep', 25),
                ],
                'event.tools.range.complete.count': [
                    ('CommonMonthStep', total - 7),
                ],
                'event.tools.range.complete.fraction': [
                    ('CommonMonthStep', (total - 7.0) / total),
                ],
            }
        )

    def test_start_after_long_months_back(self):
        total = 12 - 4
        self._nonempty_subcase(
            {
                'now': datetime_to_epoch(datetime.datetime(2014, 11, 22)),
                'start': datetime.datetime(2014, 3, 1),
                'step_limit': 4,
                'months_back': 12 * 24,
            },
            (datetime.datetime(2014, 3, 1), datetime.datetime(2014, 10, 1)),
            [
                'CommonMonthStep(m=2014-03)',
                'CommonMonthStep(m=2014-04)',
                'CommonMonthStep(m=2014-05)',
                'CommonMonthStep(m=2014-06)',
            ],
            {
                'event.tools.range.delay': [
                    ('CommonMonthStep', total),
                ],
                'event.tools.range.complete.count': [
                    ('CommonMonthStep', total - 7),
                ],
                'event.tools.range.complete.fraction': [
                    ('CommonMonthStep', (total - 7.0) / total),
                ],
            }
        )

    def test_start_long_before_long_months_back_and_with_long_months_forward(self):
        total = (2025 - 2011) * 12 - 2
        self._nonempty_subcase(
            {
                'now': datetime_to_epoch(datetime.datetime(2017, 10, 22, 12, 4, 29)),
                'start': datetime.date(2011, 3, 20),
                'stop': datetime.date(2025, 1, 29),
                'step_limit': 4,
                'months_back': 3 * 12,
                'months_forward': 3 * 12,
            },
            (datetime.datetime(2014, 10, 1), datetime.datetime(2020, 9, 1)),
            [
                'CommonMonthStep(m=2014-10)',
                'CommonMonthStep(m=2014-11)',
                'CommonMonthStep(m=2014-12)',
                'CommonMonthStep(m=2015-01)',
            ],
            {
                'event.tools.range.delay': [
                    ('CommonMonthStep', (2025 - (2017 - 3)) * 12 - 9),
                ],
                'event.tools.range.complete.count': [
                    ('CommonMonthStep', total - 7),
                ],
                'event.tools.range.complete.fraction': [
                    ('CommonMonthStep', (total - 7.0) / total),
                ],
            }
        )

    def test_zero_months_forward(self):
        total = (2017 - 2011) * 12
        self._nonempty_subcase(
            {
                'now': datetime_to_epoch(datetime.datetime(2017, 10, 31, 12, 4, 29)),
                'start': datetime.date(2011, 10, 1),
                'step_limit': 10,
                'months_back': 4,
            },
            (datetime.datetime(2017, 6, 1), datetime.datetime(2017, 9, 1)),
            [
                'CommonMonthStep(m=2017-06)',
                'CommonMonthStep(m=2017-07)',
                'CommonMonthStep(m=2017-08)',
                'CommonMonthStep(m=2017-09)',
            ],
            {
                'event.tools.range.delay': [
                    ('CommonMonthStep', 4),
                ],
                'event.tools.range.complete.count': [
                    ('CommonMonthStep', total - 4),
                ],
                'event.tools.range.complete.fraction': [
                    ('CommonMonthStep', (total - 4.0) / total),
                ],
            }
        )

    def test_months_forward_on_first_of_month(self):
        total = (2017 - 2011) * 12 + 2
        self._nonempty_subcase(
            {
                'now': datetime_to_epoch(datetime.datetime(2017, 10, 1, 12, 4, 29)),
                'start': datetime.date(2011, 10, 1),
                'step_limit': 10,
                'months_back': 4,
                'months_forward': 2
            },
            (datetime.datetime(2017, 6, 1), datetime.datetime(2017, 11, 1)),
            [
                'CommonMonthStep(m=2017-06)',
                'CommonMonthStep(m=2017-07)',
                'CommonMonthStep(m=2017-08)',
                'CommonMonthStep(m=2017-09)',
                'CommonMonthStep(m=2017-10)',
                'CommonMonthStep(m=2017-11)',
            ],
            {
                'event.tools.range.delay': [
                    ('CommonMonthStep', 6),
                ],
                'event.tools.range.complete.count': [
                    ('CommonMonthStep', total - 6),
                ],
                'event.tools.range.complete.fraction': [
                    ('CommonMonthStep', (total - 6.0) / total),
                ],
            }
        )

    def test_consistent_formatting(self):
        step = RangeMonthly(of=CommonMonthStep,
                            start=datetime.date(2018, 1, 4))
        self.assertEqual(step._format_range([datetime.datetime(2018, 2, 3, 14), datetime.datetime(2018, 4, 5, 21)]),
                         '[2018-02, 2018-04]')


class MonthInstantiationTest(LuigiTestCase):

    def test_old_month_instantiation(self):
        """
        Verify that you can still programmatically set of param as string
        """
        class MyStep(luigi.Step):
            month_param = luigi.MonthParameter()

            def complete(self):
                return False

        range_step = RangeMonthly(now=datetime_to_epoch(datetime.datetime(2016, 1, 1)),
                                  of=MyStep,
                                  start=datetime.date(2015, 12, 1),
                                  stop=datetime.date(2016, 1, 1))
        expected_step = MyStep(month_param=datetime.date(2015, 12, 1))
        self.assertEqual(expected_step, list(range_step._requires())[0])

    def test_month_cli_instantiation(self):
        """
        Verify that you can still use Range through CLI
        """

        class MyStep(luigi.Step):
            step_namespace = "wohoo"
            month_param = luigi.MonthParameter()
            secret = 'some-value-to-sooth-python-linters'
            comp = False

            def complete(self):
                return self.comp

            def run(self):
                self.comp = True
                MyStep.secret = 'yay'

        now = str(int(datetime_to_epoch(datetime.datetime(2016, 1, 1))))
        self.run_locally_split('RangeMonthly --of wohoo.MyStep --now {now} --start 2015-12 --stop 2016-01'.format(now=now))
        self.assertEqual(MyStep(month_param=datetime.date(1934, 12, 1)).secret, 'yay')

    def test_param_name(self):
        class MyStep(luigi.Step):
            some_non_range_param = luigi.Parameter(default='woo')
            month_param = luigi.MonthParameter()

            def complete(self):
                return False

        range_step = RangeMonthly(now=datetime_to_epoch(datetime.datetime(2016, 1, 1)),
                                  of=MyStep,
                                  start=datetime.date(2015, 12, 1),
                                  stop=datetime.date(2016, 1, 1),
                                  param_name='month_param')
        expected_step = MyStep('woo', datetime.date(2015, 12, 1))
        self.assertEqual(expected_step, list(range_step._requires())[0])

    def test_param_name_with_inferred_fs(self):
        class MyStep(luigi.Step):
            some_non_range_param = luigi.Parameter(default='woo')
            month_param = luigi.MonthParameter()

            def output(self):
                return MockTarget(self.month_param.strftime('/n2000y01a05n/%Y_%m-aww/21mm%Hdara21/ooo'))

        range_step = RangeMonthly(now=datetime_to_epoch(datetime.datetime(2016, 1, 1)),
                                  of=MyStep,
                                  start=datetime.date(2015, 12, 1),
                                  stop=datetime.date(2016, 1, 1),
                                  param_name='month_param')
        expected_step = MyStep('woo', datetime.date(2015, 12, 1))
        self.assertEqual(expected_step, list(range_step._requires())[0])

    def test_of_param_distinction(self):
        class MyStep(luigi.Step):
            arbitrary_param = luigi.Parameter(default='foo')
            arbitrary_integer_param = luigi.IntParameter(default=10)
            month_param = luigi.MonthParameter()

            def complete(self):
                return False

        range_step_1 = RangeMonthly(now=datetime_to_epoch(datetime.datetime(2015, 12, 2)),
                                    of=MyStep,
                                    start=datetime.date(2015, 12, 1),
                                    stop=datetime.date(2016, 1, 1))
        range_step_2 = RangeMonthly(now=datetime_to_epoch(datetime.datetime(2015, 12, 2)),
                                    of=MyStep,
                                    of_params=dict(arbitrary_param="bar", abitrary_integer_param=2),
                                    start=datetime.date(2015, 12, 1),
                                    stop=datetime.date(2016, 1, 1))
        self.assertNotEqual(range_step_1.step_id, range_step_2.step_id)

    def test_of_param_commandline(self):
        class MyStep(luigi.Step):
            step_namespace = "wohoo"
            month_param = luigi.MonthParameter()
            arbitrary_param = luigi.Parameter(default='foo')
            arbitrary_integer_param = luigi.IntParameter(default=10)
            state = (None, None)
            comp = False

            def complete(self):
                return self.comp

            def run(self):
                self.comp = True
                MyStep.state = (self.arbitrary_param, self.arbitrary_integer_param)

        now = str(int(datetime_to_epoch(datetime.datetime(2016, 1, 1))))
        self.run_locally(['RangeMonthly', '--of', 'wohoo.MyStep',
                          '--of-params', '{"arbitrary_param":"bar","arbitrary_integer_param":5}',
                          '--now', '{0}'.format(now), '--start', '2015-12', '--stop', '2016-01'])
        self.assertEqual(MyStep.state, ('bar', 5))


class RangeDailyTest(unittest.TestCase):

    def test_bulk_complete_correctly_interfaced(self):
        class BulkCompleteDailyStep(luigi.Step):
            d = luigi.DateParameter()

            @classmethod
            def bulk_complete(self, parameter_tuples):
                return list(parameter_tuples)[:-2]

            def output(self):
                raise RuntimeError("Shouldn't get called while resolving deps via bulk_complete")

        step = RangeDaily(now=datetime_to_epoch(datetime.datetime(2015, 12, 1)),
                          of=BulkCompleteDailyStep,
                          start=datetime.date(2015, 11, 1),
                          stop=datetime.date(2015, 12, 1))

        expected = [
            'BulkCompleteDailyStep(d=2015-11-29)',
            'BulkCompleteDailyStep(d=2015-11-30)',
        ]

        actual = [str(t) for t in step.requires()]
        self.assertEqual(actual, expected)

    def test_bulk_complete_of_params(self):
        class BulkCompleteDailyStep(luigi.Step):
            non_positional_arbitrary_argument = luigi.Parameter(default="whatever", positional=False, significant=False)
            d = luigi.DateParameter()
            arbitrary_argument = luigi.BoolParameter()

            @classmethod
            def bulk_complete(cls, parameter_tuples):
                ptuples = list(parameter_tuples)
                for t in map(cls, ptuples):
                    assert t.arbitrary_argument
                return ptuples[:-2]

            def output(self):
                raise RuntimeError("Shouldn't get called while resolving deps via bulk_complete")

        step = RangeDaily(now=datetime_to_epoch(datetime.datetime(2015, 12, 1)),
                          of=BulkCompleteDailyStep,
                          of_params=dict(arbitrary_argument=True),
                          start=datetime.date(2015, 11, 1),
                          stop=datetime.date(2015, 12, 1))
        expected = [
            'BulkCompleteDailyStep(d=2015-11-29, arbitrary_argument=True)',
            'BulkCompleteDailyStep(d=2015-11-30, arbitrary_argument=True)',
        ]

        actual = [str(t) for t in step.requires()]
        self.assertEqual(actual, expected)

    @mock.patch('luigi.mock.MockFileSystem.listdir',
                new=mock_listdir([
                    '/data/2014/p/v/z/2014_/_03-_-21octor/20/ZOOO',
                    '/data/2014/p/v/z/2014_/_03-_-23octor/20/ZOOO',
                    '/data/2014/p/v/z/2014_/_03-_-24octor/20/ZOOO',
                ]))
    @mock.patch('luigi.mock.MockFileSystem.exists',
                new=mock_exists_always_true)
    def test_missing_steps_correctly_required(self):
        class SomeDailyStep(luigi.Step):
            d = luigi.DateParameter()

            def output(self):
                return MockTarget(self.d.strftime('/data/2014/p/v/z/%Y_/_%m-_-%doctor/20/ZOOO'))

        step = RangeDaily(now=datetime_to_epoch(datetime.datetime(2016, 4, 1)),
                          of=SomeDailyStep,
                          start=datetime.date(2014, 3, 20),
                          step_limit=3,
                          days_back=3 * 365)
        expected = [
            'SomeDailyStep(d=2014-03-20)',
            'SomeDailyStep(d=2014-03-22)',
            'SomeDailyStep(d=2014-03-25)',
        ]
        actual = [str(t) for t in step.requires()]
        self.assertEqual(actual, expected)


class RangeHourlyTest(unittest.TestCase):

    # fishy to mock the mock, but MockFileSystem doesn't support globs yet
    @mock.patch('luigi.mock.MockFileSystem.listdir', new=mock_listdir(mock_contents))
    @mock.patch('luigi.mock.MockFileSystem.exists',
                new=mock_exists_always_true)
    def test_missing_steps_correctly_required(self):
        for step_path in step_a_paths:
            MockTarget(step_path)
        # this test takes a few seconds. Since stop is not defined,
        # finite_datetimes constitute many years to consider
        step = RangeHourly(now=datetime_to_epoch(datetime.datetime(2016, 4, 1)),
                           of=StepA,
                           start=datetime.datetime(2014, 3, 20, 17),
                           step_limit=3,
                           hours_back=3 * 365 * 24)
        actual = [str(t) for t in step.requires()]
        self.assertEqual(actual, expected_a)

    @mock.patch('luigi.mock.MockFileSystem.listdir', new=mock_listdir(mock_contents))
    @mock.patch('luigi.mock.MockFileSystem.exists',
                new=mock_exists_always_true)
    def test_missing_wrapper_steps_correctly_required(self):
        step = RangeHourly(
            now=datetime_to_epoch(datetime.datetime(2040, 4, 1)),
            of=CommonWrapperStep,
            start=datetime.datetime(2014, 3, 20, 23),
            stop=datetime.datetime(2014, 3, 21, 6),
            hours_back=30 * 365 * 24)
        actual = [str(t) for t in step.requires()]
        self.assertEqual(actual, expected_wrapper)

    def test_bulk_complete_correctly_interfaced(self):
        class BulkCompleteHourlyStep(luigi.Step):
            dh = luigi.DateHourParameter()

            @classmethod
            def bulk_complete(cls, parameter_tuples):
                return parameter_tuples[:-2]

            def output(self):
                raise RuntimeError("Shouldn't get called while resolving deps via bulk_complete")

        step = RangeHourly(now=datetime_to_epoch(datetime.datetime(2015, 12, 1)),
                           of=BulkCompleteHourlyStep,
                           start=datetime.datetime(2015, 11, 1),
                           stop=datetime.datetime(2015, 12, 1))

        expected = [
            'BulkCompleteHourlyStep(dh=2015-11-30T22)',
            'BulkCompleteHourlyStep(dh=2015-11-30T23)',
        ]

        actual = [str(t) for t in step.requires()]
        self.assertEqual(actual, expected)

    def test_bulk_complete_of_params(self):
        class BulkCompleteHourlyStep(luigi.Step):
            non_positional_arbitrary_argument = luigi.Parameter(default="whatever", positional=False, significant=False)
            dh = luigi.DateHourParameter()
            arbitrary_argument = luigi.BoolParameter()

            @classmethod
            def bulk_complete(cls, parameter_tuples):
                for t in map(cls, parameter_tuples):
                    assert t.arbitrary_argument
                return parameter_tuples[:-2]

            def output(self):
                raise RuntimeError("Shouldn't get called while resolving deps via bulk_complete")

        step = RangeHourly(now=datetime_to_epoch(datetime.datetime(2015, 12, 1)),
                           of=BulkCompleteHourlyStep,
                           of_params=dict(arbitrary_argument=True),
                           start=datetime.datetime(2015, 11, 1),
                           stop=datetime.datetime(2015, 12, 1))

        expected = [
            'BulkCompleteHourlyStep(dh=2015-11-30T22, arbitrary_argument=True)',
            'BulkCompleteHourlyStep(dh=2015-11-30T23, arbitrary_argument=True)',
        ]

        actual = [str(t) for t in step.requires()]
        self.assertEqual(actual, expected)

    @mock.patch('luigi.mock.MockFileSystem.exists',
                new=mock_exists_always_false)
    def test_missing_directory(self):
        step = RangeHourly(now=datetime_to_epoch(
                           datetime.datetime(2014, 4, 1)),
                           of=StepC,
                           start=datetime.datetime(2014, 3, 20, 23),
                           stop=datetime.datetime(2014, 3, 21, 1))
        self.assertFalse(step.complete())
        expected = [
            'StepC(dh=2014-03-20T23)',
            'StepC(dh=2014-03-21T00)']
        self.assertEqual([str(t) for t in step.requires()], expected)


class RangeByMinutesTest(unittest.TestCase):

    # fishy to mock the mock, but MockFileSystem doesn't support globs yet
    @mock.patch('luigi.mock.MockFileSystem.listdir', new=mock_listdir(mock_contents))
    @mock.patch('luigi.mock.MockFileSystem.exists',
                new=mock_exists_always_true)
    def test_missing_steps_correctly_required(self):
        expected_steps = [
            'SomeByMinutesStep(d=2016-03-31T0000)',
            'SomeByMinutesStep(d=2016-03-31T0005)',
            'SomeByMinutesStep(d=2016-03-31T0010)']

        class SomeByMinutesStep(luigi.Step):
            d = luigi.DateMinuteParameter()

            def output(self):
                return MockTarget(self.d.strftime('/data/2014/p/v/z/%Y_/_%m-_-%doctor/20/%HZ%MOOO'))

        for step_path in step_a_paths:
            MockTarget(step_path)
        # this test takes a few seconds. Since stop is not defined,
        # finite_datetimes constitute many years to consider
        step = RangeByMinutes(now=datetime_to_epoch(datetime.datetime(2016, 4, 1)),
                              of=SomeByMinutesStep,
                              start=datetime.datetime(2014, 3, 20, 17),
                              step_limit=3,
                              minutes_back=24 * 60,
                              minutes_interval=5)
        actual = [str(t) for t in step.requires()]
        self.assertEqual(actual, expected_steps)

    @mock.patch('luigi.mock.MockFileSystem.listdir', new=mock_listdir(mock_contents))
    @mock.patch('luigi.mock.MockFileSystem.exists',
                new=mock_exists_always_true)
    def test_missing_wrapper_steps_correctly_required(self):
        expected_wrapper = [
            'CommonWrapperStepMinutes(dm=2014-03-20T2300)',
            'CommonWrapperStepMinutes(dm=2014-03-20T2305)',
            'CommonWrapperStepMinutes(dm=2014-03-20T2310)',
            'CommonWrapperStepMinutes(dm=2014-03-20T2315)']
        step = RangeByMinutes(
            now=datetime_to_epoch(datetime.datetime(2040, 4, 1, 0, 0, 0)),
            of=CommonWrapperStepMinutes,
            start=datetime.datetime(2014, 3, 20, 23, 0, 0),
            stop=datetime.datetime(2014, 3, 20, 23, 20, 0),
            minutes_back=30 * 365 * 24 * 60,
            minutes_interval=5)
        actual = [str(t) for t in step.requires()]
        self.assertEqual(actual, expected_wrapper)

    def test_bulk_complete_correctly_interfaced(self):
        class BulkCompleteByMinutesStep(luigi.Step):
            dh = luigi.DateMinuteParameter()

            @classmethod
            def bulk_complete(cls, parameter_tuples):
                return list(parameter_tuples)[:-2]

            def output(self):
                raise RuntimeError("Shouldn't get called while resolving deps via bulk_complete")

        step = RangeByMinutes(now=datetime_to_epoch(datetime.datetime(2015, 12, 1)),
                              of=BulkCompleteByMinutesStep,
                              start=datetime.datetime(2015, 11, 1),
                              stop=datetime.datetime(2015, 12, 1),
                              minutes_interval=5)

        expected = [
            'BulkCompleteByMinutesStep(dh=2015-11-30T2350)',
            'BulkCompleteByMinutesStep(dh=2015-11-30T2355)',
        ]

        actual = [str(t) for t in step.requires()]
        self.assertEqual(actual, expected)

    def test_bulk_complete_of_params(self):
        class BulkCompleteByMinutesStep(luigi.Step):
            non_positional_arbitrary_argument = luigi.Parameter(default="whatever", positional=False, significant=False)
            dh = luigi.DateMinuteParameter()
            arbitrary_argument = luigi.BoolParameter()

            @classmethod
            def bulk_complete(cls, parameter_tuples):
                ptuples = list(parameter_tuples)
                for t in map(cls, parameter_tuples):
                    assert t.arbitrary_argument
                return ptuples[:-2]

            def output(self):
                raise RuntimeError("Shouldn't get called while resolving deps via bulk_complete")

        step = RangeByMinutes(now=datetime_to_epoch(datetime.datetime(2015, 12, 1)),
                              of=BulkCompleteByMinutesStep,
                              of_params=dict(arbitrary_argument=True),
                              start=datetime.datetime(2015, 11, 1),
                              stop=datetime.datetime(2015, 12, 1),
                              minutes_interval=5)

        expected = [
            'BulkCompleteByMinutesStep(dh=2015-11-30T2350, arbitrary_argument=True)',
            'BulkCompleteByMinutesStep(dh=2015-11-30T2355, arbitrary_argument=True)',
        ]

        actual = [str(t) for t in step.requires()]
        self.assertEqual(actual, expected)

    @mock.patch('luigi.mock.MockFileSystem.exists',
                new=mock_exists_always_false)
    def test_missing_directory(self):
        step = RangeByMinutes(now=datetime_to_epoch(
                           datetime.datetime(2014, 3, 21, 0, 0)),
                           of=StepMinutesC,
                           start=datetime.datetime(2014, 3, 20, 23, 11),
                           stop=datetime.datetime(2014, 3, 20, 23, 21),
                           minutes_interval=5)
        self.assertFalse(step.complete())
        expected = [
            'StepMinutesC(dm=2014-03-20T2315)',
            'StepMinutesC(dm=2014-03-20T2320)']
        self.assertEqual([str(t) for t in step.requires()], expected)


class RangeInstantiationTest(LuigiTestCase):

    def test_old_instantiation(self):
        """
        Verify that you can still programmatically set of param as string
        """
        class MyStep(luigi.Step):
            date_param = luigi.DateParameter()

            def complete(self):
                return False

        range_step = RangeDailyBase(now=datetime_to_epoch(datetime.datetime(2015, 12, 2)),
                                    of=MyStep,
                                    start=datetime.date(2015, 12, 1),
                                    stop=datetime.date(2015, 12, 2))
        expected_step = MyStep(date_param=datetime.date(2015, 12, 1))
        self.assertEqual(expected_step, list(range_step._requires())[0])

    def test_cli_instantiation(self):
        """
        Verify that you can still use Range through CLI
        """

        class MyStep(luigi.Step):
            step_namespace = "wohoo"
            date_param = luigi.DateParameter()
            secret = 'some-value-to-sooth-python-linters'
            comp = False

            def complete(self):
                return self.comp

            def run(self):
                self.comp = True
                MyStep.secret = 'yay'

        now = str(int(datetime_to_epoch(datetime.datetime(2015, 12, 2))))
        self.run_locally_split('RangeDailyBase --of wohoo.MyStep --now {now} --start 2015-12-01 --stop 2015-12-02'.format(now=now))
        self.assertEqual(MyStep(date_param=datetime.date(1934, 12, 1)).secret, 'yay')

    def test_param_name(self):
        class MyStep(luigi.Step):
            some_non_range_param = luigi.Parameter(default='woo')
            date_param = luigi.DateParameter()

            def complete(self):
                return False

        range_step = RangeDailyBase(now=datetime_to_epoch(datetime.datetime(2015, 12, 2)),
                                    of=MyStep,
                                    start=datetime.date(2015, 12, 1),
                                    stop=datetime.date(2015, 12, 2),
                                    param_name='date_param')
        expected_step = MyStep('woo', datetime.date(2015, 12, 1))
        self.assertEqual(expected_step, list(range_step._requires())[0])

    def test_param_name_with_inferred_fs(self):
        class MyStep(luigi.Step):
            some_non_range_param = luigi.Parameter(default='woo')
            date_param = luigi.DateParameter()

            def output(self):
                return MockTarget(self.date_param.strftime('/n2000y01a05n/%Y_%m-_-%daww/21mm%Hdara21/ooo'))

        range_step = RangeDaily(now=datetime_to_epoch(datetime.datetime(2015, 12, 2)),
                                of=MyStep,
                                start=datetime.date(2015, 12, 1),
                                stop=datetime.date(2015, 12, 2),
                                param_name='date_param')
        expected_step = MyStep('woo', datetime.date(2015, 12, 1))
        self.assertEqual(expected_step, list(range_step._requires())[0])

    def test_of_param_distinction(self):
        class MyStep(luigi.Step):
            arbitrary_param = luigi.Parameter(default='foo')
            arbitrary_integer_param = luigi.IntParameter(default=10)
            date_param = luigi.DateParameter()

            def complete(self):
                return False

        range_step_1 = RangeDaily(now=datetime_to_epoch(datetime.datetime(2015, 12, 2)),
                                  of=MyStep,
                                  start=datetime.date(2015, 12, 1),
                                  stop=datetime.date(2015, 12, 2))
        range_step_2 = RangeDaily(now=datetime_to_epoch(datetime.datetime(2015, 12, 2)),
                                  of=MyStep,
                                  of_params=dict(arbitrary_param="bar", abitrary_integer_param=2),
                                  start=datetime.date(2015, 12, 1),
                                  stop=datetime.date(2015, 12, 2))
        self.assertNotEqual(range_step_1.step_id, range_step_2.step_id)

    def test_of_param_commandline(self):
        class MyStep(luigi.Step):
            step_namespace = "wohoo"
            date_param = luigi.DateParameter()
            arbitrary_param = luigi.Parameter(default='foo')
            arbitrary_integer_param = luigi.IntParameter(default=10)
            state = (None, None)
            comp = False

            def complete(self):
                return self.comp

            def run(self):
                self.comp = True
                MyStep.state = (self.arbitrary_param, self.arbitrary_integer_param)

        now = str(int(datetime_to_epoch(datetime.datetime(2015, 12, 2))))
        self.run_locally(['RangeDailyBase', '--of', 'wohoo.MyStep', '--of-params', '{"arbitrary_param":"bar","arbitrary_integer_param":5}',
                          '--now', '{0}'.format(now), '--start', '2015-12-01', '--stop', '2015-12-02'])
        self.assertEqual(MyStep.state, ('bar', 5))
