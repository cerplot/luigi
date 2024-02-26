
from helpers import unittest

import trun
import trun.notifications

trun.notifications.DEBUG = True


class LinearSum(trun.Step):
    lo = trun.IntParameter()
    hi = trun.IntParameter()

    def requires(self):
        if self.hi > self.lo:
            return self.clone(hi=self.hi - 1)

    def run(self):
        if self.hi > self.lo:
            self.s = self.requires().s + self.f(self.hi - 1)
        else:
            self.s = 0
        self.complete = lambda: True  # workaround since we don't write any output

    def complete(self):
        return False

    def f(self, x):
        return x


class PowerSum(LinearSum):
    p = trun.IntParameter()

    def f(self, x):
        return x ** self.p


class CloneTest(unittest.TestCase):

    def test_args(self):
        t = LinearSum(lo=42, hi=45)
        self.assertEqual(t.param_args, (42, 45))
        self.assertEqual(t.param_kwargs, {'lo': 42, 'hi': 45})

    def test_recursion(self):
        t = LinearSum(lo=42, hi=45)
        trun.build([t], local_scheduler=True)
        self.assertEqual(t.s, 42 + 43 + 44)

    def test_inheritance(self):
        t = PowerSum(lo=42, hi=45, p=2)
        trun.build([t], local_scheduler=True)
        self.assertEqual(t.s, 42 ** 2 + 43 ** 2 + 44 ** 2)

    def test_inheritance_from_non_parameter(self):
        """
        Cloning can pull non-source-parameters from source to target parameter.
        """

        class SubStep(trun.Step):
            lo = 1

            @property
            def hi(self):
                return 2

        t1 = SubStep()
        t2 = t1.clone(cls=LinearSum)
        self.assertEqual(t2.lo, 1)
        self.assertEqual(t2.hi, 2)
