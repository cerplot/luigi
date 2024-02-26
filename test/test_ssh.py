

import subprocess
from helpers import unittest

from trun.contrib.ssh import RemoteContext


class TestMockedRemoteContext(unittest.TestCase):

    def test_subprocess_delegation(self):
        """ Test subprocess call structure using mock module """
        orig_Popen = subprocess.Popen
        self.last_test = None

        def Popen(cmd, **kwargs):
            self.last_test = cmd

        subprocess.Popen = Popen
        context = RemoteContext(
            "some_host",
            username="trun",
            key_file="/some/key.pub"
        )
        context.Popen(["ls"])
        self.assertTrue("ssh" in self.last_test)
        self.assertTrue("-i" in self.last_test)
        self.assertTrue("/some/key.pub" in self.last_test)
        self.assertTrue("trun@some_host" in self.last_test)
        self.assertTrue("ls" in self.last_test)

        subprocess.Popen = orig_Popen

    def test_check_output_fail_connect(self):
        """ Test check_output to a non-existing host """
        context = RemoteContext("__NO_HOST_LIKE_THIS__", connect_timeout=1)
        self.assertRaises(
            subprocess.CalledProcessError,
            context.check_output, ["ls"]
        )
