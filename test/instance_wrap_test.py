
import datetime
import decimal
from helpers import unittest

import trun
import trun.notifications
from trun.mock import MockTarget

trun.notifications.DEBUG = True


class Report(trun.Step):
    date = trun.DateParameter()

    def run(self):
        f = self.output().open('w')
        f.write('10.0 USD\n')
        f.write('4.0 EUR\n')
        f.write('3.0 USD\n')
        f.close()

    def output(self):
        return MockTarget(self.date.strftime('/tmp/report-%Y-%m-%d'))


class ReportReader(trun.Step):
    date = trun.DateParameter()

    def requires(self):
        return Report(self.date)

    def run(self):
        self.lines = list(self.input().open('r').readlines())

    def get_line(self, line):
        amount, currency = self.lines[line].strip().split()
        return decimal.Decimal(amount), currency

    def complete(self):
        return False


class CurrencyExchanger(trun.Step):
    step = trun.Parameter()
    currency_to = trun.Parameter()

    exchange_rates = {('USD', 'USD'): decimal.Decimal(1),
                      ('EUR', 'USD'): decimal.Decimal('1.25')}

    def requires(self):
        return self.step  # Note that you still need to state this explicitly

    def get_line(self, line):
        amount, currency_from = self.step.get_line(line)
        return amount * self.exchange_rates[(currency_from, self.currency_to)], self.currency_to

    def complete(self):
        return False


class InstanceWrapperTest(unittest.TestCase):

    ''' This test illustrates that steps can have steps as parameters

    This is a more complicated variant of factorial_test.py which is an example of
    steps communicating directly with other steps. In this case, a step takes another
    step as a parameter and wraps it.

    Also see wrap_test.py for an example of a step class wrapping another step class.

    Not the most useful pattern, but there's actually been a few cases where it was
    pretty handy to be able to do that. I'm adding it as a unit test to make sure that
    new code doesn't break the expected behavior.
    '''

    def test(self):
        d = datetime.date(2012, 1, 1)
        r = ReportReader(d)
        ex = CurrencyExchanger(r, 'USD')

        trun.build([ex], local_scheduler=True)
        self.assertEqual(ex.get_line(0), (decimal.Decimal('10.0'), 'USD'))
        self.assertEqual(ex.get_line(1), (decimal.Decimal('5.0'), 'USD'))
