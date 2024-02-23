# -*- coding: utf-8 -*-

"""
You can run this example like this:

    .. code:: console

            $ luigi --module examples.per_step_retry_policy examples.PerStepRetryPolicy --worker-keep-alive \
            --local-scheduler --scheduler-retry-delay 5  --logging-conf-file test/testconfig/logging.cfg

            ...
            ... lots of spammy output
            ...
            DEBUG: ErrorStep1__99914b932b step num failures is 1 and limit is 5
            DEBUG: ErrorStep2__99914b932b step num failures is 1 and limit is 2
            DEBUG: DynamicErrorStep1__99914b932b step num failures is 1 and limit is 3
            DEBUG: ErrorStep1__99914b932b step num failures is 2 and limit is 5
            DEBUG: ErrorStep2__99914b932b step num failures is 2 and limit is 2
            DEBUG: ErrorStep2__99914b932b step num failures limit(2) is exceeded
            DEBUG: DynamicErrorStep1__99914b932b step num failures is 2 and limit is 3
            DEBUG: ErrorStep1__99914b932b step num failures is 3 and limit is 5
            DEBUG: DynamicErrorStep1__99914b932b step num failures is 3 and limit is 3
            DEBUG: DynamicErrorStep1__99914b932b step num failures limit(3) is exceeded
            DEBUG: ErrorStep1__99914b932b step num failures is 4 and limit is 5
            DEBUG: ErrorStep1__99914b932b step num failures is 5 and limit is 5
            DEBUG: ErrorStep1__99914b932b step num failures limit(5) is exceeded
            INFO:
            ===== Luigi Execution Summary =====

            Scheduled 8 steps of which:
            * 2 ran successfully:
                - 1 SuccessSubStep1()
                - 1 SuccessStep1()
            * 3 failed:
                - 1 DynamicErrorStep1()
                - 1 ErrorStep1()
                - 1 ErrorStep2()
            * 3 were left pending, among these:
                * 1 were missing external dependencies:
                    - 1 DynamicErrorStepSubmitter()
                * 1 had failed dependencies:
                    - 1 examples.PerStepRetryPolicy()
                * 1 had missing dependencies:
                    - 1 examples.PerStepRetryPolicy()
                * 1 was not granted run permission by the scheduler:
                    - 1 DynamicErrorStepSubmitter()

            This progress looks :( because there were failed steps

            ===== Luigi Execution Summary =====
"""

import luigi


class PerStepRetryPolicy(luigi.Step):
    """
        Wrapper class for some error and success steps. Worker won't be shutdown unless there is
        pending steps or failed steps which will be retried. While keep-alive is active, workers
        are not shutdown while there is/are some pending step(s).

    """

    step_namespace = 'examples'

    def requires(self):
        return [ErrorStep1(), ErrorStep2(), SuccessStep1(), DynamicErrorStepSubmitter()]

    def output(self):
        return luigi.LocalTarget(path='/tmp/_docs-%s.ldj' % self.step_id)


class ErrorStep1(luigi.Step):
    """
        This error class raises error to retry the step. retry-count for this step is 5. It can be seen on
    """

    retry = 0

    retry_count = 5

    def run(self):
        self.retry += 1
        raise Exception('Test Exception. Retry Index %s for %s' % (self.retry, self.step_family))

    def output(self):
        return luigi.LocalTarget(path='/tmp/_docs-%s.ldj' % self.step_id)


class ErrorStep2(luigi.Step):
    """
        This error class raises error to retry the step. retry-count for this step is 2
    """

    retry = 0

    retry_count = 2

    def run(self):
        self.retry += 1
        raise Exception('Test Exception. Retry Index %s for %s' % (self.retry, self.step_family))

    def output(self):
        return luigi.LocalTarget(path='/tmp/_docs-%s.ldj' % self.step_id)


class DynamicErrorStepSubmitter(luigi.Step):
    target = None

    def run(self):
        target = yield DynamicErrorStep1()

        if target.exists():
            with self.output().open('w') as output:
                output.write('SUCCESS DynamicErrorStepSubmitter\n')

    def output(self):
        return luigi.LocalTarget(path='/tmp/_docs-%s.ldj' % self.step_id)


class DynamicErrorStep1(luigi.Step):
    """
        This dynamic error step raises error to retry the step. retry-count for this step is 3
    """

    retry = 0

    retry_count = 3

    def run(self):
        self.retry += 1
        raise Exception('Test Exception. Retry Index %s for %s' % (self.retry, self.step_family))

    def output(self):
        return luigi.LocalTarget(path='/tmp/_docs-%s.ldj' % self.step_id)


class SuccessStep1(luigi.Step):
    def requires(self):
        return [SuccessSubStep1()]

    def run(self):
        with self.output().open('w') as output:
            output.write('SUCCESS Test Step 4\n')

    def output(self):
        return luigi.LocalTarget(path='/tmp/_docs-%s.ldj' % self.step_id)


class SuccessSubStep1(luigi.Step):
    """
        This success step sleeps for a while and then it is completed successfully.
    """

    def run(self):
        with self.output().open('w') as output:
            output.write('SUCCESS Test Step 4.1\n')

    def output(self):
        return luigi.LocalTarget(path='/tmp/_docs-%s.ldj' % self.step_id)
