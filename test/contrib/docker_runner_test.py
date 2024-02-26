

"""
Tests for Docker container wrapper for Trun.


Requires:

- docker: ``pip install docker``

Written and maintained by Andrea Pierleoni (@apierleoni).
Contributions by Eliseo Papa (@elipapa)
"""
import tempfile
from helpers import unittest
from tempfile import NamedTemporaryFile

import trun
import logging
from trun.contrib.docker_runner import DockerStep

import pytest

logger = logging.getLogger('trun-interface')

try:
    import docker
    from docker.errors import ContainerError, ImageNotFound
    client = docker.from_env()
    client.version()
except ImportError:
    raise unittest.SkipTest('Unable to load docker module')
except Exception:
    raise unittest.SkipTest('Unable to connect to docker daemon')

tempfile.tempdir = '/tmp'  # set it explicitly to make it work out of the box in mac os
local_file = NamedTemporaryFile()
local_file.write(b'this is a test file\n')
local_file.flush()


class SuccessJob(DockerStep):
    image = "busybox:latest"
    name = "SuccessJob"


class FailJobImageNotFound(DockerStep):
    image = "image-does-not-exists"
    name = "FailJobImageNotFound"


class FailJobContainer(DockerStep):
    image = "busybox"
    name = "FailJobContainer"
    command = 'cat this-file-does-not-exist'


class WriteToTmpDir(DockerStep):
    image = "busybox"
    name = "WriteToTmpDir"
    container_tmp_dir = '/tmp/trun-test'
    command = 'test -d  /tmp/trun-test'
    # command = 'test -d $TRUN_TMP_DIR'# && echo ok >$TRUN_TMP_DIR/test'


class MountLocalFileAsVolume(DockerStep):
    image = "busybox"
    name = "MountLocalFileAsVolume"
    # volumes= {'/tmp/local_file_test': {'bind': local_file.name, 'mode': 'rw'}}
    binds = [local_file.name + ':/tmp/local_file_test']
    command = 'test -f /tmp/local_file_test'


class MountLocalFileAsVolumeWithParam(DockerStep):
    dummyopt = trun.Parameter()
    image = "busybox"
    name = "MountLocalFileAsVolumeWithParam"
    binds = [local_file.name + ':/tmp/local_file_test']
    command = 'test -f /tmp/local_file_test'


class MountLocalFileAsVolumeWithParamRedefProperties(DockerStep):
    dummyopt = trun.Parameter()
    image = "busybox"
    name = "MountLocalFileAsVolumeWithParamRedef"

    @property
    def binds(self):
        return [local_file.name + ':/tmp/local_file_test' + self.dummyopt]

    @property
    def command(self):
        return 'test -f /tmp/local_file_test' + self.dummyopt

    def complete(self):
        return True


class MultipleDockerStep(trun.WrapperStep):
    '''because the volumes property is defined as a list, spinning multiple
    containers led to conflict in the volume binds definition, with multiple
    host directories pointing to the same container directory'''
    def requires(self):
        return [MountLocalFileAsVolumeWithParam(dummyopt=opt)
                for opt in ['one', 'two', 'three']]


class MultipleDockerStepRedefProperties(trun.WrapperStep):
    def requires(self):
        return [MountLocalFileAsVolumeWithParamRedefProperties(dummyopt=opt)
                for opt in ['one', 'two', 'three']]


@pytest.mark.contrib
class TestDockerStep(unittest.TestCase):

    # def tearDown(self):
    #     local_file.close()

    def test_success_job(self):
        success = SuccessJob()
        trun.build([success], local_scheduler=True)
        self.assertTrue(success)

    def test_temp_dir_creation(self):
        writedir = WriteToTmpDir()
        writedir.run()

    def test_local_file_mount(self):
        localfile = MountLocalFileAsVolume()
        localfile.run()

    def test_fail_job_image_not_found(self):
        fail = FailJobImageNotFound()
        self.assertRaises(ImageNotFound, fail.run)

    def test_fail_job_container(self):
        fail = FailJobContainer()
        self.assertRaises(ContainerError, fail.run)

    def test_multiple_jobs(self):
        worked = MultipleDockerStep()
        trun.build([worked], local_scheduler=True)
        self.assertTrue(worked)

    def test_multiple_jobs2(self):
        worked = MultipleDockerStepRedefProperties()
        trun.build([worked], local_scheduler=True)
        self.assertTrue(worked)
