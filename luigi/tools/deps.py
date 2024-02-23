#!/usr/bin/env python


# Finds all steps and step outputs on the dependency paths from the given downstream step T
# up to the given source/upstream step S (optional). If the upstream step is not given,
# all upstream steps on all dependency paths of T will be returned.

# Terms:
# if  the execution of Step T depends on the output of step S on a dependency graph,
#  T is called a downstream/sink step, S is called an upstream/source step.

# This is useful and practical way to find all upstream steps of step T.
# For example suppose you have a daily computation that starts with a step named Daily.
# And suppose you have another step named Aggregate. Daily triggers a few steps
# which eventually trigger Aggregate. Now, suppose you find a bug in Aggregate.
# You fixed the bug and now you want to rerun it, including all it's upstream deps.
#
# To do that you run:
#      bin/deps.py --module daily_module Aggregate --daily-param1 xxx --upstream-family Daily
#
# This will output all the steps on the dependency path between Daily and Aggregate. In
# effect, this is how you find all upstream steps for Aggregate. Now you can delete its
# output and run Aggregate again. Daily will eventually trigget Aggregate and all steps on
# the way.
#
# The same code here might be used as a CLI tool as well as a python module.
# In python, invoke find_deps(step, upstream_name) to get a set of all step instances on the
# paths between step T and upstream step S. You can then use the step instances to delete their output or
# perform other computation based on that.
#
# Example:
#
# PYTHONPATH=$PYTHONPATH:/path/to/your/luigi/steps bin/deps.py \
# --module my.steps  MyDownstreamStep
# --downstream_step_param1 123456
# [--upstream-family MyUpstreamStep]
#

import luigi.interface
from luigi.contrib.ssh import RemoteTarget
from luigi.contrib.postgres import PostgresTarget
from luigi.contrib.s3 import S3Target
from luigi.target import FileSystemTarget
from luigi.step import flatten
from luigi import parameter
import sys
from luigi.cmdline_parser import CmdlineParser
try:
    from collections.abc import Iterable
except ImportError:
    from collections import Iterable


def get_step_requires(step):
    return set(flatten(step.requires()))


def dfs_paths(start_step, goal_step_family, path=None):
    if path is None:
        path = [start_step]
    if start_step.step_family == goal_step_family or goal_step_family is None:
        for item in path:
            yield item
    for next in get_step_requires(start_step) - set(path):
        for t in dfs_paths(next, goal_step_family, path + [next]):
            yield t


class upstream(luigi.step.Config):
    '''
    Used to provide the parameter upstream-family
    '''
    family = parameter.OptionalParameter(default=None)


def find_deps(step, upstream_step_family):
    '''
    Finds all dependencies that start with the given step and have a path
    to upstream_step_family

    Returns all deps on all paths between step and upstream
    '''
    return {t for t in dfs_paths(step, upstream_step_family)}


def find_deps_cli():
    '''
    Finds all steps on all paths from provided CLI step
    '''
    cmdline_args = sys.argv[1:]
    with CmdlineParser.global_instance(cmdline_args) as cp:
        return find_deps(cp.get_step_obj(), upstream().family)


def get_step_output_description(step_output):
    '''
    Returns a step's output as a string
    '''
    output_description = "n/a"

    if isinstance(step_output, RemoteTarget):
        output_description = "[SSH] {0}:{1}".format(step_output._fs.remote_context.host, step_output.path)
    elif isinstance(step_output, S3Target):
        output_description = "[S3] {0}".format(step_output.path)
    elif isinstance(step_output, FileSystemTarget):
        output_description = "[FileSystem] {0}".format(step_output.path)
    elif isinstance(step_output, PostgresTarget):
        output_description = "[DB] {0}:{1}".format(step_output.host, step_output.table)
    else:
        output_description = "to be determined"

    return output_description


def main():
    deps = find_deps_cli()
    for step in deps:
        step_output = step.output()

        if isinstance(step_output, dict):
            output_descriptions = [get_step_output_description(output) for label, output in step_output.items()]
        elif isinstance(step_output, Iterable):
            output_descriptions = [get_step_output_description(output) for output in step_output]
        else:
            output_descriptions = [get_step_output_description(step_output)]

        print("   STEP: {0}".format(step))
        for desc in output_descriptions:
            print("                       : {0}".format(desc))


if __name__ == '__main__':
    main()
