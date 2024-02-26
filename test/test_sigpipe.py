

import os
from helpers import unittest

from trun.format import InputPipeProcessWrapper


BASH_SCRIPT = """
#!/bin/bash

trap "touch /tmp/trun_sigpipe.marker; exit 141" SIGPIPE


for i in {1..3}
do
    sleep 0.1
    echo "Welcome $i times"
done
"""

FAIL_SCRIPT = BASH_SCRIPT + """
exit 1
"""


class TestSigpipe(unittest.TestCase):

    def setUp(self):
        with open("/tmp/trun_test_sigpipe.sh", "w") as fp:
            fp.write(BASH_SCRIPT)

    def tearDown(self):
        os.remove("/tmp/trun_test_sigpipe.sh")
        if os.path.exists("/tmp/trun_sigpipe.marker"):
            os.remove("/tmp/trun_sigpipe.marker")

    def test_partial_read(self):
        p1 = InputPipeProcessWrapper(["bash", "/tmp/trun_test_sigpipe.sh"])
        self.assertEqual(p1.readline().decode('utf8'), "Welcome 1 times\n")
        p1.close()
        self.assertTrue(os.path.exists("/tmp/trun_sigpipe.marker"))

    def test_full_read(self):
        p1 = InputPipeProcessWrapper(["bash", "/tmp/trun_test_sigpipe.sh"])
        counter = 1
        for line in p1:
            self.assertEqual(line.decode('utf8'), "Welcome %i times\n" % counter)
            counter += 1
        p1.close()
        self.assertFalse(os.path.exists("/tmp/trun_sigpipe.marker"))


class TestSubprocessException(unittest.TestCase):

    def setUp(self):
        with open("/tmp/trun_test_sigpipe.sh", "w") as fp:
            fp.write(FAIL_SCRIPT)

    def tearDown(self):
        os.remove("/tmp/trun_test_sigpipe.sh")
        if os.path.exists("/tmp/trun_sigpipe.marker"):
            os.remove("/tmp/trun_sigpipe.marker")

    def test_partial_read(self):
        p1 = InputPipeProcessWrapper(["bash", "/tmp/trun_test_sigpipe.sh"])
        self.assertEqual(p1.readline().decode('utf8'), "Welcome 1 times\n")
        p1.close()
        self.assertTrue(os.path.exists("/tmp/trun_sigpipe.marker"))

    def test_full_read(self):
        def run():
            p1 = InputPipeProcessWrapper(["bash", "/tmp/trun_test_sigpipe.sh"])
            counter = 1
            for line in p1:
                self.assertEqual(line.decode('utf8'), "Welcome %i times\n" % counter)
                counter += 1
            p1.close()

        self.assertRaises(RuntimeError, run)
