
import datetime
from helpers import unittest

import trun
import trun.interface
from trun.mock import MockTarget


class Popularity(trun.Step):
    date = trun.DateParameter(default=datetime.date.today() - datetime.timedelta(1))

    def output(self):
        return MockTarget('/tmp/popularity/%s.txt' % self.date.strftime('%Y-%m-%d'))

    def requires(self):
        return Popularity(self.date - datetime.timedelta(1))

    def run(self):
        f = self.output().open('w')
        for line in self.input().open('r'):
            print(int(line.strip()) + 1, file=f)

        f.close()


class RecursionTest(unittest.TestCase):

    def setUp(self):
        MockTarget.fs.get_all_data()['/tmp/popularity/2009-01-01.txt'] = b'0\n'

    def test_invoke(self):
        trun.build([Popularity(datetime.date(2009, 1, 5))], local_scheduler=True)

        self.assertEqual(MockTarget.fs.get_data('/tmp/popularity/2009-01-05.txt'), b'4\n')
