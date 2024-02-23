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

import unittest
import os
import sys
import pickle
import trun
import trun.contrib.hdfs
from trun.mock import MockTarget
from helpers import with_config, temporary_unloaded_module
from trun.contrib.external_program import ExternalProgramRunError
from trun.contrib.spark import SparkSubmitStep, PySparkStep
from mock import mock, patch, call, MagicMock
from functools import partial
from multiprocessing import Value
from subprocess import Popen
from io import BytesIO

import pytest


def poll_generator():
    yield None
    yield 1


def setup_run_process(proc):
    poll_gen = poll_generator()
    proc.return_value.poll = lambda: next(poll_gen)
    proc.return_value.returncode = 0
    proc.return_value.stdout = BytesIO()
    proc.return_value.stderr = BytesIO()


class TestSparkSubmitStep(SparkSubmitStep):
    name = "AppName"
    entry_class = "org.test.MyClass"
    jars = ["jars/my.jar"]
    py_files = ["file1.py", "file2.py"]
    files = ["file1", "file2"]
    conf = {"Prop": "Value"}
    properties_file = "conf/spark-defaults.conf"
    driver_memory = "4G"
    driver_java_options = "-Xopt"
    driver_library_path = "library/path"
    driver_class_path = "class/path"
    executor_memory = "8G"
    driver_cores = 8
    supervise = True
    total_executor_cores = 150
    executor_cores = 10
    queue = "queue"
    num_executors = 2
    archives = ["archive1", "archive2"]
    app = "file"
    pyspark_python = '/a/b/c'
    pyspark_driver_python = '/b/c/d'
    hadoop_user_name = 'trunuser'

    def app_options(self):
        return ["arg1", "arg2"]

    def output(self):
        return trun.LocalTarget('output')


class TestDefaultSparkSubmitStep(SparkSubmitStep):
    app = 'test.py'

    def output(self):
        return trun.LocalTarget('output')


class TestPySparkStep(PySparkStep):

    def input(self):
        return MockTarget('input')

    def output(self):
        return MockTarget('output')

    def main(self, sc, *args):
        sc.textFile(self.input().path).saveAsTextFile(self.output().path)


class TestPySparkSessionStep(PySparkStep):
    def input(self):
        return MockTarget('input')

    def output(self):
        return MockTarget('output')

    def main(self, spark, *args):
        spark.sql(self.input().path).write.saveAsTable(self.output().path)


class MessyNamePySparkStep(TestPySparkStep):
    name = 'AppName(a,b,c,1:2,3/4)'


