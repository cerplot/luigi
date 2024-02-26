

from helpers import unittest

import pytest

import trun.target
from trun.contrib.target import CascadingClient


@pytest.mark.contrib
class CascadingClientTest(unittest.TestCase):

    def setUp(self):
        class FirstClient:

            def exists(self, pos_arg, kw_arg='first'):
                if pos_arg < 10:
                    return pos_arg
                elif pos_arg < 20:
                    return kw_arg
                elif kw_arg == 'raise_fae':
                    raise trun.target.FileAlreadyExists('oh noes!')
                else:
                    raise Exception()

        class SecondClient:

            def exists(self, pos_arg, other_kw_arg='second',
                       kw_arg='for-backwards-compatibility'):
                if pos_arg < 30:
                    return -pos_arg
                elif pos_arg < 40:
                    return other_kw_arg
                else:
                    raise Exception()

        self.clients = [FirstClient(), SecondClient()]
        self.client = CascadingClient(self.clients)

    def test_successes(self):
        self.assertEqual(5, self.client.exists(5))
        self.assertEqual('yay', self.client.exists(15, kw_arg='yay'))

    def test_fallbacking(self):
        self.assertEqual(-25, self.client.exists(25))
        self.assertEqual('lol', self.client.exists(35, kw_arg='yay',
                                                   other_kw_arg='lol'))
        # Note: the first method don't accept the other keyword argument
        self.assertEqual(-15, self.client.exists(15, kw_arg='yay',
                                                 other_kw_arg='lol'))

    def test_failings(self):
        self.assertRaises(Exception, lambda: self.client.exists(45))
        self.assertRaises(AttributeError, lambda: self.client.mkdir())

    def test_FileAlreadyExists_propagation(self):
        self.assertRaises(trun.target.FileAlreadyExists,
                          lambda: self.client.exists(25, kw_arg='raise_fae'))

    def test_method_names_kwarg(self):
        self.client = CascadingClient(self.clients, method_names=[])
        self.assertRaises(AttributeError, lambda: self.client.exists())
        self.client = CascadingClient(self.clients, method_names=['exists'])
        self.assertEqual(5, self.client.exists(5))
