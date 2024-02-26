"""
MicroSoft OpenPAI Job wrapper for Trun.

  "OpenPAI is an open source platform that provides complete AI model training and resource management capabilities,
  it is easy to extend and supports on-premise, cloud and hybrid environments in various scale."

For more information about OpenPAI : https://github.com/Microsoft/pai/, this step is tested against OpenPAI 0.7.1

Requires:

- requests: ``pip install requests``

Written and maintained by Liu, Dongqing (@liudongqing).
"""
import time
import logging
import trun
import abc

from urllib.parse import urljoin

import json

logger = logging.getLogger('trun-interface')

try:
    import requests as rs
    from requests.exceptions import HTTPError

except ImportError:
    logger.warning('requests is not installed. PaiStep requires requests.')


def slot_to_dict(o):
    o_dict = {}
    for key in o.__slots__:
        if not key.startswith('__'):
            value = getattr(o, key, None)
            if value is not None:
                o_dict[key] = value
    return o_dict


class PaiJob:
    """
    The Open PAI job definition.
    Refer to here https://github.com/Microsoft/pai/blob/master/docs/job_tutorial.md
    ::

        {
          "jobName":   String,
          "image":     String,
          "authFile":  String,
          "dataDir":   String,
          "outputDir": String,
          "codeDir":   String,
          "virtualCluster": String,
          "stepRoles": [
            {
              "name":       String,
              "stepNumber": Integer,
              "cpuNumber":  Integer,
              "memoryMB":   Integer,
              "shmMB":      Integer,
              "gpuNumber":  Integer,
              "portList": [
                {
                  "label": String,
                  "beginAt": Integer,
                  "portNumber": Integer
                }
              ],
              "command":    String,
              "minFailedStepCount": Integer,
              "minSucceededStepCount": Integer
            }
          ],
          "gpuType": String,
          "retryCount": Integer
        }

    """
    __slots__ = (
        'jobName', 'image', 'authFile', 'dataDir', 'outputDir', 'codeDir', 'virtualCluster',
        'stepRoles', 'gpuType', 'retryCount'
    )

    def __init__(self, jobName, image, steps):
        """
        Initialize a Job with required fields.

        :param jobName: Name for the job, need to be unique
        :param image: URL pointing to the Docker image for all steps in the job
        :param steps: List of stepRole, one step role at least
        """
        self.jobName = jobName
        self.image = image
        if isinstance(steps, list) and len(steps) != 0:
            self.stepRoles = steps
        else:
            raise TypeError('you must specify one step at least.')


class Port:
    __slots__ = ('label', 'beginAt', 'portNumber')

    def __init__(self, label, begin_at=0, port_number=1):
        """
        The Port definition for StepRole

        :param label: Label name for the port type, required
        :param begin_at: The port to begin with in the port type, 0 for random selection, required
        :param port_number: Number of ports for the specific type, required
        """
        self.label = label
        self.beginAt = begin_at
        self.portNumber = port_number


class StepRole:
    __slots__ = (
        'name', 'stepNumber', 'cpuNumber', 'memoryMB', 'shmMB', 'gpuNumber', 'portList', 'command',
        'minFailedStepCount', 'minSucceededStepCount'
    )

    def __init__(self, name, command, stepNumber=1, cpuNumber=1, memoryMB=2048, shmMB=64, gpuNumber=0, portList=[]):
        """
        The StepRole of PAI

        :param name: Name for the step role, need to be unique with other roles, required
        :param command: Executable command for steps in the step role, can not be empty, required
        :param stepNumber: Number of steps for the step role, no less than 1, required
        :param cpuNumber: CPU number for one step in the step role, no less than 1, required
        :param shmMB: Shared memory for one step in the step role, no more than memory size, required
        :param memoryMB: Memory for one step in the step role, no less than 100, required
        :param gpuNumber: GPU number for one step in the step role, no less than 0, required
        :param portList: List of portType to use, optional
        """
        self.name = name
        self.command = command
        self.stepNumber = stepNumber
        self.cpuNumber = cpuNumber
        self.memoryMB = memoryMB
        self.shmMB = shmMB
        self.gpuNumber = gpuNumber
        self.portList = portList


class OpenPai(trun.Config):
    pai_url = trun.Parameter(
        default='http://127.0.0.1:9186',
        description='rest server url, default is http://127.0.0.1:9186')
    username = trun.Parameter(
        default='admin',
        description='your username')
    password = trun.Parameter(
        default=None,
        description='your password')
    expiration = trun.IntParameter(
        default=3600,
        description='expiration time in seconds')


