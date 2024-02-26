
import random

import trun
import trun.format
import trun.contrib.hdfs
from trun.contrib.spark import SparkSubmitStep


class UserItemMatrix(trun.Step):

    #: the size of the data being generated
    data_size = trun.IntParameter()

    def run(self):
        """
        Generates :py:attr:`~.UserItemMatrix.data_size` elements.
        Writes this data in \\ separated value format into the target :py:func:`~/.UserItemMatrix.output`.

        The data has the following elements:

        * `user` is the default Elasticsearch id field,
        * `track`: the text,
        * `rating`: the day when the data was created.

        """
        w = self.output().open('w')
        for user in range(self.data_size):
            track = int(random.random() * self.data_size)
            w.write('%d\\%d\\%f' % (user, track, 1.0))
        w.close()

    def output(self):
        """
        Returns the target output for this step.
        In this case, a successful execution of this step will create a file in HDFS.

        :return: the target output for this step.
        :rtype: object (:py:class:`~trun.target.Target`)
        """
        return trun.contrib.hdfs.HdfsTarget('data-matrix', format=trun.format.Gzip)


class SparkALS(SparkSubmitStep):
    """
    This step runs a :py:class:`trun.contrib.spark.SparkSubmitStep` step
    over the target data returned by :py:meth:`~/.UserItemMatrix.output` and
    writes the result into its :py:meth:`~.SparkALS.output` target (a file in HDFS).

    This class uses :py:meth:`trun.contrib.spark.SparkSubmitStep.run`.

    Example trun configuration::

        [spark]
        spark-submit: /usr/local/spark/bin/spark-submit
        master: yarn-client

    """
    data_size = trun.IntParameter(default=1000)

    driver_memory = '2g'
    executor_memory = '3g'
    num_executors = trun.IntParameter(default=100)

    app = 'my-spark-assembly.jar'
    entry_class = 'com.spotify.spark.ImplicitALS'

    def app_options(self):
        # These are passed to the Spark main args in the defined order.
        return [self.input().path, self.output().path]

    def requires(self):
        """
        This step's dependencies:

        * :py:class:`~.UserItemMatrix`

        :return: object (:py:class:`trun.step.Step`)
        """
        return UserItemMatrix(self.data_size)

    def output(self):
        """
        Returns the target output for this step.
        In this case, a successful execution of this step will create a file in HDFS.

        :return: the target output for this step.
        :rtype: object (:py:class:`~trun.target.Target`)
        """
        # The corresponding Spark job outputs as GZip format.
        return trun.contrib.hdfs.HdfsTarget('als-output/', format=trun.format.Gzip)


'''
// Corresponding example Spark Job, a wrapper around the MLLib ALS job.
// This class would have to be jarred into my-spark-assembly.jar
// using sbt assembly (or package) and made available to the Trun job
// above.

package com.spotify.spark

import org.apache.spark._
import org.apache.spark.mllib.recommendation.{Rating, ALS}
import org.apache.hadoop.io.compress.GzipCodec

object ImplicitALS {

  def main(args: Array[String]) {
    val sc = new SparkContext(args(0), "ImplicitALS")
    val input = args(1)
    val output = args(2)

    val ratings = sc.textFile(input)
      .map { l: String =>
        val t = l.split('\t')
        Rating(t(0).toInt, t(1).toInt, t(2).toFloat)
      }

    val model = ALS.trainImplicit(ratings, 40, 20, 0.8, 150)
    model
      .productFeatures
      .map { case (id, vec) =>
        id + "\t" + vec.map(d => "%.6f".format(d)).mkString(" ")
      }
      .saveAsTextFile(output, classOf[GzipCodec])

    sc.stop()
  }
}
'''
