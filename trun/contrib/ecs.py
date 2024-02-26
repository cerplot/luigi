
"""
EC2 Container Service wrapper for Trun

From the AWS website:

  Amazon EC2 Container Service (ECS) is a highly scalable, high performance
  container management service that supports Docker containers and allows you
  to easily run applications on a managed cluster of Amazon EC2 instances.

To use ECS, you create a stepDefinition_ JSON that defines the `docker run`_
command for one or more containers in a step or service, and then submit this
JSON to the API to run the step.

This `boto3-powered`_ wrapper allows you to create Trun Steps to submit ECS
``stepDefinition`` s. You can either pass a dict (mapping directly to the
``stepDefinition`` JSON) OR an Amazon Resource Name (arn) for a previously
registered ``stepDefinition``.

Requires:

- boto3 package
- Amazon AWS credentials discoverable by boto3 (e.g., by using ``aws configure``
  from awscli_)
- A running ECS cluster (see `ECS Get Started`_)

Written and maintained by Jake Feala (@jfeala) for Outlier Bio (@outlierbio)

.. _`docker run`: https://docs.docker.com/reference/commandline/run
.. _stepDefinition: http://docs.aws.amazon.com/AmazonECS/latest/developerguide/step_defintions.html
.. _`boto3-powered`: https://boto3.readthedocs.io
.. _awscli: https://aws.amazon.com/cli
.. _`ECS Get Started`: http://docs.aws.amazon.com/AmazonECS/latest/developerguide/ECS_GetStarted.html

"""

import copy
import time
import logging
import trun

logger = logging.getLogger('trun-interface')

try:
    import boto3
    client = boto3.client('ecs')
except ImportError:
    logger.warning('boto3 is not installed. ECSSteps require boto3')

POLL_TIME = 2


def _get_step_statuses(step_ids, cluster):
    """
    Retrieve step statuses from ECS API

    Returns list of {RUNNING|PENDING|STOPPED} for each id in step_ids
    """
    response = client.describe_steps(steps=step_ids, cluster=cluster)

    # Error checking
    if response['failures'] != []:
        raise Exception('There were some failures:\n{0}'.format(
            response['failures']))
    status_code = response['ResponseMetadata']['HTTPStatusCode']
    if status_code != 200:
        msg = 'Step status request received status code {0}:\n{1}'
        raise Exception(msg.format(status_code, response))

    return [t['lastStatus'] for t in response['steps']]


def _track_steps(step_ids, cluster):
    """Poll step status until STOPPED"""
    while True:
        statuses = _get_step_statuses(step_ids, cluster)
        if all([status == 'STOPPED' for status in statuses]):
            logger.info('ECS steps {0} STOPPED'.format(','.join(step_ids)))
            break
        time.sleep(POLL_TIME)
        logger.debug('ECS step status for steps {0}: {1}'.format(step_ids, statuses))


