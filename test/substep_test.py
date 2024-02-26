

import abc
from helpers import unittest

import trun


class AbstractStep(trun.Step):
    k = trun.IntParameter()

    @property
    @abc.abstractmethod
    def foo(self):
        raise NotImplementedError

    @abc.abstractmethod
    def helper_function(self):
        raise NotImplementedError

    def run(self):
        return ",".join([self.foo, self.helper_function()])


class Implementation(AbstractStep):

    @property
    def foo(self):
        return "bar"

    def helper_function(self):
        return "hello" * self.k


class AbstractSubclassTest(unittest.TestCase):

    def test_instantiate_abstract(self):
        def try_instantiate():
            AbstractStep(k=1)

        self.assertRaises(TypeError, try_instantiate)

    def test_instantiate(self):
        self.assertEqual("bar,hellohello", Implementation(k=2).run())
