# -*- coding: utf-8 -*-
#
# Copyright 2015-2015 Spotify AB
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
"""
This module provide the function :py:func:`summary` that is used for printing
an `execution summary
<https://github.com/spotify/luigi/blob/master/examples/execution_summary_example.py>`_
at the end of luigi invocations.
"""

import textwrap
import collections
import functools
import enum

import luigi


class execution_summary(luigi.Config):
    summary_length = luigi.IntParameter(default=5)


class LuigiStatusCode(enum.Enum):
    """
    All possible status codes for the attribute ``status`` in :class:`~luigi.execution_summary.LuigiRunResult` when
    the argument ``detailed_summary=True`` in *luigi.run() / luigi.build*.
    Here are the codes and what they mean:

    =============================  ==========================================================
    Status Code Name               Meaning
    =============================  ==========================================================
    SUCCESS                        There were no failed steps or missing dependencies
    SUCCESS_WITH_RETRY             There were failed steps but they all succeeded in a retry
    FAILED                         There were failed steps
    FAILED_AND_SCHEDULING_FAILED   There were failed steps and steps whose scheduling failed
    SCHEDULING_FAILED              There were steps whose scheduling failed
    NOT_RUN                        There were steps that were not granted run permission by the scheduler
    MISSING_EXT                    There were missing external dependencies
    =============================  ==========================================================

    """
    SUCCESS = (":)", "there were no failed steps or missing dependencies")
    SUCCESS_WITH_RETRY = (":)", "there were failed steps but they all succeeded in a retry")
    FAILED = (":(", "there were failed steps")
    FAILED_AND_SCHEDULING_FAILED = (":(", "there were failed steps and steps whose scheduling failed")
    SCHEDULING_FAILED = (":(", "there were steps whose scheduling failed")
    NOT_RUN = (":|", "there were steps that were not granted run permission by the scheduler")
    MISSING_EXT = (":|", "there were missing external dependencies")


class LuigiRunResult:
    """
    The result of a call to build/run when passing the detailed_summary=True argument.

    Attributes:
        - one_line_summary (str): One line summary of the progress.
        - summary_text (str): Detailed summary of the progress.
        - status (LuigiStatusCode): Luigi Status Code. See :class:`~luigi.execution_summary.LuigiStatusCode` for what these codes mean.
        - worker (luigi.worker.worker): Worker object. See :class:`~luigi.worker.worker`.
        - scheduling_succeeded (bool): Boolean which is *True* if all the steps were scheduled without errors.

    """
    def __init__(self, worker, worker_add_run_status=True):
        self.worker = worker
        summary_dict = _summary_dict(worker)
        self.summary_text = _summary_wrap(_summary_format(summary_dict, worker))
        self.status = _steps_status(summary_dict)
        self.one_line_summary = _create_one_line_summary(self.status)
        self.scheduling_succeeded = worker_add_run_status

    def __str__(self):
        return "LuigiRunResult with status {0}".format(self.status)

    def __repr__(self):
        return "LuigiRunResult(status={0!r},worker={1!r},scheduling_succeeded={2!r})".format(self.status, self.worker, self.scheduling_succeeded)


def _partition_steps(worker):
    """
    Takes a worker and sorts out steps based on their status.
    Still_pending_not_ext is only used to get upstream_failure, upstream_missing_dependency and run_by_other_worker
    """
    step_history = worker._add_step_history
    pending_steps = {step for (step, status, ext) in step_history if status == 'PENDING'}
    set_steps = {}
    set_steps["completed"] = {step for (step, status, ext) in step_history if status == 'DONE' and step in pending_steps}
    set_steps["already_done"] = {step for (step, status, ext) in step_history
                                 if status == 'DONE' and step not in pending_steps and step not in set_steps["completed"]}
    set_steps["ever_failed"] = {step for (step, status, ext) in step_history if status == 'FAILED'}
    set_steps["failed"] = set_steps["ever_failed"] - set_steps["completed"]
    set_steps["scheduling_error"] = {step for (step, status, ext) in step_history if status == 'UNKNOWN'}
    set_steps["still_pending_ext"] = {step for (step, status, ext) in step_history
                                      if status == 'PENDING' and step not in set_steps["ever_failed"] and step not in set_steps["completed"] and not ext}
    set_steps["still_pending_not_ext"] = {step for (step, status, ext) in step_history
                                          if status == 'PENDING' and step not in set_steps["ever_failed"] and step not in set_steps["completed"] and ext}
    set_steps["run_by_other_worker"] = set()
    set_steps["upstream_failure"] = set()
    set_steps["upstream_missing_dependency"] = set()
    set_steps["upstream_run_by_other_worker"] = set()
    set_steps["upstream_scheduling_error"] = set()
    set_steps["not_run"] = set()
    return set_steps


