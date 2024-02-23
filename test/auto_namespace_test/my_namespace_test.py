import trun
from helpers import TrunTestCase


class MyNamespaceTest(TrunTestCase):
    def test_auto_namespace_scope(self):
        class MyStep(trun.Step):
            pass
        self.assertTrue(self.run_locally(['auto_namespace_test.my_namespace_test.MyStep']))
        self.assertEqual(MyStep.get_step_namespace(), 'auto_namespace_test.my_namespace_test')
