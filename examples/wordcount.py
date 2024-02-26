
import trun


class InputText(trun.ExternalStep):
    """
    This class represents something that was created elsewhere by an external process,
    so all we want to do is to implement the output method.
    """
    date = trun.DateParameter()

    def output(self):
        """
        Returns the target output for this step.
        In this case, it expects a file to be present in the local file system.

        :return: the target output for this step.
        :rtype: object (:py:class:`trun.target.Target`)
        """
        return trun.LocalTarget(self.date.strftime('/var/tmp/text/%Y-%m-%d.txt'))


class WordCount(trun.Step):
    date_interval = trun.DateIntervalParameter()

    def requires(self):
        """
        This step's dependencies:

        * :py:class:`~.InputText`

        :return: list of object (:py:class:`trun.step.Step`)
        """
        return [InputText(date) for date in self.date_interval.dates()]

    def output(self):
        """
        Returns the target output for this step.
        In this case, a successful execution of this step will create a file on the local filesystem.

        :return: the target output for this step.
        :rtype: object (:py:class:`trun.target.Target`)
        """
        return trun.LocalTarget('/var/tmp/text-count/%s' % self.date_interval)

    def run(self):
        """
        1. count the words for each of the :py:meth:`~.InputText.output` targets created by :py:class:`~.InputText`
        2. write the count into the :py:meth:`~.WordCount.output` target
        """
        count = {}

        # NOTE: self.input() actually returns an element for the InputText.output() target
        for f in self.input():  # The input() method is a wrapper around requires() that returns Target objects
            for line in f.open('r'):  # Target objects are a file system/format abstraction and this will return a file stream object
                for word in line.strip().split():
                    count[word] = count.get(word, 0) + 1

        # output data
        f = self.output().open('w')
        for word, count in count.items():
            f.write("%s\t%d\n" % (word, count))
        f.close()  # WARNING: file system operations are atomic therefore if you don't close the file you lose all data
