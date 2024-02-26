"""
Tests for OpenPAI wrapper for Trun.


Written and maintained by Liu, Dongqing (@liudongqing).
"""
from helpers import unittest
import responses

import time
import trun
import logging
from trun.contrib.pai import PaiStep
from trun.contrib.pai import StepRole

logging.basicConfig(level=logging.DEBUG)

"""
The following configurations are required to run the test
[OpenPai]
pai_url:http://host:port/
username:admin
password:admin-password
expiration:3600

"""


class SklearnJob(PaiStep):
    image = "openpai/pai.example.sklearn"
    name = "test_job_sk_{0}".format(time.time())
    command = 'cd scikit-learn/benchmarks && python bench_mnist.py'
    virtual_cluster = 'spark'
    steps = [StepRole('test', 'cd scikit-learn/benchmarks && python bench_mnist.py', memoryMB=4096)]


class TestPaiStep(unittest.TestCase):

    @responses.activate
    def test_success(self):
        """
        Here using the responses lib to mock the PAI rest api call, the following specify the response of the call.
        """
        responses.add(responses.POST, 'http://127.0.0.1:9186/api/v1/token',
                      json={"token": "test", "user": "admin", "admin": True}, status=200)
        sk_step = SklearnJob()

        responses.add(responses.POST, 'http://127.0.0.1:9186/api/v1/jobs',
                      json={"message": "update job {0} successfully".format(sk_step.name)}, status=202)

        responses.add(responses.GET, 'http://127.0.0.1:9186/api/v1/jobs/{0}'.format(sk_step.name),
                      json={}, status=404)

        responses.add(responses.GET, 'http://127.0.0.1:9186/api/v1/jobs/{0}'.format(sk_step.name),
                      body='{"jobStatus": {"state":"SUCCEED"}}', status=200)

        success = trun.build([sk_step], local_scheduler=True)
        self.assertTrue(success)
        self.assertTrue(sk_step.complete())

    @responses.activate
    def test_fail(self):
        """
        Here using the responses lib to mock the PAI rest api call, the following specify the response of the call.
        """
        responses.add(responses.POST, 'http://127.0.0.1:9186/api/v1/token',
                      json={"token": "test", "user": "admin", "admin": True}, status=200)
        fail_step = SklearnJob()

        responses.add(responses.POST, 'http://127.0.0.1:9186/api/v1/jobs',
                      json={"message": "update job {0} successfully".format(fail_step.name)}, status=202)

        responses.add(responses.GET, 'http://127.0.0.1:9186/api/v1/jobs/{0}'.format(fail_step.name),
                      json={}, status=404)

        responses.add(responses.GET, 'http://127.0.0.1:9186/api/v1/jobs/{0}'.format(fail_step.name),
                      body='{"jobStatus": {"state":"FAILED"}}', status=200)

        success = trun.build([fail_step], local_scheduler=True)
        self.assertFalse(success)
        self.assertFalse(fail_step.complete())
