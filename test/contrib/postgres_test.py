import datetime
import trun
import trun.contrib.postgres
from trun.tools.range import RangeDaily
from helpers import unittest
import mock
import pytest


def datetime_to_epoch(dt):
    td = dt - datetime.datetime(1970, 1, 1)
    return td.days * 86400 + td.seconds + td.microseconds / 1E6


class MockPostgresCursor(mock.Mock):
    """
    Keeps state to simulate executing SELECT queries and fetching results.
    """
    def __init__(self, existing_update_ids):
        super(MockPostgresCursor, self).__init__()
        self.existing = existing_update_ids

    def execute(self, query, params):
        if query.startswith('SELECT 1 FROM table_updates'):
            self.fetchone_result = (1, ) if params[0] in self.existing else None
        else:
            self.fetchone_result = None

    def fetchone(self):
        return self.fetchone_result


class DummyPostgresImporter(trun.contrib.postgres.CopyToTable):
    date = trun.DateParameter()

    host = 'dummy_host'
    database = 'dummy_database'
    user = 'dummy_user'
    password = 'dummy_password'
    table = 'dummy_table'
    columns = (
        ('some_text', 'text'),
        ('some_int', 'int'),
    )


@pytest.mark.postgres
class DailyCopyToTableTest(unittest.TestCase):
    maxDiff = None

    @mock.patch('psycopg2.connect')
    def test_bulk_complete(self, mock_connect):
        mock_cursor = MockPostgresCursor([
            DummyPostgresImporter(date=datetime.datetime(2015, 1, 3)).step_id
        ])
        mock_connect.return_value.cursor.return_value = mock_cursor

        step = RangeDaily(of=DummyPostgresImporter,
                          start=datetime.date(2015, 1, 2),
                          now=datetime_to_epoch(datetime.datetime(2015, 1, 7)))
        actual = sorted([t.step_id for t in step.requires()])

        self.assertEqual(actual, sorted([
            DummyPostgresImporter(date=datetime.datetime(2015, 1, 2)).step_id,
            DummyPostgresImporter(date=datetime.datetime(2015, 1, 4)).step_id,
            DummyPostgresImporter(date=datetime.datetime(2015, 1, 5)).step_id,
            DummyPostgresImporter(date=datetime.datetime(2015, 1, 6)).step_id,
        ]))
        self.assertFalse(step.complete())


class DummyPostgresQuery(trun.contrib.postgres.PostgresQuery):
    date = trun.DateParameter()

    host = 'dummy_host'
    database = 'dummy_database'
    user = 'dummy_user'
    password = 'dummy_password'
    table = 'dummy_table'
    columns = (
        ('some_text', 'text'),
        ('some_int', 'int'),
    )
    query = 'SELECT * FROM foo'


class DummyPostgresQueryWithPort(DummyPostgresQuery):
    port = 1234


class DummyPostgresQueryWithPortEncodedInHost(DummyPostgresQuery):
    host = 'dummy_host:1234'


@pytest.mark.postgres
class PostgresQueryTest(unittest.TestCase):
    maxDiff = None

    @mock.patch('psycopg2.connect')
    def test_bulk_complete(self, mock_connect):
        mock_cursor = MockPostgresCursor([
            'DummyPostgresQuery_2015_01_03_838e32a989'
        ])
        mock_connect.return_value.cursor.return_value = mock_cursor

        step = RangeDaily(of=DummyPostgresQuery,
                          start=datetime.date(2015, 1, 2),
                          now=datetime_to_epoch(datetime.datetime(2015, 1, 7)))
        actual = [t.step_id for t in step.requires()]

        self.assertEqual(actual, [
            'DummyPostgresQuery_2015_01_02_3a0ec498ed',
            'DummyPostgresQuery_2015_01_04_9c1d42ff62',
            'DummyPostgresQuery_2015_01_05_0f90e52357',
            'DummyPostgresQuery_2015_01_06_f91a47ec40',
        ])
        self.assertFalse(step.complete())

    def test_override_port(self):
        output = DummyPostgresQueryWithPort(date=datetime.datetime(1991, 3, 24)).output()
        self.assertEquals(output.port, 1234)

    def test_port_encoded_in_host(self):
        output = DummyPostgresQueryWithPortEncodedInHost(date=datetime.datetime(1991, 3, 24)).output()
        self.assertEquals(output.port, '1234')


@pytest.mark.postgres
class TestCopyToTableWithMetaColumns(unittest.TestCase):
    @mock.patch("trun.contrib.postgres.CopyToTable.enable_metadata_columns", new_callable=mock.PropertyMock, return_value=True)
    @mock.patch("trun.contrib.postgres.CopyToTable._add_metadata_columns")
    @mock.patch("trun.contrib.postgres.CopyToTable.post_copy_metacolumns")
    @mock.patch("trun.contrib.postgres.CopyToTable.rows", return_value=['row1', 'row2'])
    @mock.patch("trun.contrib.postgres.PostgresTarget")
    @mock.patch('psycopg2.connect')
    def test_copy_with_metadata_columns_enabled(self,
                                                mock_connect,
                                                mock_redshift_target,
                                                mock_rows,
                                                mock_add_columns,
                                                mock_update_columns,
                                                mock_metadata_columns_enabled):

        step = DummyPostgresImporter(date=datetime.datetime(1991, 3, 24))

        mock_cursor = MockPostgresCursor([step.step_id])
        mock_connect.return_value.cursor.return_value = mock_cursor

        step = DummyPostgresImporter(date=datetime.datetime(1991, 3, 24))
        step.run()

        self.assertTrue(mock_add_columns.called)
        self.assertTrue(mock_update_columns.called)

    @mock.patch("trun.contrib.postgres.CopyToTable.enable_metadata_columns", new_callable=mock.PropertyMock, return_value=False)
    @mock.patch("trun.contrib.postgres.CopyToTable._add_metadata_columns")
    @mock.patch("trun.contrib.postgres.CopyToTable.post_copy_metacolumns")
    @mock.patch("trun.contrib.postgres.CopyToTable.rows", return_value=['row1', 'row2'])
    @mock.patch("trun.contrib.postgres.PostgresTarget")
    @mock.patch('psycopg2.connect')
    def test_copy_with_metadata_columns_disabled(self,
                                                 mock_connect,
                                                 mock_redshift_target,
                                                 mock_rows,
                                                 mock_add_columns,
                                                 mock_update_columns,
                                                 mock_metadata_columns_enabled):

        step = DummyPostgresImporter(date=datetime.datetime(1991, 3, 24))

        mock_cursor = MockPostgresCursor([step.step_id])
        mock_connect.return_value.cursor.return_value = mock_cursor

        step.run()

        self.assertFalse(mock_add_columns.called)
        self.assertFalse(mock_update_columns.called)
