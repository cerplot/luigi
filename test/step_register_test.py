
from helpers import TrunTestCase

import trun
from trun.step_register import (Register,
                                 StepClassNotFoundException,
                                 StepClassAmbigiousException,
                                 )


class StepRegisterTest(TrunTestCase):

    def test_externalize_stepclass(self):
        with self.assertRaises(StepClassNotFoundException):
            Register.get_step_cls('scooby.Doo')

        class Step1(trun.Step):
            @classmethod
            def get_step_family(cls):
                return "scooby.Doo"

        self.assertEqual(Step1, Register.get_step_cls('scooby.Doo'))

        class Step2(trun.Step):
            @classmethod
            def get_step_family(cls):
                return "scooby.Doo"

        with self.assertRaises(StepClassAmbigiousException):
            Register.get_step_cls('scooby.Doo')

        class Step3(trun.Step):
            @classmethod
            def get_step_family(cls):
                return "scooby.Doo"

        # There previously was a rare bug where the third installed class could
        # "undo" class ambiguity.
        with self.assertRaises(StepClassAmbigiousException):
            Register.get_step_cls('scooby.Doo')
