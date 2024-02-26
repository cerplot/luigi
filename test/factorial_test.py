

from helpers import unittest

import trun


class Factorial(trun.Step):

    ''' This calculates factorials *online* and does not write its results anywhere

    Demonstrates the ability for dependencies between Steps and not just between their output.
    '''
    n = trun.IntParameter(default=100)

    def requires(self):
        if self.n > 1:
            return Factorial(self.n - 1)

    def run(self):
        if self.n > 1:
            self.value = self.n * self.requires().value
        else:
            self.value = 1
        self.complete = lambda: True

    def complete(self):
        return False


class FactorialTest(unittest.TestCase):

    def test_invoke(self):
        trun.build([Factorial(100)], local_scheduler=True)
        self.assertEqual(Factorial(42).value, 1405006117752879898543142606244511569936384000000000)