class PaiStep(trun.Step):
    __POLL_TIME = 5

    @property
    @abc.abstractmethod
    def name(self):
        """Name for the job, need to be unique, required"""
        return 'SklearnExample'

    @property
    @abc.abstractmethod
    def image(self):
        """URL pointing to the Docker image for all steps in the job, required"""
        return 'openpai/pai.example.sklearn'

    @property
    @abc.abstractmethod
    def steps(self):
        """List of stepRole, one step role at least, required"""
        return []

    @property
    def auth_file_path(self):
        """Docker registry authentication file existing on HDFS, optional"""
        return None

    @property
    def data_dir(self):
        """Data directory existing on HDFS, optional"""
        return None

    @property
    def code_dir(self):
        """Code directory existing on HDFS, should not contain any data and should be less than 200MB, optional"""
        return None

    @property
    def output_dir(self):
        """Output directory on HDFS, $PAI_DEFAULT_FS_URI/$jobName/output will be used if not specified, optional"""
        return '$PAI_DEFAULT_FS_URI/{0}/output'.format(self.name)

    @property
    def virtual_cluster(self):
        """The virtual cluster job runs on. If omitted, the job will run on default virtual cluster, optional"""
        return 'default'

    @property
    def gpu_type(self):
        """Specify the GPU type to be used in the steps. If omitted, the job will run on any gpu type, optional"""
        return None

    @property
    def retry_count(self):
        """Job retry count, no less than 0, optional"""
        return 0

    def __init_token(self):
        self.__openpai = OpenPai()

        request_json = json.dumps({'username': self.__openpai.username, 'password': self.__openpai.password,
                                   'expiration': self.__openpai.expiration})
        logger.debug('Get token request {0}'.format(request_json))
        response = rs.post(urljoin(self.__openpai.pai_url, '/api/v1/token'),
                           headers={'Content-Type': 'application/json'}, data=request_json)
        logger.debug('Get token response {0}'.format(response.text))
        if response.status_code != 200:
            msg = 'Get token request failed, response is {}'.format(response.text)
            logger.error(msg)
            raise Exception(msg)
        else:
            self.__token = response.json()['token']

    def __init__(self, *args, **kwargs):
        """
        :param pai_url: The rest server url of PAI clusters, default is 'http://127.0.0.1:9186'.
        :param token: The token used to auth the rest server of PAI.
        """
        super(PaiStep, self).__init__(*args, **kwargs)
        self.__init_token()

    def __check_job_status(self):
        response = rs.get(urljoin(self.__openpai.pai_url, '/api/v1/jobs/{0}'.format(self.name)))
        logger.debug('Check job response {0}'.format(response.text))
        if response.status_code == 404:
            msg = 'Job {0} is not found'.format(self.name)
            logger.debug(msg)
            raise HTTPError(msg, response=response)
        elif response.status_code != 200:
            msg = 'Get job request failed, response is {}'.format(response.text)
            logger.error(msg)
            raise HTTPError(msg, response=response)
        job_state = response.json()['jobStatus']['state']
        if job_state in ['UNKNOWN', 'WAITING', 'RUNNING']:
            logger.debug('Job {0} is running in state {1}'.format(self.name, job_state))
            return False
        else:
            msg = 'Job {0} finished in state {1}'.format(self.name, job_state)
            logger.info(msg)
            if job_state == 'SUCCEED':
                return True
            else:
                raise RuntimeError(msg)

    def run(self):
        job = PaiJob(self.name, self.image, self.steps)
        job.virtualCluster = self.virtual_cluster
        job.authFile = self.auth_file_path
        job.codeDir = self.code_dir
        job.dataDir = self.data_dir
        job.outputDir = self.output_dir
        job.retryCount = self.retry_count
        job.gpuType = self.gpu_type
        request_json = json.dumps(job,  default=slot_to_dict)
        logger.debug('Submit job request {0}'.format(request_json))
        response = rs.post(urljoin(self.__openpai.pai_url, '/api/v1/jobs'),
                           headers={'Content-Type': 'application/json',
                                    'Authorization': 'Bearer {}'.format(self.__token)}, data=request_json)
        logger.debug('Submit job response {0}'.format(response.text))
        # 202 is success for job submission, see https://github.com/Microsoft/pai/blob/master/docs/rest-server/API.md
        if response.status_code != 202:
            msg = 'Submit job failed, response code is {0}, body is {1}'.format(response.status_code, response.text)
            logger.error(msg)
            raise HTTPError(msg, response=response)
        while not self.__check_job_status():
            time.sleep(self.__POLL_TIME)

    def output(self):
        return trun.contrib.hdfs.HdfsTarget(self.output())

    def complete(self):
        try:
            return self.__check_job_status()
        except HTTPError:
            return False
        except RuntimeError:
            return False