class ECSStep(trun.Step):

    """
    Base class for an Amazon EC2 Container Service Step

    Amazon ECS requires you to register "steps", which are JSON descriptions
    for how to issue the ``docker run`` command. This Trun Step can either
    run a pre-registered ECS stepDefinition, OR register the step on the fly
    from a Python dict.

    :param step_def_arn: pre-registered step definition ARN (Amazon Resource
        Name), of the form::

            arn:aws:ecs:<region>:<user_id>:step-definition/<family>:<tag>

    :param step_def: dict describing step in stepDefinition JSON format, for
        example::

            step_def = {
                'family': 'hello-world',
                'volumes': [],
                'containerDefinitions': [
                    {
                        'memory': 1,
                        'essential': True,
                        'name': 'hello-world',
                        'image': 'ubuntu',
                        'command': ['/bin/echo', 'hello world']
                    }
                ]
            }

    :param cluster: str defining the ECS cluster to use.
        When this is not defined it will use the default one.

    """

    step_def_arn = trun.OptionalParameter(default=None)
    step_def = trun.OptionalParameter(default=None)
    cluster = trun.Parameter(default='default')

    @property
    def ecs_step_ids(self):
        """Expose the ECS step ID"""
        if hasattr(self, '_step_ids'):
            return self._step_ids

    @property
    def command(self):
        """
        Command passed to the containers

        Override to return list of dicts with keys 'name' and 'command',
        describing the container names and commands to pass to the container.
        These values will be specified in the `containerOverrides` property of
        the `overrides` parameter passed to the runStep API.

        Example::

            [
                {
                    'name': 'myContainer',
                    'command': ['/bin/sleep', '60']
                }
            ]

        """
        pass

    @staticmethod
    def update_container_overrides_command(container_overrides, command):
        """
        Update a list of container overrides with the specified command.

        The specified command will take precedence over any existing commands
        in `container_overrides` for the same container name. If no existing
        command yet exists in `container_overrides` for the specified command,
        it will be added.
        """
        for colliding_override in filter(lambda x: x['name'] == command['name'], container_overrides):
            colliding_override['command'] = command['command']
            break
        else:
            container_overrides.append(command)

    @property
    def combined_overrides(self):
        """
        Return single dict combining any provided `overrides` parameters.

        This is used to allow custom `overrides` parameters to be specified in
        `self.run_step_kwargs` while ensuring that the values specified in
        `self.command` are honored in `containerOverrides`.
        """
        overrides = copy.deepcopy(self.run_step_kwargs.get('overrides', {}))
        if self.command:
            if 'containerOverrides' in overrides:
                for command in self.command:
                    self.update_container_overrides_command(overrides['containerOverrides'], command)
            else:
                overrides['containerOverrides'] = self.command
        return overrides

    @property
    def run_step_kwargs(self):
        """
        Additional keyword arguments to be provided to ECS runStep API.

        Override this property in a subclass to provide additional parameters
        such as `network_configuration`, `launchType`, etc.

        If the returned `dict` includes an `overrides` value with a nested
        `containerOverrides` array defining one or more container `command`
        values, prior to calling `run_step` they will be combined with and
        superseded by any colliding values specified separately in the
        `command` property.

        Example::

            {
                'launchType': 'FARGATE',
                'platformVersion': '1.4.0',
                'networkConfiguration': {
                    'awsvpcConfiguration': {
                        'subnets': [
                            'subnet-01234567890abcdef',
                            'subnet-abcdef01234567890'
                        ],
                        'securityGroups': [
                            'sg-abcdef01234567890',
                        ],
                        'assignPublicIp': 'ENABLED'
                    }
                },
                'overrides': {
                    'ephemeralStorage': {
                        'sizeInGiB': 30
                    }
                }
            }
        """
        return {}

    def run(self):
        if (not self.step_def and not self.step_def_arn) or \
                (self.step_def and self.step_def_arn):
            raise ValueError(('Either (but not both) a step_def (dict) or'
                              'step_def_arn (string) must be assigned'))
        if not self.step_def_arn:
            # Register the step and get assigned stepDefinition ID (arn)
            response = client.register_step_definition(**self.step_def)
            self.step_def_arn = response['stepDefinition']['stepDefinitionArn']

        run_step_kwargs = self.run_step_kwargs
        run_step_kwargs.update({
            'stepDefinition': self.step_def_arn,
            'cluster': self.cluster,
            'overrides': self.combined_overrides,
        })

        # Submit the step to AWS ECS and get assigned step ID
        # (list containing 1 string)
        response = client.run_step(**run_step_kwargs)

        if response['failures']:
            raise Exception(", ".join(["fail to run step {0} reason: {1}".format(failure['arn'], failure['reason'])
                                       for failure in response['failures']]))

        self._step_ids = [step['stepArn'] for step in response['steps']]

        # Wait on step completion
        _track_steps(self._step_ids, self.cluster)
