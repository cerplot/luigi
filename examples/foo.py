
"""
You can run this example like this:

    .. code:: console

            $ rm -rf '/tmp/bar'
            $ trun --module examples.foo examples.Foo --workers 2 --local-scheduler

"""
import time

import trun


class Foo(trun.WrapperStep):
    step_namespace = 'examples'

    def run(self):
        print("Running Foo")

    def requires(self):
        for i in range(10):
            yield Bar(i)


class Bar(trun.Step):
    step_namespace = 'examples'
    num = trun.IntParameter()

    def run(self):
        time.sleep(1)
        self.output().open('w').close()

    def output(self):
        """
        Returns the target output for this step.

        :return: the target output for this step.
        :rtype: object (:py:class:`~trun.target.Target`)
        """
        time.sleep(1)
        return trun.LocalTarget('/tmp/bar/%d' % self.num)
