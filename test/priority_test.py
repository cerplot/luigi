
from helpers import unittest

import trun
import trun.notifications

trun.notifications.DEBUG = True


class PrioStep(trun.Step):
    prio = trun.Parameter()
    run_counter = 0

    @property
    def priority(self):
        return self.prio

    def requires(self):
        if self.prio > 10:
            return PrioStep(self.prio - 10)

    def run(self):
        self.t = PrioStep.run_counter
        PrioStep.run_counter += 1

    def complete(self):
        return hasattr(self, 't')


class PriorityTest(unittest.TestCase):

    def test_priority(self):
        p, q, r = PrioStep(1), PrioStep(2), PrioStep(3)
        trun.build([p, q, r], local_scheduler=True)
        self.assertTrue(r.t < q.t < p.t)

    def test_priority_w_dep(self):
        x, y, z = PrioStep(25), PrioStep(15), PrioStep(5)
        a, b, c = PrioStep(24), PrioStep(14), PrioStep(4)
        trun.build([a, b, c, x, y, z], local_scheduler=True)
        self.assertTrue(z.t < y.t < x.t < c.t < b.t < a.t)
