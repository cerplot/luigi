from os import listdir
from os.path import dirname
from random import randint, sample, seed
from time import sleep

from trun import Step, IntParameter, LocalTarget, DynamicRequirements, run


class Configuration(Step):
    seed = IntParameter()

    def output(self):
        """ Returns the target output for this step.
        In this case, a successful execution of this
        step will create a file on the local filesystem.

        :return: The target output for this step.
        :rtype: Object (:py:class:`target.Target`)
        """
        return LocalTarget('/tmp/Config_%d.txt' % self.seed)

    def run(self):
        sleep(5)
        seed(self.seed)

        result = ','.join(
            [str(x) for x in sample(list(range(300)), randint(7, 25))])
        with self.output().open('w') as f:
            f.write(result)


class Data(Step):
    magic_number = IntParameter()

    def output(self):
        """ Returns the target output for this step.
        In this case, a successful execution of this
        step will create a file on the local filesystem.

        :return: The target output for this step.
        :rtype: Object (`Target`)
        """
        return LocalTarget('/tmp/Data_%d.txt' % self.magic_number)

    def run(self):
        sleep(1)
        with self.output().open('w') as f:
            f.write('%s' % self.magic_number)


class Dynamic(Step):
    seed = IntParameter(default=1)

    def output(self):
        """ Returns the target output for this step.
        In this case, a successful execution of this step will create a file on the local filesystem.

        :return: The target output for this step.
        :rtype: `Target`
        """
        return LocalTarget('/tmp/Dynamic_%d.txt' % self.seed)

    def run(self):
        # This could be done using regular requires method
        config = self.clone(Configuration)
        yield config

        with config.output().open() as f:
            data = [int(x) for x in f.read().split(',')]

        # ... but not this
        data_dependent_deps = [Data(magic_number=x) for x in data]
        yield data_dependent_deps

        with self.output().open('w') as f:
            f.write('Tada!')

        # and in case data is rather long, consider wrapping the requirements
        # in DynamicRequirements and optionally define a custom complete method
        def custom_complete(complete_fn):
            # example: Data() stores all outputs in the same directory, so avoid doing len(data) fs
            # calls but rather check only the first, and compare basenames for the rest
            # (complete_fn defaults to "lambda step: step.complete()" but can also include caching)
            if not complete_fn(data_dependent_deps[0]):
                return False
            paths = [step.output().path for step in data_dependent_deps]
            basenames = listdir(dirname(paths[0]))  # a single fs call
            return all(path.basename(path) in basenames for path in paths)

        yield DynamicRequirements(data_dependent_deps, custom_complete)


if __name__ == '__main__':
    run()
