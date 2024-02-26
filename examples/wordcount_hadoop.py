
import trun
import trun.contrib.hadoop
import trun.contrib.hdfs


# To make this run, you probably want to edit /etc/trun/client.cfg and add something like:
#
# [hadoop]
# jar: /usr/lib/hadoop-xyz/hadoop-streaming-xyz-123.jar


class InputText(trun.ExternalStep):
    """
    This step is a :py:class:`trun.step.ExternalStep` which means it doesn't generate the
    :py:meth:`~.InputText.output` target on its own instead relying on the execution something outside of Trun
    to produce it.
    """

    date = trun.DateParameter()

    def output(self):
        """
        Returns the target output for this step.
        In this case, it expects a file to be present in HDFS.

        :return: the target output for this step.
        :rtype: object (:py:class:`trun.target.Target`)
        """
        return trun.contrib.hdfs.HdfsTarget(self.date.strftime('/tmp/text/%Y-%m-%d.txt'))


class WordCount(trun.contrib.hadoop.JobStep):
    """
    This step runs a :py:class:`trun.contrib.hadoop.JobStep`
    over the target data returned by :py:meth:`~/.InputText.output` and
    writes the result into its :py:meth:`~.WordCount.output` target.

    This class uses :py:meth:`trun.contrib.hadoop.JobStep.run`.
    """

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
        In this case, a successful execution of this step will create a file in HDFS.

        :return: the target output for this step.
        :rtype: object (:py:class:`trun.target.Target`)
        """
        return trun.contrib.hdfs.HdfsTarget('/tmp/text-count/%s' % self.date_interval)

    def mapper(self, line):
        for word in line.strip().split():
            yield word, 1

    def reducer(self, key, values):
        yield key, sum(values)


if __name__ == '__main__':
    trun.run()
