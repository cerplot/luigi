

"""
Docker container wrapper for Trun.

Enables running a docker container as a step in trun.
This wrapper uses the Docker Python SDK to communicate directly with the
Docker API avoiding the common pattern to invoke the docker client
from the command line. Using the SDK it is possible to detect and properly
handle errors occurring when pulling, starting or running the containers.
On top of this, it is possible to mount a single file in the container
and a temporary directory is created on the host and mounted allowing
the handling of files bigger than the container limit.

Requires:

- docker: ``pip install docker``

Written and maintained by Andrea Pierleoni (@apierleoni).
Contributions by Eliseo Papa (@elipapa).
"""
from tempfile import mkdtemp
import logging
import trun

from trun.local_target import LocalFileSystem

logger = logging.getLogger('trun-interface')

try:
    import docker
    from docker.errors import ContainerError, ImageNotFound, APIError

except ImportError:
    logger.warning('docker is not installed. DockerStep requires docker.')
    docker = None

# TODO: may need to implement this logic for remote hosts
# class dockerconfig(trun.Config):
#     '''
#     this class allows to use the trun.cfg file to specify the path to the docker config.json.
#     The docker client should look by default in the main directory,
#      but on different systems this may need to be specified.
#     '''
#     docker_config_path = trun.Parameter(
#         default="~/.docker/config.json",
#         description="Path to dockercfg file for authentication")


class DockerStep(trun.Step):

    @property
    def image(self):
        return 'alpine'

    @property
    def command(self):
        return "echo hello world"

    @property
    def name(self):
        return None

    @property
    def host_config_options(self):
        '''
        Override this to specify host_config options like gpu requests or shm
        size e.g. `{"device_requests": [docker.types.DeviceRequest(count=1, capabilities=[["gpu"]])]}`

        See https://docker-py.readthedocs.io/en/stable/api.html#docker.api.container.ContainerApiMixin.create_host_config
        '''
        return {}

    @property
    def container_options(self):
        '''
        Override this to specify container options like user or ports e.g.
        `{"user": f"{os.getuid()}:{os.getgid()}"}`

        See https://docker-py.readthedocs.io/en/stable/api.html#docker.api.container.ContainerApiMixin.create_container
        '''
        return {}

    @property
    def environment(self):
        return {}

    @property
    def container_tmp_dir(self):
        return '/tmp/trun'

    @property
    def binds(self):
        '''
        Override this to mount local volumes, in addition to the /tmp/trun
        which gets defined by default. This should return a list of strings.
        e.g. ['/hostpath1:/containerpath1', '/hostpath2:/containerpath2']
        '''
        return None

    @property
    def network_mode(self):
        return ''

    @property
    def docker_url(self):
        return None

    @property
    def auto_remove(self):
        return True

    @property
    def force_pull(self):
        return False

    @property
    def mount_tmp(self):
        return True

    def __init__(self, *args, **kwargs):
        '''
        When a new instance of the DockerStep class gets created:
        - call the parent class __init__ method
        - start the logger
        - init an instance of the docker client
        - create a tmp dir
        - add the temp dir to the volume binds specified in the step
        '''
        super(DockerStep, self).__init__(*args, **kwargs)
        self.__logger = logger

        '''init docker client
        using the low level API as the higher level API does not allow to mount single
        files as volumes
        '''
        self._client = docker.APIClient(self.docker_url)

        # add latest tag if nothing else is specified by step
        if ':' not in self.image:
            self._image = ':'.join([self.image, 'latest'])
        else:
            self._image = self.image

        if self.mount_tmp:
            # create a tmp_dir, NOTE: /tmp needs to be specified for it to work on
            # macOS, despite what the python documentation says
            self._host_tmp_dir = mkdtemp(suffix=self.step_id,
                                         prefix='trun-docker-tmp-dir-',
                                         dir='/tmp')

            self._binds = ['{0}:{1}'.format(self._host_tmp_dir, self.container_tmp_dir)]
        else:
            self._binds = []

        # update environment property with the (internal) location of tmp_dir
        self.environment['TRUN_TMP_DIR'] = self.container_tmp_dir

        # add additional volume binds specified by the user to the tmp_Dir bind
        if isinstance(self.binds, str):
            self._binds.append(self.binds)
        elif isinstance(self.binds, list):
            self._binds.extend(self.binds)

        # derive volumes (ie. list of container destination paths) from
        # specified binds
        self._volumes = [b.split(':')[1] for b in self._binds]

    def run(self):

        # get image if missing
        if self.force_pull or len(self._client.images(name=self._image)) == 0:
            logger.info('Pulling docker image ' + self._image)
            try:
                for logline in self._client.pull(self._image, stream=True):
                    logger.debug(logline.decode('utf-8'))
            except APIError as e:
                self.__logger.warning("Error in Docker API: " + e.explanation)
                raise

        # remove clashing container if a container with the same name exists
        if self.auto_remove and self.name:
            try:
                self._client.remove_container(self.name,
                                              force=True)
            except APIError as e:
                self.__logger.warning("Ignored error in Docker API: " + e.explanation)

        # run the container
        try:
            logger.debug('Creating image: %s command: %s volumes: %s'
                         % (self._image, self.command, self._binds))

            host_config = self._client.create_host_config(binds=self._binds,
                                                          network_mode=self.network_mode,
                                                          **self.host_config_options)

            container = self._client.create_container(self._image,
                                                      command=self.command,
                                                      name=self.name,
                                                      environment=self.environment,
                                                      volumes=self._volumes,
                                                      host_config=host_config,
                                                      **self.container_options)
            self._client.start(container['Id'])

            exit_status = self._client.wait(container['Id'])
            # docker-py>=3.0.0 returns a dict instead of the status code directly
            if type(exit_status) is dict:
                exit_status = exit_status['StatusCode']

            if exit_status != 0:
                stdout = False
                stderr = True
                error = self._client.logs(container['Id'],
                                          stdout=stdout,
                                          stderr=stderr)
            if self.auto_remove:
                try:
                    self._client.remove_container(container['Id'])
                except docker.errors.APIError:
                    self.__logger.warning("Container " + container['Id'] +
                                          " could not be removed")
            if exit_status != 0:
                raise ContainerError(container, exit_status, self.command, self._image, error)

        except ContainerError as e:
            # catch non zero exti status and return it
            container_name = ''
            if self.name:
                container_name = self.name
            try:
                message = e.message
            except AttributeError:
                message = str(e)
            self.__logger.error("Container " + container_name +
                                " exited with non zero code: " + message)
            raise
        except ImageNotFound:
            self.__logger.error("Image " + self._image + " not found")
            raise
        except APIError as e:
            self.__logger.error("Error in Docker API: "+e.explanation)
            raise

        # delete temp dir
        filesys = LocalFileSystem()
        if self.mount_tmp and filesys.exists(self._host_tmp_dir):
            filesys.remove(self._host_tmp_dir, recursive=True)