@pytest.mark.apache
class SparkSubmitStepTest(unittest.TestCase):
    ss = 'ss-stub'

    @with_config(
        {'spark': {'spark-submit': ss, 'master': "yarn-client", 'hadoop-conf-dir': 'path', 'deploy-mode': 'client'}})
    @patch('trun.contrib.external_program.subprocess.Popen')
    def test_run(self, proc):
        setup_run_process(proc)
        job = TestSparkSubmitStep()
        job.run()

        self.assertEqual(proc.call_args[0][0],
                         ['ss-stub', '--master', 'yarn-client', '--deploy-mode', 'client', '--name', 'AppName',
                          '--class', 'org.test.MyClass', '--jars', 'jars/my.jar', '--py-files', 'file1.py,file2.py',
                          '--files', 'file1,file2', '--archives', 'archive1,archive2', '--conf', 'Prop=Value',
                          '--conf', 'spark.pyspark.python=/a/b/c', '--conf', 'spark.pyspark.driver.python=/b/c/d',
                          '--properties-file', 'conf/spark-defaults.conf', '--driver-memory', '4G',
                          '--driver-java-options', '-Xopt',
                          '--driver-library-path', 'library/path', '--driver-class-path', 'class/path',
                          '--executor-memory', '8G',
                          '--driver-cores', '8', '--supervise', '--total-executor-cores', '150', '--executor-cores',
                          '10',
                          '--queue', 'queue', '--num-executors', '2', 'file', 'arg1', 'arg2'])

    @with_config({'spark': {'hadoop-conf-dir': 'path'}})
    @patch('trun.contrib.external_program.subprocess.Popen')
    def test_environment_is_set_correctly(self, proc):
        setup_run_process(proc)
        job = TestSparkSubmitStep()
        job.run()

        assert job._conf == {
            'Prop': 'Value',
            'spark.pyspark.python': '/a/b/c',
            'spark.pyspark.driver.python': '/b/c/d'
        }
        assert job.program_environment()['HADOOP_USER_NAME'] == 'trunuser'
        self.assertIn('HADOOP_CONF_DIR', proc.call_args[1]['env'])
        self.assertEqual(proc.call_args[1]['env']['HADOOP_CONF_DIR'], 'path')

    @with_config(
        {'spark': {'spark-submit': ss, 'master': 'spark://host:7077', 'conf': 'prop1=val1', 'jars': 'jar1.jar,jar2.jar',
                   'files': 'file1,file2', 'py-files': 'file1.py,file2.py', 'archives': 'archive1'}})
    @patch('trun.contrib.external_program.subprocess.Popen')
    def test_defaults(self, proc):
        proc.return_value.returncode = 0
        job = TestDefaultSparkSubmitStep()
        job.run()
        self.assertEqual(proc.call_args[0][0],
                         ['ss-stub', '--master', 'spark://host:7077', '--jars', 'jar1.jar,jar2.jar',
                          '--py-files', 'file1.py,file2.py', '--files', 'file1,file2', '--archives', 'archive1',
                          '--conf', 'prop1=val1', 'test.py'])

    @patch('trun.contrib.external_program.logger')
    @patch('trun.contrib.external_program.tempfile.TemporaryFile')
    @patch('trun.contrib.external_program.subprocess.Popen')
    def test_handle_failed_job(self, proc, file, logger):
        proc.return_value.returncode = 1
        file.return_value = BytesIO(b'spark test error')
        try:
            job = TestSparkSubmitStep()
            job.run()
        except ExternalProgramRunError as e:
            self.assertEqual(e.err, 'spark test error')
            self.assertIn('spark test error', str(e))
            self.assertIn(call.info('Program stderr:\nspark test error'),
                          logger.mock_calls)
        else:
            self.fail("Should have thrown ExternalProgramRunError")

    @patch('trun.contrib.external_program.logger')
    @patch('trun.contrib.external_program.tempfile.TemporaryFile')
    @patch('trun.contrib.external_program.subprocess.Popen')
    def test_dont_log_stderr_on_success(self, proc, file, logger):
        proc.return_value.returncode = 0
        file.return_value = BytesIO(b'spark normal error output')
        job = TestSparkSubmitStep()
        job.run()

        self.assertNotIn(call.info(
            'Program stderr:\nspark normal error output'),
            logger.mock_calls)

    @patch('trun.contrib.external_program.subprocess.Popen')
    def test_app_must_be_set(self, proc):
        with self.assertRaises(NotImplementedError):
            job = SparkSubmitStep()
            job.run()

    @patch('trun.contrib.external_program.subprocess.Popen')
    def test_app_interruption(self, proc):

        def interrupt():
            raise KeyboardInterrupt()

        proc.return_value.wait = interrupt
        try:
            job = TestSparkSubmitStep()
            job.run()
        except KeyboardInterrupt:
            pass
        proc.return_value.kill.check_called()

    @with_config({'spark': {'deploy-mode': 'client'}})
    def test_tracking_url_is_found_in_stderr_client_mode(self):
        test_val = Value('i', 0)

        def fake_set_tracking_url(val, url):
            if url == "http://10.66.76.155:4040":
                val.value += 1

        def Popen_wrap(args, **kwargs):
            return Popen('>&2 echo "INFO SparkUI: Bound SparkUI to 0.0.0.0, and started at http://10.66.76.155:4040"',
                         shell=True, **kwargs)

        step = TestSparkSubmitStep()
        with mock.patch('trun.contrib.external_program.subprocess.Popen', wraps=Popen_wrap):
            with mock.patch.object(step, 'set_tracking_url', new=partial(fake_set_tracking_url, test_val)):
                step.run()
                self.assertEqual(test_val.value, 1)

    @with_config({'spark': {'deploy-mode': 'cluster'}})
    def test_tracking_url_is_found_in_stderr_cluster_mode(self):
        test_val = Value('i', 0)

        def fake_set_tracking_url(val, url):
            if url == "https://127.0.0.1:4040":
                val.value += 1

        def Popen_wrap(args, **kwargs):
            return Popen('>&2 echo "tracking URL: https://127.0.0.1:4040"', shell=True, **kwargs)

        step = TestSparkSubmitStep()
        with mock.patch('trun.contrib.external_program.subprocess.Popen', wraps=Popen_wrap):
            with mock.patch.object(step, 'set_tracking_url', new=partial(fake_set_tracking_url, test_val)):
                step.run()
                self.assertEqual(test_val.value, 1)


