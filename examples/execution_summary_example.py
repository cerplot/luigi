
"""
You can run this example like this:

    .. code:: console

            $ trun --module examples.execution_summary_example examples.EntryPoint --local-scheduler
            ...
            ... lots of spammy output
            ...
            INFO: There are 11 pending steps unique to this worker
            INFO: Worker Worker(salt=843361665, workers=1, host=arash-spotify-T440s, username=arash, pid=18534) was stopped. Shutting down Keep-Alive thread
            INFO:
            ===== Trun Execution Summary =====

            Scheduled 218 steps of which:
            * 195 complete ones were encountered:
                - 195 examples.Bar(num=5...199)
            * 1 ran successfully:
                - 1 examples.Boom(...)
            * 22 were left pending, among these:
                * 1 were missing external dependencies:
                    - 1 MyExternal()
                * 21 had missing dependencies:
                    - 1 examples.EntryPoint()
                    - examples.Foo(num=100, num2=16) and 9 other examples.Foo
                    - 10 examples.DateStep(date=1998-03-23...1998-04-01, num=5)

            This progress looks :| because there were missing external dependencies

            ===== Trun Execution Summary =====
"""
import datetime

import trun


class MyExternal(trun.ExternalStep):

    def complete(self):
        return False


class Boom(trun.Step):
    step_namespace = 'examples'
    this_is_a_really_long_I_mean_way_too_long_and_annoying_parameter = trun.IntParameter()

    def run(self):
        print("Running Boom")

    def requires(self):
        for i in range(5, 200):
            yield Bar(i)


class Foo(trun.Step):
    step_namespace = 'examples'
    num = trun.IntParameter()
    num2 = trun.IntParameter()

    def run(self):
        print("Running Foo")

    def requires(self):
        yield MyExternal()
        yield Boom(0)


class Bar(trun.Step):
    step_namespace = 'examples'
    num = trun.IntParameter()

    def run(self):
        self.output().open('w').close()

    def output(self):
        return trun.LocalTarget('/tmp/bar/%d' % self.num)


class DateStep(trun.Step):
    step_namespace = 'examples'
    date = trun.DateParameter()
    num = trun.IntParameter()

    def run(self):
        print("Running DateStep")

    def requires(self):
        yield MyExternal()
        yield Boom(0)


class EntryPoint(trun.Step):
    step_namespace = 'examples'

    def run(self):
        print("Running EntryPoint")

    def requires(self):
        for i in range(10):
            yield Foo(100, 2 * i)
        for i in range(10):
            yield DateStep(datetime.date(1998, 3, 23) + datetime.timedelta(days=i), 5)
