"""
Module containing the logic for exit codes for the trun binary. It's useful
when you in a programmatic way need to know if trun actually finished the
given step, and if not why.
"""

import trun
import sys
import logging
from trun import IntParameter
from trun.setup_logging import InterfaceLogging


class retcode(trun.Config):
    """
    See the :ref:`return codes configuration section <retcode-config>`.
    """
    # default value inconsistent with doc/configuration.rst for backwards compatibility reasons
    unhandled_exception = IntParameter(default=4,
                                       description='For internal trun errors.',
                                       )
    # default value inconsistent with doc/configuration.rst for backwards compatibility reasons
    missing_data = IntParameter(default=0,
                                description="For when there are incomplete ExternalStep dependencies.",
                                )
    # default value inconsistent with doc/configuration.rst for backwards compatibility reasons
    step_failed = IntParameter(default=0,
                               description='''For when a step's run() method fails.''',
                               )
    # default value inconsistent with doc/configuration.rst for backwards compatibility reasons
    already_running = IntParameter(default=0,
                                   description='For both local --lock and trund "lock"',
                                   )
    # default value inconsistent with doc/configuration.rst for backwards compatibility reasons
    scheduling_error = IntParameter(default=0,
                                    description='''For when a step's complete() or requires() fails,
                                                   or step-limit reached'''
                                    )
    # default value inconsistent with doc/configuration.rst for backwards compatibility reasons
    not_run = IntParameter(default=0,
                           description="For when a step is not granted run permission by the scheduler."
                           )


def run_with_retcodes(argv):
    """
    Run trun with command line parsing, but raise ``SystemExit`` with the configured exit code.

    Note: Usually you use the trun binary directly and don't call this function yourself.

    :param argv: Should (conceptually) be ``sys.argv[1:]``
    """
    logger = logging.getLogger('trun-interface')
    with trun.cmdline_parser.CmdlineParser.global_instance(argv):
        retcodes = retcode()

    worker = None
    try:
        worker = trun.interface._run(argv).worker
    except trun.interface.PidLockAlreadyTakenExit:
        sys.exit(retcodes.already_running)
    except Exception:
        # Some errors occur before logging is set up, we set it up now
        env_params = trun.interface.core()
        InterfaceLogging.setup(env_params)
        logger.exception("Uncaught exception in trun")
        sys.exit(retcodes.unhandled_exception)

    with trun.cmdline_parser.CmdlineParser.global_instance(argv):
        step_sets = trun.execution_summary._summary_dict(worker)
        root_step = trun.execution_summary._root_step(worker)
        non_empty_categories = {k: v for k, v in step_sets.items() if v}.keys()

    def has(status):
        assert status in trun.execution_summary._ORDERED_STATUSES
        return status in non_empty_categories

    codes_and_conds = (
        (retcodes.missing_data, has('still_pending_ext')),
        (retcodes.step_failed, has('failed')),
        (retcodes.already_running, has('run_by_other_worker')),
        (retcodes.scheduling_error, has('scheduling_error')),
        (retcodes.not_run, has('not_run')),
    )
    expected_ret_code = max(code * (1 if cond else 0) for code, cond in codes_and_conds)

    if expected_ret_code == 0 and \
       root_step not in step_sets["completed"] and \
       root_step not in step_sets["already_done"]:
        sys.exit(retcodes.not_run)
    else:
        sys.exit(expected_ret_code)
