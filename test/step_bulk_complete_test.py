
from helpers import unittest
from trun import Step
from trun import Parameter
from trun.step import MixinNaiveBulkComplete

COMPLETE_STEPS = ["A", "B", "C"]


class MockStep(MixinNaiveBulkComplete, Step):
    param_a = Parameter()
    param_b = Parameter(default="Not Mandatory")

    def complete(self):
        return self.param_a in COMPLETE_STEPS


class MixinNaiveBulkCompleteTest(unittest.TestCase):
    """
        Test that the MixinNaiveBulkComplete can handle
        input as
         - iterable of parameters (for single param steps)
         - iterable of parameter tuples (for multi param steps)
         - iterable of parameter dicts (for multi param steps)
    """
    def test_single_arg_list(self):
        single_arg_list = ["A", "B", "x"]
        expected_single_arg_list = {p for p in single_arg_list if p in COMPLETE_STEPS}
        self.assertEqual(
            expected_single_arg_list,
            set(MockStep.bulk_complete(single_arg_list))
        )

    def test_multiple_arg_tuple(self):
        multiple_arg_tuple = (("A", "1"), ("B", "2"), ("X", "3"), ("C", "2"))
        expected_multiple_arg_tuple = {p for p in multiple_arg_tuple if p[0] in COMPLETE_STEPS}
        self.assertEqual(
            expected_multiple_arg_tuple,
            set(MockStep.bulk_complete(multiple_arg_tuple))
        )

    def test_multiple_arg_dict(self):
        multiple_arg_dict = (
            {"param_a": "X", "param_b": "1"},
            {"param_a": "C", "param_b": "1"}
        )
        expected_multiple_arg_dict = (
            [p for p in multiple_arg_dict if p["param_a"] in COMPLETE_STEPS]
        )
        self.assertEqual(
            expected_multiple_arg_dict,
            MockStep.bulk_complete(multiple_arg_dict)
        )