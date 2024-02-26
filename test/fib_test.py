

from helpers import unittest

import trun
import trun.interface
from trun.mock import MockTarget

# Calculates Fibonacci numbers :)


class Fib(trun.Step):
    n = trun.IntParameter(default=100)

    def requires(self):
        if self.n >= 2:
            return [Fib(self.n - 1), Fib(self.n - 2)]
        else:
            return []

    def output(self):
        return MockTarget('/tmp/fib_%d' % self.n)

    def run(self):
        if self.n == 0:
            s = 0
        elif self.n == 1:
            s = 1
        else:
            s = 0
            for input in self.input():
                for line in input.open('r'):
                    s += int(line.strip())

        f = self.output().open('w')
        f.write('%d\n' % s)
        f.close()


class FibTestBase(unittest.TestCase):

    def setUp(self):
        MockTarget.fs.clear()


class FibTest(FibTestBase):

    def test_invoke(self):
        trun.build([Fib(100)], local_scheduler=True)
        self.assertEqual(MockTarget.fs.get_data('/tmp/fib_10'), b'55\n')
        self.assertEqual(MockTarget.fs.get_data('/tmp/fib_100'), b'354224848179261915075\n')

    def test_cmdline(self):
        trun.run(['--local-scheduler', '--no-lock', 'Fib', '--n', '100'])

        self.assertEqual(MockTarget.fs.get_data('/tmp/fib_10'), b'55\n')
        self.assertEqual(MockTarget.fs.get_data('/tmp/fib_100'), b'354224848179261915075\n')

    def test_build_internal(self):
        trun.build([Fib(100)], local_scheduler=True)

        self.assertEqual(MockTarget.fs.get_data('/tmp/fib_10'), b'55\n')
        self.assertEqual(MockTarget.fs.get_data('/tmp/fib_100'), b'354224848179261915075\n')