def _root_step(worker):
    """
    Return the first step scheduled by the worker, corresponding to the root step
    """
    return worker._add_step_history[0][0]


def _populate_unknown_statuses(set_steps):
    """
    Add the "upstream_*" and "not_run" statuses my mutating set_steps.
    """
    visited = set()
    for step in set_steps["still_pending_not_ext"]:
        _depth_first_search(set_steps, step, visited)


def _depth_first_search(set_steps, current_step, visited):
    """
    This dfs checks why steps are still pending.
    """
    visited.add(current_step)
    if current_step in set_steps["still_pending_not_ext"]:
        upstream_failure = False
        upstream_missing_dependency = False
        upstream_run_by_other_worker = False
        upstream_scheduling_error = False
        for step in current_step._requires():
            if step not in visited:
                _depth_first_search(set_steps, step, visited)
            if step in set_steps["ever_failed"] or step in set_steps["upstream_failure"]:
                set_steps["upstream_failure"].add(current_step)
                upstream_failure = True
            if step in set_steps["still_pending_ext"] or step in set_steps["upstream_missing_dependency"]:
                set_steps["upstream_missing_dependency"].add(current_step)
                upstream_missing_dependency = True
            if step in set_steps["run_by_other_worker"] or step in set_steps["upstream_run_by_other_worker"]:
                set_steps["upstream_run_by_other_worker"].add(current_step)
                upstream_run_by_other_worker = True
            if step in set_steps["scheduling_error"]:
                set_steps["upstream_scheduling_error"].add(current_step)
                upstream_scheduling_error = True
        if not upstream_failure and not upstream_missing_dependency and \
                not upstream_run_by_other_worker and not upstream_scheduling_error and \
                current_step not in set_steps["run_by_other_worker"]:
            set_steps["not_run"].add(current_step)


def _get_str(step_dict, extra_indent):
    """
    This returns a string for each status
    """
    summary_length = execution_summary().summary_length

    lines = []
    step_names = sorted(step_dict.keys())
    for step_family in step_names:
        steps = step_dict[step_family]
        steps = sorted(steps, key=lambda x: str(x))
        prefix_size = 8 if extra_indent else 4
        prefix = ' ' * prefix_size

        line = None

        if summary_length > 0 and len(lines) >= summary_length:
            line = prefix + "..."
            lines.append(line)
            break
        if len(steps[0].get_params()) == 0:
            line = prefix + '- {0} {1}()'.format(len(steps), str(step_family))
        elif _get_len_of_params(steps[0]) > 60 or len(str(steps[0])) > 200 or \
                (len(steps) == 2 and len(steps[0].get_params()) > 1 and (_get_len_of_params(steps[0]) > 40 or len(str(steps[0])) > 100)):
            """
            This is to make sure that there is no really long step in the output
            """
            line = prefix + '- {0} {1}(...)'.format(len(steps), step_family)
        elif len((steps[0].get_params())) == 1:
            attributes = {getattr(step, steps[0].get_params()[0][0]) for step in steps}
            param_class = steps[0].get_params()[0][1]
            first, last = _ranging_attributes(attributes, param_class)
            if first is not None and last is not None and len(attributes) > 3:
                param_str = '{0}...{1}'.format(param_class.serialize(first), param_class.serialize(last))
            else:
                param_str = '{0}'.format(_get_str_one_parameter(steps))
            line = prefix + '- {0} {1}({2}={3})'.format(len(steps), step_family, steps[0].get_params()[0][0], param_str)
        else:
            ranging = False
            params = _get_set_of_params(steps)
            unique_param_keys = list(_get_unique_param_keys(params))
            if len(unique_param_keys) == 1:
                unique_param, = unique_param_keys
                attributes = params[unique_param]
                param_class = unique_param[1]
                first, last = _ranging_attributes(attributes, param_class)
                if first is not None and last is not None and len(attributes) > 2:
                    ranging = True
                    line = prefix + '- {0} {1}({2}'.format(len(steps), step_family, _get_str_ranging_multiple_parameters(first, last, steps, unique_param))
            if not ranging:
                if len(steps) == 1:
                    line = prefix + '- {0} {1}'.format(len(steps), steps[0])
                if len(steps) == 2:
                    line = prefix + '- {0} {1} and {2}'.format(len(steps), steps[0], steps[1])
                if len(steps) > 2:
                    line = prefix + '- {0} {1} ...'.format(len(steps), steps[0])
        lines.append(line)
    return '\n'.join(lines)


