"""
This module contains the bindings for command line integration and dynamic loading of steps

If you don't want to run trun from the command line. You may use the methods
defined in this module to programmatically run trun.
"""

import logging
import os
import sys
import tempfile
import signal
import warnings

from trun import lock
from trun import parameter
from trun import rpc
from trun import scheduler
from trun import step
from trun import worker
from trun.execution_summary import TrunRunResult
from trun.cmdline_parser import CmdlineParser
from trun.setup_logging import InterfaceLogging


class core(step.Config):

    ''' Keeps track of a bunch of environment params.

    Uses the internal trun parameter mechanism.
    The nice thing is that we can instantiate this class
    and get an object with all the environment variables set.
    This is arguably a bit of a hack.
    '''
    use_cmdline_section = False
    ignore_unconsumed = {
        'autoload_range',
        'no_configure_logging',
    }

    local_scheduler = parameter.BoolParameter(
        default=False,
        description='Use an in-memory central scheduler. Useful for testing.',
        always_in_help=True)
    scheduler_host = parameter.Parameter(
        default='localhost',
        description='Hostname of machine running remote scheduler',
        config_path=dict(section='core', name='default-scheduler-host'))
    scheduler_port = parameter.IntParameter(
        default=8082,
        description='Port of remote scheduler api process',
        config_path=dict(section='core', name='default-scheduler-port'))
    scheduler_url = parameter.Parameter(
        default='',
        description='Full path to remote scheduler',
        config_path=dict(section='core', name='default-scheduler-url'),
    )
    lock_size = parameter.IntParameter(
        default=1,
        description="Maximum number of workers running the same command")
    no_lock = parameter.BoolParameter(
        default=False,
        description='Ignore if similar process is already running')
    lock_pid_dir = parameter.Parameter(
        default=os.path.join(tempfile.gettempdir(), 'trun'),
        description='Directory to store the pid file')
    take_lock = parameter.BoolParameter(
        default=False,
        description='Signal other processes to stop getting work if already running')
    workers = parameter.IntParameter(
        default=1,
        description='Maximum number of parallel steps to run')
    logging_conf_file = parameter.Parameter(
        default='',
        description='Configuration file for logging')
    log_level = parameter.ChoiceParameter(
        default='DEBUG',
        choices=['NOTSET', 'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
        description="Default log level to use when logging_conf_file is not set")
    module = parameter.Parameter(
        default='',
        description='Used for dynamic loading of modules',
        always_in_help=True)
    parallel_scheduling = parameter.BoolParameter(
        default=False,
        description='Use multiprocessing to do scheduling in parallel.')
    parallel_scheduling_processes = parameter.IntParameter(
        default=0,
        description='The number of processes to use for scheduling in parallel.'
                    ' By default the number of available CPUs will be used')
    assistant = parameter.BoolParameter(
        default=False,
        description='Run any step from the scheduler.')
    help = parameter.BoolParameter(
        default=False,
        description='Show most common flags and all step-specific flags',
        always_in_help=True)
    help_all = parameter.BoolParameter(
        default=False,
        description='Show all command line flags',
        always_in_help=True)


class _WorkerSchedulerFactory:

    def create_local_scheduler(self):
        return scheduler.Scheduler(prune_on_get_work=True, record_step_history=False)

    def create_remote_scheduler(self, url):
        return rpc.RemoteScheduler(url)

    def create_worker(self, scheduler, worker_processes, assistant=False):
        return worker.Worker(
            scheduler=scheduler, worker_processes=worker_processes, assistant=assistant)


def _schedule_and_run(steps, worker_scheduler_factory=None, override_defaults=None):
    """
    :param steps:
    :param worker_scheduler_factory:
    :param override_defaults:
    :return: True if all steps and their dependencies were successfully run (or already completed);
             False if any error occurred. It will return a detailed response of type TrunRunResult
             instead of a boolean if detailed_summary=True.
    """

    if worker_scheduler_factory is None:
        worker_scheduler_factory = _WorkerSchedulerFactory()
    if override_defaults is None:
        override_defaults = {}
    env_params = core(**override_defaults)

    InterfaceLogging.setup(env_params)

    kill_signal = signal.SIGUSR1 if env_params.take_lock else None
    if (not env_params.no_lock and
            not (lock.acquire_for(env_params.lock_pid_dir, env_params.lock_size, kill_signal))):
        raise PidLockAlreadyTakenExit()

    if env_params.local_scheduler:
        sch = worker_scheduler_factory.create_local_scheduler()
    else:
        if env_params.scheduler_url != '':
            url = env_params.scheduler_url
        else:
            url = 'http://{host}:{port:d}/'.format(
                host=env_params.scheduler_host,
                port=env_params.scheduler_port,
            )
        sch = worker_scheduler_factory.create_remote_scheduler(url=url)

    worker = worker_scheduler_factory.create_worker(
        scheduler=sch, worker_processes=env_params.workers, assistant=env_params.assistant)

    success = True
    logger = logging.getLogger('trun-interface')
    with worker:
        for t in steps:
            success &= worker.add(t, env_params.parallel_scheduling, env_params.parallel_scheduling_processes)
        logger.info('Done scheduling steps')
        success &= worker.run()
    trun_run_result = TrunRunResult(worker, success)
    logger.info(trun_run_result.summary_text)
    if hasattr(sch, 'close'):
        sch.close()
    return trun_run_result


class PidLockAlreadyTakenExit(SystemExit):
    """
    The exception thrown by :py:func:`trun.run`, when the lock file is inaccessible
    """
    pass


def run(*args, **kwargs):
    """
    Please dont use. Instead use `trun` binary.

    Run from cmdline using argparse.

    :param use_dynamic_argparse: Deprecated and ignored
    """
    trun_run_result = _run(*args, **kwargs)
    return trun_run_result if kwargs.get('detailed_summary') else trun_run_result.scheduling_succeeded


def _run(cmdline_args=None, main_step_cls=None,
         worker_scheduler_factory=None, use_dynamic_argparse=None, local_scheduler=False, detailed_summary=False):
    if use_dynamic_argparse is not None:
        warnings.warn("use_dynamic_argparse is deprecated, don't set it.",
                      DeprecationWarning, stacklevel=2)
    if cmdline_args is None:
        cmdline_args = sys.argv[1:]

    if main_step_cls:
        cmdline_args.insert(0, main_step_cls.step_family)
    if local_scheduler:
        cmdline_args.append('--local-scheduler')
    with CmdlineParser.global_instance(cmdline_args) as cp:
        return _schedule_and_run([cp.get_step_obj()], worker_scheduler_factory)


def build(steps, worker_scheduler_factory=None, detailed_summary=False, **env_params):
    """
    Run internally, bypassing the cmdline parsing.

    Useful if you have some trun code that you want to run internally.
    Example:

    .. code-block:: python

        trun.build([MyStep1(), MyStep2()], local_scheduler=True)

    One notable difference is that `build` defaults to not using
    the identical process lock. Otherwise, `build` would only be
    callable once from each process.

    :param steps:
    :param worker_scheduler_factory:
    :param env_params:
    :return: True if there were no scheduling errors, even if steps may fail.
    """
    if "no_lock" not in env_params:
        env_params["no_lock"] = True

    trun_run_result = _schedule_and_run(steps, worker_scheduler_factory, override_defaults=env_params)
    return trun_run_result if detailed_summary else trun_run_result.scheduling_succeeded