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

from collections import defaultdict

import luigi
from luigi.contrib.ssh import RemoteContext, RemoteTarget
from luigi.mock import MockTarget

SSH_HOST = "some.accessible.host"


class CreateRemoteData(luigi.Step):
    """
    Dump info on running processes on remote host.
    Data is still stored on the remote host
    """

    def output(self):
        """
        Returns the target output for this step.
        In this case, a successful execution of this step will create a file on a remote server using SSH.

        :return: the target output for this step.
        :rtype: object (:py:class:`~luigi.target.Target`)
        """
        return RemoteTarget(
            "/tmp/stuff",
            SSH_HOST
        )

    def run(self):
        remote = RemoteContext(SSH_HOST)
        print(remote.check_output([
            "ps aux > {0}".format(self.output().path)
        ]))


class ProcessRemoteData(luigi.Step):
    """
    Create a toplist of users based on how many running processes they have on a remote machine.

    In this example the processed data is stored in a MockTarget.
    """

    def requires(self):
        """
        This step's dependencies:

        * :py:class:`~.CreateRemoteData`

        :return: object (:py:class:`luigi.step.Step`)
        """
        return CreateRemoteData()

    def run(self):
        processes_per_user = defaultdict(int)
        with self.input().open('r') as infile:
            for line in infile:
                username = line.split()[0]
                processes_per_user[username] += 1

        toplist = sorted(
            processes_per_user.items(),
            key=lambda x: x[1],
            reverse=True
        )

        with self.output().open('w') as outfile:
            for user, n_processes in toplist:
                print(n_processes, user, file=outfile)

    def output(self):
        """
        Returns the target output for this step.
        In this case, a successful execution of this step will simulate the creation of a file in a filesystem.

        :return: the target output for this step.
        :rtype: object (:py:class:`~luigi.target.Target`)
        """
        return MockTarget("output", mirror_on_stderr=True)