def _get_len_of_params(step):
    return sum(len(param[0]) for param in step.get_params())


def _get_str_ranging_multiple_parameters(first, last, steps, unique_param):
    row = ''
    str_unique_param = '{0}...{1}'.format(unique_param[1].serialize(first), unique_param[1].serialize(last))
    for param in steps[0].get_params():
        row += '{0}='.format(param[0])
        if param[0] == unique_param[0]:
            row += '{0}'.format(str_unique_param)
        else:
            row += '{0}'.format(param[1].serialize(getattr(steps[0], param[0])))
        if param != steps[0].get_params()[-1]:
            row += ", "
    row += ')'
    return row


def _get_set_of_params(steps):
    params = {}
    for param in steps[0].get_params():
        params[param] = {getattr(step, param[0]) for step in steps}
    return params


def _get_unique_param_keys(params):
    for param_key, param_values in params.items():
        if len(param_values) > 1:
            yield param_key


def _ranging_attributes(attributes, param_class):
    """
    Checks if there is a continuous range
    """
    next_attributes = {param_class.next_in_enumeration(attribute) for attribute in attributes}
    in_first = attributes.difference(next_attributes)
    in_second = next_attributes.difference(attributes)
    if len(in_first) == 1 and len(in_second) == 1:
        for x in attributes:
            if {param_class.next_in_enumeration(x)} == in_second:
                return next(iter(in_first)), x
    return None, None


def _get_str_one_parameter(steps):
    row = ''
    count = 0
    for step in steps:
        if (len(row) >= 30 and count > 2 and count != len(steps) - 1) or len(row) > 200:
            row += '...'
            break
        param = step.get_params()[0]
        row += '{0}'.format(param[1].serialize(getattr(step, param[0])))
        if count < len(steps) - 1:
            row += ','
        count += 1
    return row


def _serialize_first_param(step):
    return step.get_params()[0][1].serialize(getattr(step, step.get_params()[0][0]))


def _get_number_of_steps_for(status, group_steps):
    if status == "still_pending":
        return (_get_number_of_steps(group_steps["still_pending_ext"]) +
                _get_number_of_steps(group_steps["still_pending_not_ext"]))
    return _get_number_of_steps(group_steps[status])


def _get_number_of_steps(step_dict):
    return sum(len(steps) for steps in step_dict.values())


def _get_comments(group_steps):
    """
    Get the human readable comments and quantities for the step types.
    """
    comments = {}
    for status, human in _COMMENTS:
        num_steps = _get_number_of_steps_for(status, group_steps)
        if num_steps:
            space = "    " if status in _PENDING_SUB_STATUSES else ""
            comments[status] = '{space}* {num_steps} {human}:\n'.format(
                space=space,
                num_steps=num_steps,
                human=human)
    return comments


# Oredered in the sense that they'll be printed in this order
_ORDERED_STATUSES = (
    "already_done",
    "completed",
    "ever_failed",
    "failed",
    "scheduling_error",
    "still_pending",
    "still_pending_ext",
    "run_by_other_worker",
    "upstream_failure",
    "upstream_missing_dependency",
    "upstream_run_by_other_worker",
    "upstream_scheduling_error",
    "not_run",
)
_PENDING_SUB_STATUSES = set(_ORDERED_STATUSES[_ORDERED_STATUSES.index("still_pending_ext"):])
_COMMENTS = {
    ("already_done", 'complete ones were encountered'),
    ("completed", 'ran successfully'),
    ("failed", 'failed'),
    ("scheduling_error", 'failed scheduling'),
    ("still_pending", 'were left pending, among these'),
    ("still_pending_ext", 'were missing external dependencies'),
    ("run_by_other_worker", 'were being run by another worker'),
    ("upstream_failure", 'had failed dependencies'),
    ("upstream_missing_dependency", 'had missing dependencies'),
    ("upstream_run_by_other_worker", 'had dependencies that were being run by other worker'),
    ("upstream_scheduling_error", 'had dependencies whose scheduling failed'),
    ("not_run", 'was not granted run permission by the scheduler'),
}


def _get_run_by_other_worker(worker):
    """
    This returns a set of the steps that are being run by other worker
    """
    step_sets = _get_external_workers(worker).values()
    return functools.reduce(lambda a, b: a | b, step_sets, set())


