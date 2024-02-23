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

import logging
import os

import trun
import trun.contrib.hadoop_jar
import trun.contrib.hdfs

logger = logging.getLogger('trun-interface')


def hadoop_examples_jar():
    config = trun.configuration.get_config()
    examples_jar = config.get('hadoop', 'examples-jar')
    if not examples_jar:
        logger.error("You must specify hadoop:examples-jar in trun.cfg")
        raise
    if not os.path.exists(examples_jar):
        logger.error("Can't find example jar: " + examples_jar)
        raise
    return examples_jar


DEFAULT_TERASORT_IN = '/tmp/terasort-in'
DEFAULT_TERASORT_OUT = '/tmp/terasort-out'


class TeraGen(trun.contrib.hadoop_jar.HadoopJarJobStep):
    """
    Runs TeraGen, by default with 1TB of data (10B records)
    """

    records = trun.Parameter(default="10000000000",
                              description="Number of records, each record is 100 Bytes")
    terasort_in = trun.Parameter(default=DEFAULT_TERASORT_IN,
                                  description="directory to store terasort input into.")

    def output(self):
        """
        Returns the target output for this step.
        In this case, a successful execution of this step will create a file in HDFS.

        :return: the target output for this step.
        :rtype: object (:py:class:`~trun.target.Target`)
        """
        return trun.contrib.hdfs.HdfsTarget(self.terasort_in)

    def jar(self):
        return hadoop_examples_jar()

    def main(self):
        return "teragen"

    def args(self):
        # First arg is 10B -- each record is 100bytes
        return [self.records, self.output()]


class TeraSort(trun.contrib.hadoop_jar.HadoopJarJobStep):
    """
    Runs TeraGent, by default using
    """

    terasort_in = trun.Parameter(default=DEFAULT_TERASORT_IN,
                                  description="directory to store terasort input into.")
    terasort_out = trun.Parameter(default=DEFAULT_TERASORT_OUT,
                                   description="directory to store terasort output into.")

    def requires(self):
        """
        This step's dependencies:

        * :py:class:`~.TeraGen`

        :return: object (:py:class:`trun.step.Step`)
        """
        return TeraGen(terasort_in=self.terasort_in)

    def output(self):
        """
        Returns the target output for this step.
        In this case, a successful execution of this step will create a file in HDFS.

        :return: the target output for this step.
        :rtype: object (:py:class:`~trun.target.Target`)
        """
        return trun.contrib.hdfs.HdfsTarget(self.terasort_out)

    def jar(self):
        return hadoop_examples_jar()

    def main(self):
        return "terasort"

    def args(self):
        return [self.input(), self.output()]
