"""
This file implements unit test cases for trun/contrib/sqla.py
Author: Gouthaman Balaraman
Date: 01/02/2015
"""
import os
import shutil
import tempfile
import unittest

import trun
import sqlalchemy
from trun.contrib import sqla
from trun.mock import MockTarget
import pytest
from helpers import skipOnTravisAndGithubActions


class BaseStep(trun.Step):

    STEP_LIST = ["item%d\tproperty%d\n" % (i, i) for i in range(10)]

    def output(self):
        return MockTarget("BaseStep", mirror_on_stderr=True)

    def run(self):
        out = self.output().open("w")
        for step in self.STEP_LIST:
            out.write(step)
        out.close()


@pytest.mark.contrib
class TestSQLA(unittest.TestCase):
    NUM_WORKERS = 1

    def _clear_tables(self):
        meta = sqlalchemy.MetaData()
        meta.reflect(bind=self.engine)
        for table in reversed(meta.sorted_tables):
            self.engine.execute(table.delete())

    def setUp(self):
        self.tempdir = tempfile.mkdtemp()
        self.connection_string = self.get_connection_string()
        self.connect_args = {'timeout': 5.0}
        self.engine = sqlalchemy.create_engine(self.connection_string, connect_args=self.connect_args)

        # Create SQLAStep and store in self
        class SQLAStep(sqla.CopyToTable):
            columns = [
                (["item", sqlalchemy.String(64)], {}),
                (["property", sqlalchemy.String(64)], {})
            ]
            connection_string = self.connection_string
            connect_args = self.connect_args
            table = "item_property"
            chunk_size = 1

            def requires(self):
                return BaseStep()

        self.SQLAStep = SQLAStep

    def tearDown(self):
        self._clear_tables()
        if os.path.exists(self.tempdir):
            shutil.rmtree(self.tempdir)

    def get_connection_string(self, db='sqlatest.db'):
        return "sqlite:///{path}".format(path=os.path.join(self.tempdir, db))

    def test_create_table(self):
        """
        Test that this method creates table that we require
        :return:
        """
        class TestSQLData(sqla.CopyToTable):
            connection_string = self.connection_string
            connect_args = self.connect_args
            table = "test_table"
            columns = [
                (["id", sqlalchemy.Integer], dict(primary_key=True)),
                (["name", sqlalchemy.String(64)], {}),
                (["value", sqlalchemy.String(64)], {})
            ]
            chunk_size = 1

            def output(self):
                pass

        sql_copy = TestSQLData()
        eng = sqlalchemy.create_engine(TestSQLData.connection_string)
        self.assertFalse(eng.dialect.has_table(eng.connect(), TestSQLData.table))
        sql_copy.create_table(eng)
        self.assertTrue(eng.dialect.has_table(eng.connect(), TestSQLData.table))
        # repeat and ensure it just binds to existing table
        sql_copy.create_table(eng)

    def test_create_table_raises_no_columns(self):
        """
        Check that the test fails when the columns are not set
        :return:
        """
        class TestSQLData(sqla.CopyToTable):
            connection_string = self.connection_string
            table = "test_table"
            columns = []
            chunk_size = 1

        def output(self):
            pass

        sql_copy = TestSQLData()
        eng = sqlalchemy.create_engine(TestSQLData.connection_string)
        self.assertRaises(NotImplementedError, sql_copy.create_table, eng)

    def _check_entries(self, engine):
        with engine.begin() as conn:
            meta = sqlalchemy.MetaData()
            meta.reflect(bind=engine)
            self.assertEqual({'table_updates', 'item_property'}, set(meta.tables.keys()))
            table = meta.tables[self.SQLAStep.table]
            s = sqlalchemy.select([sqlalchemy.func.count(table.c.item)])
            result = conn.execute(s).fetchone()
            self.assertEqual(len(BaseStep.STEP_LIST), result[0])
            s = sqlalchemy.select([table]).order_by(table.c.item)
            result = conn.execute(s).fetchall()
            for i in range(len(BaseStep.STEP_LIST)):
                given = BaseStep.STEP_LIST[i].strip("\n").split("\t")
                given = (str(given[0]), str(given[1]))
                self.assertEqual(given, tuple(result[i]))

    def test_rows(self):
        step, step0 = self.SQLAStep(), BaseStep()
        trun.build([step, step0], local_scheduler=True, workers=self.NUM_WORKERS)

        for i, row in enumerate(step.rows()):
            given = BaseStep.STEP_LIST[i].strip("\n").split("\t")
            self.assertEqual(row, given)

    def test_run(self):
        """
        Checking that the runs go as expected. Rerunning the same shouldn't end up
        inserting more rows into the db.
        :return:
        """
        step, step0 = self.SQLAStep(), BaseStep()
        self.engine = sqlalchemy.create_engine(step.connection_string)
        trun.build([step0, step], local_scheduler=True)
        self._check_entries(self.engine)

        # rerun and the num entries should be the same
        trun.build([step0, step], local_scheduler=True, workers=self.NUM_WORKERS)
        self._check_entries(self.engine)

    def test_run_with_chunk_size(self):
        """
        The chunk_size can be specified in order to control the batch size for inserts.
        :return:
        """
        step, step0 = self.SQLAStep(), BaseStep()
        self.engine = sqlalchemy.create_engine(step.connection_string)
        step.chunk_size = 2  # change chunk size and check it runs ok
        trun.build([step, step0], local_scheduler=True, workers=self.NUM_WORKERS)
        self._check_entries(self.engine)

    def test_reflect(self):
        """
        If the table is setup already, then one can set reflect to True, and
        completely skip the columns part. It is not even required at that point.
        :return:
        """
        SQLAStep = self.SQLAStep

        class AnotherSQLAStep(sqla.CopyToTable):
            connection_string = self.connection_string
            table = "item_property"
            reflect = True
            chunk_size = 1

            def requires(self):
                return SQLAStep()

            def copy(self, conn, ins_rows, table_bound):
                ins = table_bound.update().\
                    where(table_bound.c.property == sqlalchemy.bindparam("_property")).\
                    values({table_bound.c.item: sqlalchemy.bindparam("_item")})
                conn.execute(ins, ins_rows)

            def rows(self):
                for line in BaseStep.STEP_LIST:
                    yield line.strip("\n").split("\t")

        step0, step1, step2 = AnotherSQLAStep(), self.SQLAStep(), BaseStep()
        trun.build([step0, step1, step2], local_scheduler=True, workers=self.NUM_WORKERS)
        self._check_entries(self.engine)

    def test_create_marker_table(self):
        """
        Is the marker table created as expected for the SQLAlchemyTarget
        :return:
        """
        target = sqla.SQLAlchemyTarget(self.connection_string, "test_table", "12312123")
        target.create_marker_table()
        self.assertTrue(target.engine.dialect.has_table(target.engine.connect(), target.marker_table))

    def test_touch(self):
        """
        Touch takes care of creating a checkpoint for step completion
        :return:
        """
        target = sqla.SQLAlchemyTarget(self.connection_string, "test_table", "12312123")
        target.create_marker_table()
        self.assertFalse(target.exists())
        target.touch()
        self.assertTrue(target.exists())

    def test_row_overload(self):
        """Overload the rows method and we should be able to insert data into database"""

        class SQLARowOverloadTest(sqla.CopyToTable):
            columns = [
                (["item", sqlalchemy.String(64)], {}),
                (["property", sqlalchemy.String(64)], {})
            ]
            connection_string = self.connection_string
            table = "item_property"
            chunk_size = 1

            def rows(self):
                steps = [("item0", "property0"), ("item1", "property1"), ("item2", "property2"), ("item3", "property3"),
                         ("item4", "property4"), ("item5", "property5"), ("item6", "property6"), ("item7", "property7"),
                         ("item8", "property8"), ("item9", "property9")]
                for row in steps:
                    yield row

        step = SQLARowOverloadTest()
        trun.build([step], local_scheduler=True, workers=self.NUM_WORKERS)
        self._check_entries(self.engine)

    def test_column_row_separator(self):
        """
        Test alternate column row separator works
        :return:
        """
        class ModBaseStep(trun.Step):

            def output(self):
                return MockTarget("ModBaseStep", mirror_on_stderr=True)

            def run(self):
                out = self.output().open("w")
                steps = ["item%d,property%d\n" % (i, i) for i in range(10)]
                for step in steps:
                    out.write(step)
                out.close()

        class ModSQLAStep(sqla.CopyToTable):
            columns = [
                (["item", sqlalchemy.String(64)], {}),
                (["property", sqlalchemy.String(64)], {})
            ]
            connection_string = self.connection_string
            table = "item_property"
            column_separator = ","
            chunk_size = 1

            def requires(self):
                return ModBaseStep()

        step1, step2 = ModBaseStep(), ModSQLAStep()
        trun.build([step1, step2], local_scheduler=True, workers=self.NUM_WORKERS)
        self._check_entries(self.engine)

    def test_update_rows_test(self):
        """
        Overload the copy() method and implement an update action.
        :return:
        """
        class ModBaseStep(trun.Step):

            def output(self):
                return MockTarget("BaseStep", mirror_on_stderr=True)

            def run(self):
                out = self.output().open("w")
                for step in self.STEP_LIST:
                    out.write("dummy_" + step)
                out.close()

        class ModSQLAStep(sqla.CopyToTable):
            connection_string = self.connection_string
            table = "item_property"
            columns = [
                (["item", sqlalchemy.String(64)], {}),
                (["property", sqlalchemy.String(64)], {})
            ]
            chunk_size = 1

            def requires(self):
                return ModBaseStep()

        class UpdateSQLAStep(sqla.CopyToTable):
            connection_string = self.connection_string
            table = "item_property"
            reflect = True
            chunk_size = 1

            def requires(self):
                return ModSQLAStep()

            def copy(self, conn, ins_rows, table_bound):
                ins = table_bound.update().\
                    where(table_bound.c.property == sqlalchemy.bindparam("_property")).\
                    values({table_bound.c.item: sqlalchemy.bindparam("_item")})
                conn.execute(ins, ins_rows)

            def rows(self):
                for step in self.STEP_LIST:
                    yield step.strip("\n").split("\t")

        # Running only step1, and step2 should fail
        step1, step2, step3 = ModBaseStep(), ModSQLAStep(), UpdateSQLAStep()
        trun.build([step1, step2, step3], local_scheduler=True, workers=self.NUM_WORKERS)
        self._check_entries(self.engine)

    @skipOnTravisAndGithubActions('AssertionError: 10 != 7; https://travis-ci.org/spotify/trun/jobs/156732446')
    def test_multiple_steps(self):
        """
        Test a case where there are multiple steps
        :return:
        """
        class SmallSQLAStep(sqla.CopyToTable):
            item = trun.Parameter()
            property = trun.Parameter()
            columns = [
                (["item", sqlalchemy.String(64)], {}),
                (["property", sqlalchemy.String(64)], {})
            ]
            connection_string = self.connection_string
            table = "item_property"
            chunk_size = 1

            def rows(self):
                yield (self.item, self.property)

        class ManyBaseStep(trun.Step):
            def requires(self):
                for t in BaseStep.STEP_LIST:
                    item, property = t.strip().split("\t")
                    yield SmallSQLAStep(item=item, property=property)

        step2 = ManyBaseStep()
        trun.build([step2], local_scheduler=True, workers=self.NUM_WORKERS)
        self._check_entries(self.engine)

    def test_multiple_engines(self):
        """
        Test case where different steps require different SQL engines.
        """
        alt_db = self.get_connection_string("sqlatest2.db")

        class MultiEngineStep(self.SQLAStep):
            connection_string = alt_db

        step0, step1, step2 = BaseStep(), self.SQLAStep(), MultiEngineStep()
        self.assertTrue(step1.output().engine != step2.output().engine)
        trun.build([step2, step1, step0], local_scheduler=True, workers=self.NUM_WORKERS)
        self._check_entries(step1.output().engine)
        self._check_entries(step2.output().engine)


@pytest.mark.contrib
class TestSQLA2(TestSQLA):
    """ 2 workers version
    """
    NUM_WORKERS = 2
