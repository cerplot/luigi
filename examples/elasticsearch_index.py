
import datetime
import json

import trun
from trun.contrib.esindex import CopyToIndex


class FakeDocuments(trun.Step):
    """
    Generates a local file containing 5 elements of data in JSON format.
    """

    #: the date parameter.
    date = trun.DateParameter(default=datetime.date.today())

    def run(self):
        """
        Writes data in JSON format into the step's output target.

        The data objects have the following attributes:

        * `_id` is the default Elasticsearch id field,
        * `text`: the text,
        * `date`: the day when the data was created.

        """
        today = datetime.date.today()
        with self.output().open('w') as output:
            for i in range(5):
                output.write(json.dumps({'_id': i, 'text': 'Hi %s' % i,
                                         'date': str(today)}))
                output.write('\n')

    def output(self):
        """
        Returns the target output for this step.
        In this case, a successful execution of this step will create a file on the local filesystem.

        :return: the target output for this step.
        :rtype: object (:py:class:`trun.target.Target`)
        """
        return trun.LocalTarget(path='/tmp/_docs-%s.ldj' % self.date)


class IndexDocuments(CopyToIndex):
    """
    This step loads JSON data contained in a :py:class:`trun.target.Target` into an ElasticSearch index.

    This step's input will the target returned by :py:meth:`~.FakeDocuments.output`.

    This class uses :py:meth:`trun.contrib.esindex.CopyToIndex.run`.

    After running this step you can run:

    .. code-block:: console

        $ curl "localhost:9200/example_index/_search?pretty"

    to see the indexed documents.

    To see the update log, run

    .. code-block:: console

        $ curl "localhost:9200/update_log/_search?q=target_index:example_index&pretty"

    To cleanup both indexes run:

    .. code-block:: console

        $ curl -XDELETE "localhost:9200/example_index"
        $ curl -XDELETE "localhost:9200/update_log/_query?q=target_index:example_index"

    """
    #: date step parameter (default = today)
    date = trun.DateParameter(default=datetime.date.today())

    #: the name of the index in ElasticSearch to be updated.
    index = 'example_index'
    #: the name of the document type.
    doc_type = 'greetings'
    #: the host running the ElasticSearch service.
    host = 'localhost'
    #: the port used by the ElasticSearch service.
    port = 9200

    def requires(self):
        """
        This step's dependencies:

        * :py:class:`~.FakeDocuments`

        :return: object (:py:class:`trun.step.Step`)
        """
        return FakeDocuments()


if __name__ == "__main__":
    trun.run(['IndexDocuments', '--local-scheduler'])
