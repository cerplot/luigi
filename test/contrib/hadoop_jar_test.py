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
import tempfile
import shlex
from helpers import unittest
from trun.contrib.hadoop_jar import HadoopJarJobError, HadoopJarJobStep, fix_paths
from mock import patch, Mock
import pytest


class TestHadoopJarJob(HadoopJarJobStep):
    path = trun.Parameter()

    def jar(self):
        return self.path


class TestMissingJarJob(HadoopJarJobStep):
    pass


class TestRemoteHadoopJarJob(TestHadoopJarJob):
    def ssh(self):
        return {"host": "myhost", "key_file": "file", "username": "user"}


class TestRemoteMissingJarJob(TestHadoopJarJob):
    def ssh(self):
        return {"host": "myhost", "key_file": "file"}


class TestRemoteHadoopJarTwoParamJob(TestRemoteHadoopJarJob):
    param2 = trun.Parameter()


@pytest.mark.apache
class FixPathsTest(unittest.TestCase):
    def test_fix_paths_non_hdfs_target_path(self):
        mock_job = Mock()
        mock_arg = Mock()
        mock_job.args.return_value = [mock_arg]
        mock_arg.path = 'right_path'
        self.assertEqual(([], ['right_path']), fix_paths(mock_job))

    def test_fix_paths_non_hdfs_target_str(self):
        mock_job = Mock()
        mock_arg = Mock(spec=[])
        mock_job.args.return_value = [mock_arg]
        self.assertEqual(([], [str(mock_arg)]), fix_paths(mock_job))


class HadoopJarJobStepTest(unittest.TestCase):
    @patch('trun.contrib.hadoop.run_and_track_hadoop_job')
    def test_good(self, mock_job):
        mock_job.return_value = None
        with tempfile.NamedTemporaryFile() as temp_file:
            step = TestHadoopJarJob(temp_file.name)
            step.run()

    @patch('trun.contrib.hadoop.run_and_track_hadoop_job')
    def test_missing_jar(self, mock_job):
        mock_job.return_value = None
        step = TestMissingJarJob()
        self.assertRaises(HadoopJarJobError, step.run)

    @patch('trun.contrib.hadoop.run_and_track_hadoop_job')
    def test_remote_job(self, mock_job):
        mock_job.return_value = None
        with tempfile.NamedTemporaryFile() as temp_file:
            step = TestRemoteHadoopJarJob(temp_file.name)
            step.run()

    @patch('trun.contrib.hadoop.run_and_track_hadoop_job')
    def test_remote_job_with_space_in_step_id(self, mock_job):
        with tempfile.NamedTemporaryFile() as temp_file:

            def check_space(arr, step_id):
                for a in arr:
                    if a.startswith('hadoop jar'):
                        found = False
                        for x in shlex.split(a):
                            if step_id in x:
                                found = True
                        if not found:
                            raise AssertionError

            step = TestRemoteHadoopJarTwoParamJob(temp_file.name, 'test')
            mock_job.side_effect = lambda x, _: check_space(x, str(step))
            step.run()

    @patch('trun.contrib.hadoop.run_and_track_hadoop_job')
    def test_remote_job_missing_config(self, mock_job):
        mock_job.return_value = None
        with tempfile.NamedTemporaryFile() as temp_file:
            step = TestRemoteMissingJarJob(temp_file.name)
            self.assertRaises(HadoopJarJobError, step.run)
