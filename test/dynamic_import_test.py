
from helpers import TrunTestCase, temporary_unloaded_module

import trun
import trun.interface

CONTENTS = b'''
import trun

class FooStep(trun.Step):
    x = trun.IntParameter()

    def run(self):
        trun._testing_glob_var = self.x
'''


class CmdlineTest(TrunTestCase):

    def test_dynamic_loading(self):
        with temporary_unloaded_module(CONTENTS) as temp_module_name:
            trun.interface.run(['--module', temp_module_name, 'FooStep', '--x', '123', '--local-scheduler', '--no-lock'])
            self.assertEqual(trun._testing_glob_var, 123)
