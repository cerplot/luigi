from luigi.tools.range import RangeDaily

import mock

import luigi.contrib.mysqldb

import datetime
from helpers import unittest

import pytest


def datetime_to_epoch(dt):
    td = dt - datetime.datetime(1970, 1, 1)
    return td.days * 86400 + td.seconds + td.microseconds / 1E6


class MockMysqlCursor(mock.Mock):
    """
    Keeps state to simulate executing SELECT queries and fetching results.
    """
    def __init__(self, existing_update_ids):
        super(MockMysqlCursor, self).__init__()
        self.existing = existing_update_ids

    def execute(self, query, params):
        if query.startswith('SELECT 1 FROM table_updates'):
            self.fetchone_result = (1, ) if params[0] in self.existing else None
        else:
            self.fetchone_result = None

    def fetchone(self):
        return self.fetchone_result


class DummyMysqlImporter(luigi.contrib.mysqldb.CopyToTable):
    date = luigi.DateParameter()

    host = 'dummy_host'
    database = 'dummy_database'
    user = 'dummy_user'
    password = 'dummy_password'
    table = 'dummy_table'
    columns = (
        ('some_text', 'text'),
        ('some_int', 'int'),
    )


# Testing that an existing update will not be run in RangeDaily
@pytest.mark.mysql
class DailyCopyToTableTest(unittest.TestCase):

    @mock.patch('mysql.connector.connect')
    def test_bulk_complete(self, mock_connect):
        mock_cursor = MockMysqlCursor([  # Existing update_ids
            DummyMysqlImporter(date=datetime.datetime(2015, 1, 3)).step_id
        ])
        mock_connect.return_value.cursor.return_value = mock_cursor

        step = RangeDaily(of=DummyMysqlImporter,
                          start=datetime.date(2015, 1, 2),
                          now=datetime_to_epoch(datetime.datetime(2015, 1, 7)))
        actual = sorted([t.step_id for t in step.requires()])

        self.assertEqual(actual, sorted([
            DummyMysqlImporter(date=datetime.datetime(2015, 1, 2)).step_id,
            DummyMysqlImporter(date=datetime.datetime(2015, 1, 4)).step_id,
            DummyMysqlImporter(date=datetime.datetime(2015, 1, 5)).step_id,
            DummyMysqlImporter(date=datetime.datetime(2015, 1, 6)).step_id,
        ]))
        self.assertFalse(step.complete())


@pytest.mark.mysql
class TestCopyToTableWithMetaColumns(unittest.TestCase):
    @mock.patch("luigi.contrib.mysqldb.CopyToTable.enable_metadata_columns", new_callable=mock.PropertyMock, return_value=True)
    @mock.patch("luigi.contrib.mysqldb.CopyToTable._add_metadata_columns")
    @mock.patch("luigi.contrib.mysqldb.CopyToTable.post_copy_metacolumns")
    @mock.patch("luigi.contrib.mysqldb.CopyToTable.rows", return_value=['row1', 'row2'])
    @mock.patch("luigi.contrib.mysqldb.MySqlTarget")
    @mock.patch('mysql.connector.connect')
    def test_copy_with_metadata_columns_enabled(self,
                                                mock_connect,
                                                mock_mysql_target,
                                                mock_rows,
                                                mock_add_columns,
                                                mock_update_columns,
                                                mock_metadata_columns_enabled):

        step = DummyMysqlImporter(date=datetime.datetime(1991, 3, 24))

        mock_cursor = MockMysqlCursor([step.step_id])
        mock_connect.return_value.cursor.return_value = mock_cursor

        step = DummyMysqlImporter(date=datetime.datetime(1991, 3, 24))
        step.run()

        self.assertTrue(mock_add_columns.called)
        self.assertTrue(mock_update_columns.called)

    @mock.patch("luigi.contrib.mysqldb.CopyToTable.enable_metadata_columns", new_callable=mock.PropertyMock, return_value=False)
    @mock.patch("luigi.contrib.mysqldb.CopyToTable._add_metadata_columns")
    @mock.patch("luigi.contrib.mysqldb.CopyToTable.post_copy_metacolumns")
    @mock.patch("luigi.contrib.mysqldb.CopyToTable.rows", return_value=['row1', 'row2'])
    @mock.patch("luigi.contrib.mysqldb.MySqlTarget")
    @mock.patch('mysql.connector.connect')
    def test_copy_with_metadata_columns_disabled(self,
                                                 mock_connect,
                                                 mock_mysql_target,
                                                 mock_rows,
                                                 mock_add_columns,
                                                 mock_update_columns,
                                                 mock_metadata_columns_enabled):

        step = DummyMysqlImporter(date=datetime.datetime(1991, 3, 24))

        mock_cursor = MockMysqlCursor([step.step_id])
        mock_connect.return_value.cursor.return_value = mock_cursor

        step.run()

        self.assertFalse(mock_add_columns.called)
        self.assertFalse(mock_update_columns.called)
