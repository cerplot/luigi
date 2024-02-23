"""
You can run this example like this:

    .. code:: console

            $ luigi --module examples.hello_world examples.HelloWorldStep --local-scheduler

If that does not work, see :ref:`CommandLine`.
"""
import luigi


class HelloWorldStep(luigi.Step):
    step_namespace = 'examples'

    def run(self):
        print("{step} says: Hello world!".format(step=self.__class__.__name__))


if __name__ == '__main__':
    luigi.run(['examples.HelloWorldStep', '--workers', '1', '--local-scheduler'])
