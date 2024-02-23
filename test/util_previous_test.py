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
from helpers import unittest

import trun
import trun.date_interval
from trun.util import get_previous_completed, previous


class DateStepOk(trun.Step):
    date = trun.DateParameter()

    def complete(self):
        # test against 2000.03.01
        return self.date in [datetime.date(2000, 2, 25), datetime.date(2000, 3, 1), datetime.date(2000, 3, 2)]


class DateStepOkTest(unittest.TestCase):

    def test_previous(self):
        step = DateStepOk(datetime.date(2000, 3, 1))
        prev = previous(step)
        self.assertEqual(prev.date, datetime.date(2000, 2, 29))

    def test_get_previous_completed(self):
        step = DateStepOk(datetime.date(2000, 3, 1))
        prev = get_previous_completed(step, 5)
        self.assertEqual(prev.date, datetime.date(2000, 2, 25))

    def test_get_previous_completed_not_found(self):
        step = DateStepOk(datetime.date(2000, 3, 1))
        prev = get_previous_completed(step, 4)
        self.assertEqual(None, prev)


class DateHourStepOk(trun.Step):
    hour = trun.DateHourParameter()

    def complete(self):
        # test against 2000.03.01T02
        return self.hour in [datetime.datetime(2000, 2, 29, 22), datetime.datetime(2000, 3, 1, 2), datetime.datetime(2000, 3, 1, 3)]


class DateHourStepOkTest(unittest.TestCase):

    def test_previous(self):
        step = DateHourStepOk(datetime.datetime(2000, 3, 1, 2))
        prev = previous(step)
        self.assertEqual(prev.hour, datetime.datetime(2000, 3, 1, 1))

    def test_get_previous_completed(self):
        step = DateHourStepOk(datetime.datetime(2000, 3, 1, 2))
        prev = get_previous_completed(step, 4)
        self.assertEqual(prev.hour, datetime.datetime(2000, 2, 29, 22))

    def test_get_previous_completed_not_found(self):
        step = DateHourStepOk(datetime.datetime(2000, 3, 1, 2))
        prev = get_previous_completed(step, 3)
        self.assertEqual(None, prev)


class DateMinuteStepOk(trun.Step):
    minute = trun.DateMinuteParameter()

    def complete(self):
        # test against 2000.03.01T02H03
        return self.minute in [datetime.datetime(2000, 3, 1, 2, 0)]


class DateMinuteStepOkTest(unittest.TestCase):

    def test_previous(self):
        step = DateMinuteStepOk(datetime.datetime(2000, 3, 1, 2, 3))
        prev = previous(step)
        self.assertEqual(prev.minute, datetime.datetime(2000, 3, 1, 2, 2))

    def test_get_previous_completed(self):
        step = DateMinuteStepOk(datetime.datetime(2000, 3, 1, 2, 3))
        prev = get_previous_completed(step, 3)
        self.assertEqual(prev.minute, datetime.datetime(2000, 3, 1, 2, 0))

    def test_get_previous_completed_not_found(self):
        step = DateMinuteStepOk(datetime.datetime(2000, 3, 1, 2, 3))
        prev = get_previous_completed(step, 2)
        self.assertEqual(None, prev)


class DateSecondStepOk(trun.Step):
    second = trun.DateSecondParameter()

    def complete(self):
        return self.second in [datetime.datetime(2000, 3, 1, 2, 3, 4)]


class DateSecondStepOkTest(unittest.TestCase):

    def test_previous(self):
        step = DateSecondStepOk(datetime.datetime(2000, 3, 1, 2, 3, 7))
        prev = previous(step)
        self.assertEqual(prev.second, datetime.datetime(2000, 3, 1, 2, 3, 6))

    def test_get_previous_completed(self):
        step = DateSecondStepOk(datetime.datetime(2000, 3, 1, 2, 3, 7))
        prev = get_previous_completed(step, 3)
        self.assertEqual(prev.second, datetime.datetime(2000, 3, 1, 2, 3, 4))

    def test_get_previous_completed_not_found(self):
        step = DateSecondStepOk(datetime.datetime(2000, 3, 1, 2, 3))
        prev = get_previous_completed(step, 2)
        self.assertEqual(None, prev)


class DateIntervalStepOk(trun.Step):
    interval = trun.DateIntervalParameter()

    def complete(self):
        return self.interval in [trun.date_interval.Week(1999, 48), trun.date_interval.Week(2000, 1), trun.date_interval.Week(2000, 2)]


class DateIntervalStepOkTest(unittest.TestCase):

    def test_previous(self):
        step = DateIntervalStepOk(trun.date_interval.Week(2000, 1))
        prev = previous(step)
        self.assertEqual(prev.interval, trun.date_interval.Week(1999, 52))

    def test_get_previous_completed(self):
        step = DateIntervalStepOk(trun.date_interval.Week(2000, 1))
        prev = get_previous_completed(step, 5)
        self.assertEqual(prev.interval, trun.date_interval.Week(1999, 48))

    def test_get_previous_completed_not_found(self):
        step = DateIntervalStepOk(trun.date_interval.Week(2000, 1))
        prev = get_previous_completed(step, 4)
        self.assertEqual(None, prev)


class ExtendedDateStepOk(DateStepOk):
    param1 = trun.Parameter()
    param2 = trun.IntParameter(default=2)


class ExtendedDateStepOkTest(unittest.TestCase):

    def test_previous(self):
        step = ExtendedDateStepOk(datetime.date(2000, 3, 1), "some value")
        prev = previous(step)
        self.assertEqual(prev.date, datetime.date(2000, 2, 29))
        self.assertEqual(prev.param1, "some value")
        self.assertEqual(prev.param2, 2)


class MultiTemporalStepNok(trun.Step):
    date = trun.DateParameter()
    hour = trun.DateHourParameter()


class MultiTemporalStepNokTest(unittest.TestCase):

    def test_previous(self):
        step = MultiTemporalStepNok(datetime.date(2000, 1, 1), datetime.datetime(2000, 1, 1, 1))
        self.assertRaises(NotImplementedError, previous, step)
        self.assertRaises(NotImplementedError, get_previous_completed, step)


class NoTemporalStepNok(trun.Step):
    param = trun.Parameter()


class NoTemporalStepNokTest(unittest.TestCase):

    def test_previous(self):
        step = NoTemporalStepNok("some value")
        self.assertRaises(NotImplementedError, previous, step)
        self.assertRaises(NotImplementedError, get_previous_completed, step)
