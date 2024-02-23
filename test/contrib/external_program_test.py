# -*- coding: utf-8 -*-
#
# Copyright 2012-2016 Spotify AB
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
from io import BytesIO
import os
import shutil
import subprocess
import tempfile
from functools import partial
from multiprocessing import Value

from helpers import unittest
import trun
import trun.contrib.hdfs
from trun.contrib.external_program import ExternalProgramStep, ExternalPythonProgramStep
from trun.contrib.external_program import ExternalProgramRunError
from mock import patch, call
from subprocess import Popen
import mock
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


class TestExternalProgramStep(ExternalProgramStep):
    def program_args(self):
        return ['app_path', 'arg1', 'arg2']

    def output(self):
        return trun.LocalTarget('output')


class TestLogStderrOnFailureOnlyStep(TestExternalProgramStep):
    always_log_stderr = False


class TestTouchStep(ExternalProgramStep):
    file_path = trun.Parameter()

    def program_args(self):
        return ['touch', self.output().path]

    def output(self):
        return trun.LocalTarget(self.file_path)


class TestEchoStep(ExternalProgramStep):
    MESSAGE = "Hello, world!"

    def program_args(self):
        return ['echo', self.MESSAGE]


@pytest.mark.contrib
class ExternalProgramStepTest(unittest.TestCase):
    @patch('trun.contrib.external_program.subprocess.Popen')
    def test_run(self, proc):
        setup_run_process(proc)
        job = TestExternalProgramStep()
        job.run()

        self.assertEqual(proc.call_args[0][0],
                         ['app_path', 'arg1', 'arg2'])

    @patch('trun.contrib.external_program.logger')
    @patch('trun.contrib.external_program.tempfile.TemporaryFile')
    @patch('trun.contrib.external_program.subprocess.Popen')
    def test_handle_failed_job(self, proc, file, logger):
        proc.return_value.returncode = 1
        file.return_value = BytesIO(b'stderr')
        try:
            job = TestExternalProgramStep()
            job.run()
        except ExternalProgramRunError as e:
            self.assertEqual(e.err, 'stderr')
            self.assertIn('STDERR: stderr', str(e))
            self.assertIn(call.info('Program stderr:\nstderr'), logger.mock_calls)
        else:
            self.fail('Should have thrown ExternalProgramRunError')

    @patch('trun.contrib.external_program.logger')
    @patch('trun.contrib.external_program.tempfile.TemporaryFile')
    @patch('trun.contrib.external_program.subprocess.Popen')
    def test_always_log_stderr_on_failure(self, proc, file, logger):
        proc.return_value.returncode = 1
        file.return_value = BytesIO(b'stderr')
        with self.assertRaises(ExternalProgramRunError):
            job = TestLogStderrOnFailureOnlyStep()
            job.run()

        self.assertIn(call.info('Program stderr:\nstderr'), logger.mock_calls)

    @patch('trun.contrib.external_program.logger')
    @patch('trun.contrib.external_program.tempfile.TemporaryFile')
    @patch('trun.contrib.external_program.subprocess.Popen')
    def test_log_stderr_on_success_by_default(self, proc, file, logger):
        proc.return_value.returncode = 0
        file.return_value = BytesIO(b'stderr')
        job = TestExternalProgramStep()
        job.run()

        self.assertIn(call.info('Program stderr:\nstderr'), logger.mock_calls)

    def test_capture_output_set_to_false_writes_output_to_stdout(self):

        out = tempfile.TemporaryFile()

        def Popen_wrap(args, **kwargs):
            kwargs.pop('stdout', None)
            return Popen(args, stdout=out, **kwargs)

        with mock.patch('trun.contrib.external_program.subprocess.Popen', wraps=Popen_wrap):
            step = TestEchoStep(capture_output=False)
            step.run()
            stdout = step._clean_output_file(out).strip()
            self.assertEqual(stdout, step.MESSAGE)

    @patch('trun.contrib.external_program.logger')
    @patch('trun.contrib.external_program.tempfile.TemporaryFile')
    @patch('trun.contrib.external_program.subprocess.Popen')
    def test_dont_log_stderr_on_success_if_disabled(self, proc, file, logger):
        proc.return_value.returncode = 0
        file.return_value = BytesIO(b'stderr')
        job = TestLogStderrOnFailureOnlyStep()
        job.run()

        self.assertNotIn(call.info('Program stderr:\nstderr'), logger.mock_calls)

    @patch('trun.contrib.external_program.subprocess.Popen')
    def test_program_args_must_be_implemented(self, proc):
        with self.assertRaises(NotImplementedError):
            job = ExternalProgramStep()
            job.run()

    @patch('trun.contrib.external_program.subprocess.Popen')
    def test_app_interruption(self, proc):

        def interrupt():
            raise KeyboardInterrupt()

        proc.return_value.wait = interrupt
        try:
            job = TestExternalProgramStep()
            job.run()
        except KeyboardInterrupt:
            pass
        proc.return_value.kill.check_called()

    def test_non_mocked_step_run(self):
        # create a tempdir first, to ensure an empty playground for
        # TestTouchStep to create its file in
        tempdir = tempfile.mkdtemp()
        tempfile_path = os.path.join(tempdir, 'testfile')

        try:
            job = TestTouchStep(file_path=tempfile_path)
            job.run()

            self.assertTrue(trun.LocalTarget(tempfile_path).exists())
        finally:
            # clean up temp files even if assertion fails
            shutil.rmtree(tempdir)

    def test_tracking_url_pattern_works_with_capture_output_disabled(self):
        test_val = Value('i', 0)

        def fake_set_tracking_url(val, url):
            if url == "TEXT":
                val.value += 1

        step = TestEchoStep(capture_output=False, stream_for_searching_tracking_url='stdout',
                            tracking_url_pattern=r"SOME (.*)")
        step.MESSAGE = "SOME TEXT"

        with mock.patch.object(step, 'set_tracking_url', new=partial(fake_set_tracking_url, test_val)):
            step.run()
            self.assertEqual(test_val.value, 1)

    def test_tracking_url_pattern_works_with_capture_output_enabled(self):
        test_val = Value('i', 0)

        def fake_set_tracking_url(val, url):
            if url == "THING":
                val.value += 1

        step = TestEchoStep(capture_output=True, stream_for_searching_tracking_url='stdout',
                            tracking_url_pattern=r"ANY(.*)")
        step.MESSAGE = "ANYTHING"

        with mock.patch.object(step, 'set_tracking_url', new=partial(fake_set_tracking_url, test_val)):
            step.run()
            self.assertEqual(test_val.value, 1)

    def test_tracking_url_pattern_works_with_stderr(self):
        test_val = Value('i', 0)

        def fake_set_tracking_url(val, url):
            if url == "THING_ELSE":
                val.value += 1

        def Popen_wrap(args, **kwargs):
            return Popen('>&2 echo "ANYTHING_ELSE"', shell=True, **kwargs)

        step = TestEchoStep(capture_output=True, stream_for_searching_tracking_url='stderr',
                            tracking_url_pattern=r"ANY(.*)")

        with mock.patch('trun.contrib.external_program.subprocess.Popen', wraps=Popen_wrap):
            with mock.patch.object(step, 'set_tracking_url', new=partial(fake_set_tracking_url, test_val)):
                step.run()
                self.assertEqual(test_val.value, 1)

    def test_no_url_searching_is_performed_if_pattern_is_not_set(self):
        def Popen_wrap(args, **kwargs):
            # stdout should not be replaced with pipe if tracking_url_pattern is not set
            self.assertNotEqual(kwargs['stdout'], subprocess.PIPE)
            return Popen(args, **kwargs)

        step = TestEchoStep(capture_output=True, stream_for_searching_tracking_url='stdout')

        with mock.patch('trun.contrib.external_program.subprocess.Popen', wraps=Popen_wrap):
            step.run()

    def test_tracking_url_context_works_without_capture_output(self):
        test_val = Value('i', 0)

        def fake_set_tracking_url(val, url):
            if url == "world":
                val.value += 1

        step = TestEchoStep(capture_output=False, stream_for_searching_tracking_url='stdout',
                            tracking_url_pattern=r"Hello, (.*)!")
        test_args = list(map(str, step.program_args()))
        with mock.patch.object(step, 'set_tracking_url', new=partial(fake_set_tracking_url, test_val)):
            with step._proc_with_tracking_url_context(proc_args=test_args, proc_kwargs={}) as proc:
                proc.wait()
        self.assertEqual(test_val.value, 1)

    def test_tracking_url_context_works_correctly_when_logs_output_pattern_to_url_is_not_default(self):

        class _Step(TestEchoStep):
            def build_tracking_url(self, logs_output):
                return 'The {} is mine'.format(logs_output)

        test_val = Value('i', 0)

        def fake_set_tracking_url(val, url):
            if url == "The world is mine":
                val.value += 1

        step = _Step(
            capture_output=False,
            stream_for_searching_tracking_url='stdout',
            tracking_url_pattern=r"Hello, (.*)!"
        )

        test_args = list(map(str, step.program_args()))

        with mock.patch.object(step, 'set_tracking_url', new=partial(fake_set_tracking_url, test_val)):
            with step._proc_with_tracking_url_context(proc_args=test_args, proc_kwargs={}) as proc:
                proc.wait()
        self.assertEqual(test_val.value, 1)


