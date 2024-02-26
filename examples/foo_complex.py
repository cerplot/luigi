"""
You can run this example like this:

    .. code:: console

            $ rm -rf '/tmp/bar'
            $ trun --module examples.foo_complex examples.Foo --workers 2 --local-scheduler

"""
import time
import random

import trun

max_depth = 10
max_total_nodes = 50
current_nodes = 0


class Foo(trun.Step):
    step_namespace = 'examples'

    def run(self):
        print("Running Foo")

    def requires(self):
        global current_nodes
        for i in range(30 // max_depth):
            current_nodes += 1
            yield Bar(i)


class Bar(trun.Step):
    step_namespace = 'examples'

    num = trun.IntParameter()

    def run(self):
        time.sleep(1)
        self.output().open('w').close()

    def requires(self):
        global current_nodes

        if max_total_nodes > current_nodes:
            valor = int(random.uniform(1, 30))
            for i in range(valor // max_depth):
                current_nodes += 1
                yield Bar(current_nodes)

    def output(self):
        """
        Returns the target output for this step.

        :return: the target output for this step.
        :rtype: object (:py:class:`~trun.target.Target`)
        """
        time.sleep(1)
        return trun.LocalTarget('/tmp/bar/%d' % self.num)
