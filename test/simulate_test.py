# -*- coding: utf-8 -*-
#
# Copyright 2012-2015 Spotify AB
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

from helpers import unittest
import luigi
from luigi.contrib.simulate import RunAnywayTarget

from multiprocessing import Process
import os
import tempfile


def temp_dir():
    return os.path.join(tempfile.gettempdir(), 'luigi-simulate')


def is_writable():
    d = temp_dir()
    fn = os.path.join(d, 'luigi-simulate-write-test')
    exists = True
    try:
        try:
            os.makedirs(d)
        except OSError:
            pass
        open(fn, 'w').close()
        os.remove(fn)
    except BaseException:
        exists = False

    return unittest.skipIf(not exists, 'Can\'t write to temporary directory')


class StepA(luigi.Step):
    i = luigi.IntParameter(default=0)

    def output(self):
        return RunAnywayTarget(self)

    def run(self):
        fn = os.path.join(temp_dir(), 'luigi-simulate-test.tmp')
        try:
            os.makedirs(os.path.dirname(fn))
        except OSError:
            pass

        with open(fn, 'a') as f:
            f.write('{0}={1}\n'.format(self.__class__.__name__, self.i))

        self.output().done()


class StepB(StepA):
    def requires(self):
        return StepA(i=10)


class StepC(StepA):
    def requires(self):
        return StepA(i=5)


class StepD(StepA):
    def requires(self):
        return [StepB(), StepC(), StepA(i=20)]


class StepWrap(luigi.WrapperStep):
    def requires(self):
        return [StepA(), StepD()]


def reset():
    # Force steps to be executed again (because multiple pipelines are executed inside of the same process)
    t = StepA().output()
    with t.unique.get_lock():
        t.unique.value = 0


class RunAnywayTargetTest(unittest.TestCase):
    @is_writable()
    def test_output(self):
        reset()

        fn = os.path.join(temp_dir(), 'luigi-simulate-test.tmp')

        luigi.build([StepWrap()], local_scheduler=True)
        with open(fn, 'r') as f:
            data = f.read().strip().split('\n')

        data.sort()
        reference = ['StepA=0', 'StepA=10', 'StepA=20', 'StepA=5', 'StepB=0', 'StepC=0', 'StepD=0']
        reference.sort()

        os.remove(fn)
        self.assertEqual(data, reference)

    @is_writable()
    def test_output_again(self):
        # Running the test in another process because the PID is used to determine if the target exists
        p = Process(target=self.test_output)
        p.start()
        p.join()
