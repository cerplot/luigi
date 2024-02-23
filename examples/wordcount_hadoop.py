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

import trun
import trun.contrib.hadoop
import trun.contrib.hdfs


# To make this run, you probably want to edit /etc/trun/client.cfg and add something like:
#
# [hadoop]
# jar: /usr/lib/hadoop-xyz/hadoop-streaming-xyz-123.jar


class InputText(trun.ExternalStep):
    """
    This step is a :py:class:`trun.step.ExternalStep` which means it doesn't generate the
    :py:meth:`~.InputText.output` target on its own instead relying on the execution something outside of Trun
    to produce it.
    """

    date = trun.DateParameter()

    def output(self):
        """
        Returns the target output for this step.
        In this case, it expects a file to be present in HDFS.

        :return: the target output for this step.
        :rtype: object (:py:class:`trun.target.Target`)
        """
        return trun.contrib.hdfs.HdfsTarget(self.date.strftime('/tmp/text/%Y-%m-%d.txt'))


class WordCount(trun.contrib.hadoop.JobStep):
    """
    This step runs a :py:class:`trun.contrib.hadoop.JobStep`
    over the target data returned by :py:meth:`~/.InputText.output` and
    writes the result into its :py:meth:`~.WordCount.output` target.

    This class uses :py:meth:`trun.contrib.hadoop.JobStep.run`.
    """

    date_interval = trun.DateIntervalParameter()

    def requires(self):
        """
        This step's dependencies:

        * :py:class:`~.InputText`

        :return: list of object (:py:class:`trun.step.Step`)
        """
        return [InputText(date) for date in self.date_interval.dates()]

    def output(self):
        """
        Returns the target output for this step.
        In this case, a successful execution of this step will create a file in HDFS.

        :return: the target output for this step.
        :rtype: object (:py:class:`trun.target.Target`)
        """
        return trun.contrib.hdfs.HdfsTarget('/tmp/text-count/%s' % self.date_interval)

    def mapper(self, line):
        for word in line.strip().split():
            yield word, 1

    def reducer(self, key, values):
        yield key, sum(values)


if __name__ == '__main__':
    trun.run()