@pytest.mark.apache
class PySparkStepTest(unittest.TestCase):
    ss = 'ss-stub'

    @with_config({'spark': {'spark-submit': ss, 'master': "spark://host:7077", 'deploy-mode': 'client'}})
    @patch('trun.contrib.external_program.subprocess.Popen')
    def test_run(self, proc):
        setup_run_process(proc)
        job = TestPySparkStep()
        job.run()
        proc_arg_list = proc.call_args[0][0]
        self.assertEqual(proc_arg_list[0:7],
                         ['ss-stub', '--master', 'spark://host:7077', '--deploy-mode', 'client', '--name',
                          'TestPySparkStep'])
        self.assertTrue(os.path.exists(proc_arg_list[7]))
        self.assertTrue(proc_arg_list[8].endswith('TestPySparkStep.pickle'))

    @with_config({'spark': {'spark-submit': ss, 'master': "spark://host:7077", 'deploy-mode': 'client'}})
    @patch('trun.contrib.external_program.subprocess.Popen')
    def test_run_with_pickle_dump(self, proc):
        setup_run_process(proc)
        job = TestPySparkStep()
        trun.build([job], local_scheduler=True)
        self.assertEqual(proc.call_count, 1)
        proc_arg_list = proc.call_args[0][0]
        self.assertEqual(proc_arg_list[0:7],
                         ['ss-stub', '--master', 'spark://host:7077', '--deploy-mode', 'client', '--name',
                          'TestPySparkStep'])
        self.assertTrue(os.path.exists(proc_arg_list[7]))
        self.assertTrue(proc_arg_list[8].endswith('TestPySparkStep.pickle'))

    @with_config({'spark': {'spark-submit': ss, 'master': "spark://host:7077", 'deploy-mode': 'cluster'}})
    @patch('trun.contrib.external_program.subprocess.Popen')
    def test_run_with_cluster(self, proc):
        setup_run_process(proc)
        job = TestPySparkStep()
        job.run()
        proc_arg_list = proc.call_args[0][0]
        self.assertEqual(proc_arg_list[0:8],
                         ['ss-stub', '--master', 'spark://host:7077', '--deploy-mode', 'cluster', '--name',
                          'TestPySparkStep', '--files'])
        self.assertTrue(proc_arg_list[8].endswith('TestPySparkStep.pickle'))
        self.assertTrue(os.path.exists(proc_arg_list[9]))
        self.assertEqual('TestPySparkStep.pickle', proc_arg_list[10])

    @patch.dict('sys.modules', {'pyspark': MagicMock()})
    @patch('pyspark.SparkContext')
    def test_pyspark_runner(self, spark_context):
        sc = spark_context.return_value

        def mock_spark_submit(step):
            from trun.contrib.pyspark_runner import PySparkRunner
            PySparkRunner(*step.app_command()[1:]).run()
            # Check py-package exists
            self.assertTrue(os.path.exists(sc.addPyFile.call_args[0][0]))
            # Check that main module containing the step exists.
            run_path = os.path.dirname(step.app_command()[1])
            self.assertTrue(os.path.exists(os.path.join(run_path, os.path.basename(__file__))))
            # Check that the python path contains the run_path
            self.assertTrue(run_path in sys.path)
            # Check if find_class finds the class for the correct module name.
            with open(step.app_command()[1], 'rb') as fp:
                self.assertTrue(pickle.Unpickler(fp).find_class('spark_test', 'TestPySparkStep'))

        with patch.object(SparkSubmitStep, 'run', mock_spark_submit):
            job = TestPySparkStep()
            with temporary_unloaded_module(b'') as step_module:
                with_config({'spark': {'py-packages': step_module}})(job.run)()

        sc.textFile.assert_called_with('input')
        sc.textFile.return_value.saveAsTextFile.assert_called_with('output')
        sc.stop.assert_called_once_with()

    def test_pyspark_session_runner_use_spark_session_true(self):
        pyspark = MagicMock()
        pyspark.__version__ = '2.1.0'
        pyspark_sql = MagicMock()
        with patch.dict(sys.modules, {'pyspark': pyspark, 'pyspark.sql': pyspark_sql}):
            spark = pyspark_sql.SparkSession.builder.config.return_value.enableHiveSupport.return_value.getOrCreate.return_value
            sc = spark.sparkContext

            def mock_spark_submit(step):
                from trun.contrib.pyspark_runner import PySparkSessionRunner
                PySparkSessionRunner(*step.app_command()[1:]).run()
                # Check py-package exists
                self.assertTrue(os.path.exists(sc.addPyFile.call_args[0][0]))
                # Check that main module containing the step exists.
                run_path = os.path.dirname(step.app_command()[1])
                self.assertTrue(os.path.exists(os.path.join(run_path, os.path.basename(__file__))))
                # Check that the python path contains the run_path
                self.assertTrue(run_path in sys.path)
                # Check if find_class finds the class for the correct module name.
                with open(step.app_command()[1], 'rb') as fp:
                    self.assertTrue(pickle.Unpickler(fp).find_class('spark_test', 'TestPySparkSessionStep'))

            with patch.object(SparkSubmitStep, 'run', mock_spark_submit):
                job = TestPySparkSessionStep()
                with temporary_unloaded_module(b'') as step_module:
                    with_config({'spark': {'py-packages': step_module}})(job.run)()

            spark.sql.assert_called_with('input')
            spark.sql.return_value.write.saveAsTable.assert_called_with('output')
            spark.stop.assert_called_once_with()

    def test_pyspark_session_runner_use_spark_session_true_spark1(self):
        pyspark = MagicMock()
        pyspark.__version__ = '1.6.3'
        pyspark_sql = MagicMock()
        with patch.dict(sys.modules, {'pyspark': pyspark, 'pyspark.sql': pyspark_sql}):
            def mock_spark_submit(step):
                from trun.contrib.pyspark_runner import PySparkSessionRunner
                self.assertRaises(RuntimeError, PySparkSessionRunner(*step.app_command()[1:]).run)

            with patch.object(SparkSubmitStep, 'run', mock_spark_submit):
                job = TestPySparkSessionStep()
                with temporary_unloaded_module(b'') as step_module:
                    with_config({'spark': {'py-packages': step_module}})(job.run)()

    @patch('trun.contrib.external_program.subprocess.Popen')
    def test_name_cleanup(self, proc):
        setup_run_process(proc)
        job = MessyNamePySparkStep()
        job.run()
        assert 'AppName_a_b_c_1_2_3_4_' in job.run_path
