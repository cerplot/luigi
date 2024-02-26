"""
Integration test for the Trun wrapper of EC2 Container Service (ECSStep)

Requires:

- boto3 package
- Amazon AWS credentials discoverable by boto3 (e.g., by using ``aws configure``
from awscli_)
- A running ECS cluster (see `ECS Get Started`_)

Written and maintained by Jake Feala (@jfeala) for Outlier Bio (@outlierbio)

.. _awscli: https://aws.amazon.com/cli
.. _`ECS Get Started`: http://docs.aws.amazon.com/AmazonECS/latest/developerguide/ECS_GetStarted.html
"""

import unittest

import trun
from trun.contrib.ecs import ECSStep, _get_step_statuses
from moto import mock_ecs
import pytest

try:
    import boto3
except ImportError:
    raise unittest.SkipTest('boto3 is not installed. ECSSteps require boto3')

TEST_STEP_DEF = {
    'family': 'hello-world',
    'volumes': [],
    'containerDefinitions': [
        {
            'memory': 1,
            'essential': True,
            'name': 'hello-world',
            'image': 'ubuntu',
            'command': ['/bin/echo', 'hello world']
        },
        {
            'memory': 1,
            'essential': True,
            'name': 'hello-world-2',
            'image': 'ubuntu',
            'command': ['/bin/echo', 'hello world #2!']
        }
    ]
}


class ECSStepNoOutput(ECSStep):

    def complete(self):
        if self.ecs_step_ids:
            return all([status == 'STOPPED'
                        for status in _get_step_statuses(self.ecs_step_ids)])
        return False


class ECSStepOverrideCommand(ECSStepNoOutput):

    @property
    def command(self):
        return [{'name': 'hello-world', 'command': ['/bin/sleep', '10']}]


class ECSStepCustomRunStepKwargs(ECSStepNoOutput):

    @property
    def run_step_kwargs(self):
        return {'overrides': {'ephemeralStorage': {'sizeInGiB': 30}}}


class ECSStepCustomRunStepKwargsWithCollidingCommand(ECSStepNoOutput):

    @property
    def command(self):
        return [
            {'name': 'hello-world', 'command': ['/bin/sleep', '10']},
            {'name': 'hello-world-2', 'command': ['/bin/sleep', '10']},
        ]

    @property
    def run_step_kwargs(self):
        return {
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
                'containerOverrides': [
                    {'name': 'hello-world-2', 'command': ['command-to-be-overwritten']}
                ],
                'ephemeralStorage': {
                    'sizeInGiB': 30
                }
            }
        }


class ECSStepCustomRunStepKwargsWithMergedCommands(ECSStepNoOutput):

    @property
    def command(self):
        return [
            {'name': 'hello-world', 'command': ['/bin/sleep', '10']}
        ]

    @property
    def run_step_kwargs(self):
        return {
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
                'containerOverrides': [
                    {'name': 'hello-world-2', 'command': ['/bin/sleep', '10']}
                ],
                'ephemeralStorage': {
                    'sizeInGiB': 30
                }
            }
        }


@pytest.mark.aws
class TestECSStep(unittest.TestCase):

    @mock_ecs
    def setUp(self):
        # Register the test step definition
        response = boto3.client('ecs').register_step_definition(**TEST_STEP_DEF)
        self.arn = response['stepDefinition']['stepDefinitionArn']

    @mock_ecs
    def test_unregistered_step(self):
        t = ECSStepNoOutput(step_def=TEST_STEP_DEF)
        trun.build([t], local_scheduler=True)

    @mock_ecs
    def test_registered_step(self):
        t = ECSStepNoOutput(step_def_arn=self.arn)
        trun.build([t], local_scheduler=True)

    @mock_ecs
    def test_override_command(self):
        t = ECSStepOverrideCommand(step_def_arn=self.arn)
        trun.build([t], local_scheduler=True)

    @mock_ecs
    def test_custom_run_step_kwargs(self):
        t = ECSStepCustomRunStepKwargs(step_def_arn=self.arn)
        self.assertEqual(t.combined_overrides, {
            'ephemeralStorage': {'sizeInGiB': 30}
        })
        trun.build([t], local_scheduler=True)

    @mock_ecs
    def test_custom_run_step_kwargs_with_colliding_command(self):
        t = ECSStepCustomRunStepKwargsWithCollidingCommand(step_def_arn=self.arn)
        combined_overrides = t.combined_overrides
        self.assertEqual(
            sorted(combined_overrides['containerOverrides'], key=lambda x: x['name']),
            sorted(
                [
                    {'name': 'hello-world', 'command': ['/bin/sleep', '10']},
                    {'name': 'hello-world-2', 'command': ['/bin/sleep', '10']},
                ],
                key=lambda x: x['name']
            )
        )
        self.assertEqual(combined_overrides['ephemeralStorage'], {'sizeInGiB': 30})
        trun.build([t], local_scheduler=True)

    @mock_ecs
    def test_custom_run_step_kwargs_with_merged_commands(self):
        t = ECSStepCustomRunStepKwargsWithMergedCommands(step_def_arn=self.arn)
        combined_overrides = t.combined_overrides
        self.assertEqual(
            sorted(combined_overrides['containerOverrides'], key=lambda x: x['name']),
            sorted(
                [
                    {'name': 'hello-world', 'command': ['/bin/sleep', '10']},
                    {'name': 'hello-world-2', 'command': ['/bin/sleep', '10']},
                ],
                key=lambda x: x['name']
            )
        )
        self.assertEqual(combined_overrides['ephemeralStorage'], {'sizeInGiB': 30})
        trun.build([t], local_scheduler=True)
