

from helpers import unittest

import trun


def create_class(cls_name):
    class NewStep(trun.WrapperStep):
        pass

    NewStep.__name__ = cls_name

    return NewStep


create_class('MyNewStep')


class SetStepNameTest(unittest.TestCase):

    ''' I accidentally introduced an issue in this commit:
    https://github.com/spotify/trun/commit/6330e9d0332e6152996292a39c42f752b9288c96

    This causes steps not to get exposed if they change name later. Adding a unit test
    to resolve the issue. '''

    def test_set_step_name(self):
        trun.run(['--local-scheduler', '--no-lock', 'MyNewStep'])
