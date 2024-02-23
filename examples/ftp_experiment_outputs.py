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
import luigi
from luigi.contrib.ftp import RemoteTarget

#: the FTP server
HOST = "some_host"
#: the username
USER = "user"
#: the password
PWD = "some_password"


class ExperimentStep(luigi.ExternalStep):
    """
    This class represents something that was created elsewhere by an external process,
    so all we want to do is to implement the output method.
    """

    def output(self):
        """
        Returns the target output for this step.
        In this case, a successful execution of this step will create a file that will be created in a FTP server.

        :return: the target output for this step.
        :rtype: object (:py:class:`~luigi.target.Target`)
        """
        return RemoteTarget('/experiment/output1.txt', HOST, username=USER, password=PWD)

    def run(self):
        """
        The execution of this step will write 4 lines of data on this step's target output.
        """
        with self.output().open('w') as outfile:
            print("data 0 200 10 50 60", file=outfile)
            print("data 1 190 9 52 60", file=outfile)
            print("data 2 200 10 52 60", file=outfile)
            print("data 3 195 1 52 60", file=outfile)


class ProcessingStep(luigi.Step):
    """
    This class represents something that was created elsewhere by an external process,
    so all we want to do is to implement the output method.
    """

    def requires(self):
        """
        This step's dependencies:

        * :py:class:`~.ExperimentStep`

        :return: object (:py:class:`luigi.step.Step`)
        """
        return ExperimentStep()

    def output(self):
        """
        Returns the target output for this step.
        In this case, a successful execution of this step will create a file on the local filesystem.

        :return: the target output for this step.
        :rtype: object (:py:class:`~luigi.target.Target`)
        """
        return luigi.LocalTarget('/tmp/processeddata.txt')

    def run(self):
        avg = 0.0
        elements = 0
        sumval = 0.0

        # Target objects are a file system/format abstraction and this will return a file stream object
        # NOTE: self.input() actually returns the ExperimentStep.output() target
        for line in self.input().open('r'):
            values = line.split(" ")
            avg += float(values[2])
            sumval += float(values[3])
            elements = elements + 1

        # average
        avg = avg / elements

        # save calculated values
        with self.output().open('w') as outfile:
            print(avg, sumval, file=outfile)


if __name__ == '__main__':
    luigi.run()