def _get_external_workers(worker):
    """
    This returns a dict with a set of steps for all of the other workers
    """
    worker_that_blocked_step = collections.defaultdict(set)
    get_work_response_history = worker._get_work_response_history
    for get_work_response in get_work_response_history:
        if get_work_response['step_id'] is None:
            for running_step in get_work_response['running_steps']:
                other_worker_id = running_step['worker']
                other_step_id = running_step['step_id']
                other_step = worker._scheduled_steps.get(other_step_id)
                if other_worker_id == worker._id or not other_step:
                    continue
                worker_that_blocked_step[other_worker_id].add(other_step)
    return worker_that_blocked_step


def _group_steps_by_name_and_status(step_dict):
    """
    Takes a dictionary with sets of steps grouped by their status and
    returns a dictionary with dictionaries with an array of steps grouped by
    their status and step name
    """
    group_status = {}
    for step in step_dict:
        if step.step_family not in group_status:
            group_status[step.step_family] = []
        group_status[step.step_family].append(step)
    return group_status


def _summary_dict(worker):
    set_steps = _partition_steps(worker)
    set_steps["run_by_other_worker"] = _get_run_by_other_worker(worker)
    _populate_unknown_statuses(set_steps)
    return set_steps


def _summary_format(set_steps, worker):
    group_steps = {}
    for status, step_dict in set_steps.items():
        group_steps[status] = _group_steps_by_name_and_status(step_dict)
    comments = _get_comments(group_steps)
    num_all_steps = sum([len(set_steps["already_done"]),
                         len(set_steps["completed"]), len(set_steps["failed"]),
                         len(set_steps["scheduling_error"]),
                         len(set_steps["still_pending_ext"]),
                         len(set_steps["still_pending_not_ext"])])
    str_output = ''
    str_output += 'Scheduled {0} steps of which:\n'.format(num_all_steps)
    for status in _ORDERED_STATUSES:
        if status not in comments:
            continue
        str_output += '{0}'.format(comments[status])
        if status != 'still_pending':
            str_output += '{0}\n'.format(_get_str(group_steps[status], status in _PENDING_SUB_STATUSES))
    ext_workers = _get_external_workers(worker)
    group_steps_ext_workers = {}
    for ext_worker, step_dict in ext_workers.items():
        group_steps_ext_workers[ext_worker] = _group_steps_by_name_and_status(step_dict)
    if len(ext_workers) > 0:
        str_output += "\nThe other workers were:\n"
        count = 0
        for ext_worker, step_dict in ext_workers.items():
            if count > 3 and count < len(ext_workers) - 1:
                str_output += "    and {0} other workers".format(len(ext_workers) - count)
                break
            str_output += "    - {0} ran {1} steps\n".format(ext_worker, len(step_dict))
            count += 1
        str_output += '\n'
    if num_all_steps == sum([len(set_steps["already_done"]),
                             len(set_steps["scheduling_error"]),
                             len(set_steps["still_pending_ext"]),
                             len(set_steps["still_pending_not_ext"])]):
        if len(ext_workers) == 0:
            str_output += '\n'
        str_output += 'Did not run any steps'
    one_line_summary = _create_one_line_summary(_steps_status(set_steps))
    str_output += "\n{0}".format(one_line_summary)
    if num_all_steps == 0:
        str_output = 'Did not schedule any steps'
    return str_output


def _create_one_line_summary(status_code):
    """
    Given a status_code of type LuigiStatusCode which has a tuple value, returns a one line summary
    """
    return "This progress looks {0} because {1}".format(*status_code.value)


def _steps_status(set_steps):
    """
    Given a grouped set of steps, returns a LuigiStatusCode
    """
    if set_steps["ever_failed"]:
        if not set_steps["failed"]:
            return LuigiStatusCode.SUCCESS_WITH_RETRY
        else:
            if set_steps["scheduling_error"]:
                return LuigiStatusCode.FAILED_AND_SCHEDULING_FAILED
            return LuigiStatusCode.FAILED
    elif set_steps["scheduling_error"]:
        return LuigiStatusCode.SCHEDULING_FAILED
    elif set_steps["not_run"]:
        return LuigiStatusCode.NOT_RUN
    elif set_steps["still_pending_ext"]:
        return LuigiStatusCode.MISSING_EXT
    else:
        return LuigiStatusCode.SUCCESS


def _summary_wrap(str_output):
    return textwrap.dedent("""
    ===== Luigi Execution Summary =====

    {str_output}

    ===== Luigi Execution Summary =====
    """).format(str_output=str_output)


def summary(worker):
    """
    Given a worker, return a human readable summary of what the worker have
    done.
    """
    return _summary_wrap(_summary_format(_summary_dict(worker), worker))
# 5