class TestExternalPythonProgramStep(ExternalPythonProgramStep):
    virtualenv = '/path/to/venv'
    extra_pythonpath = '/extra/pythonpath'

    def program_args(self):
        return ["app_path", "arg1", "arg2"]

    def output(self):
        return trun.LocalTarget('output')


@pytest.mark.contrib
class ExternalPythonProgramStepTest(unittest.TestCase):
    @patch.dict('os.environ', {'OTHERVAR': 'otherval'}, clear=True)
    @patch('trun.contrib.external_program.subprocess.Popen')
    def test_original_environment_is_kept_intact(self, proc):
        setup_run_process(proc)

        job = TestExternalPythonProgramStep()
        job.run()

        proc_env = proc.call_args[1]['env']
        self.assertIn('PYTHONPATH', proc_env)
        self.assertIn('OTHERVAR', proc_env)

    @patch.dict('os.environ', {'PATH': '/base/path'}, clear=True)
    @patch('trun.contrib.external_program.subprocess.Popen')
    def test_venv_is_set_and_prepended_to_path(self, proc):
        setup_run_process(proc)

        job = TestExternalPythonProgramStep()
        job.run()

        proc_env = proc.call_args[1]['env']
        self.assertIn('PATH', proc_env)
        self.assertTrue(proc_env['PATH'].startswith('/path/to/venv/bin'))
        self.assertTrue(proc_env['PATH'].endswith('/base/path'))
        self.assertIn('VIRTUAL_ENV', proc_env)
        self.assertEqual(proc_env['VIRTUAL_ENV'], '/path/to/venv')

    @patch.dict('os.environ', {}, clear=True)
    @patch('trun.contrib.external_program.subprocess.Popen')
    def test_pythonpath_is_set_if_empty(self, proc):
        setup_run_process(proc)

        job = TestExternalPythonProgramStep()
        job.run()

        proc_env = proc.call_args[1]['env']
        self.assertIn('PYTHONPATH', proc_env)
        self.assertTrue(proc_env['PYTHONPATH'].startswith('/extra/pythonpath'))

    @patch.dict('os.environ', {'PYTHONPATH': '/base/pythonpath'}, clear=True)
    @patch('trun.contrib.external_program.subprocess.Popen')
    def test_pythonpath_is_prepended_if_not_empty(self, proc):
        setup_run_process(proc)

        job = TestExternalPythonProgramStep()
        job.run()

        proc_env = proc.call_args[1]['env']
        self.assertIn('PYTHONPATH', proc_env)
        self.assertTrue(proc_env['PYTHONPATH'].startswith('/extra/pythonpath'))
        self.assertTrue(proc_env['PYTHONPATH'].endswith('/base/pythonpath'))
