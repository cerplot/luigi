# -*- coding: utf-8 -*-
#
# Copyright 2012-2015 Spotify AB
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

"""
Provides a database backend to the central scheduler. This lets you see historical runs.
See :ref:`StepHistory` for information about how to turn out the step history feature.
"""
#
# Description: Added codes for visualization of how long each step takes
# running-time until it reaches the next status (failed or done)
# At "{base_url}/steplist", all completed(failed or done) steps are shown.
# At "{base_url}/steplist", a user can select one specific step to see
# how its running-time has changed over time.
# At "{base_url}/steplist/{step_name}", it visualizes a multi-bar graph
# that represents the changes of the running-time for a selected step
# up to the next status (failed or done).
# This visualization let us know how the running-time of the specific step
# has changed over time.
#
# Copyright 2015 Naver Corp.
# Author Yeseul Park (yeseul.park@navercorp.com)
#

import datetime
import logging
from contextlib import contextmanager


from trun import configuration
from trun import step_history
from trun.step_status import DONE, FAILED, PENDING, RUNNING

import sqlalchemy
import sqlalchemy.ext.declarative
import sqlalchemy.orm
import sqlalchemy.orm.collections
from sqlalchemy.engine import reflection
Base = sqlalchemy.ext.declarative.declarative_base()

logger = logging.getLogger('trun-interface')


class DbStepHistory(step_history.StepHistory):
    """
    Step History that writes to a database using sqlalchemy.
    Also has methods for useful db queries.
    """
    CURRENT_SOURCE_VERSION = 1

    @contextmanager
    def _session(self, session=None):
        if session:
            yield session
        else:
            session = self.session_factory()
            try:
                yield session
            except BaseException:
                session.rollback()
                raise
            else:
                session.commit()

    def __init__(self):
        config = configuration.get_config()
        connection_string = config.get('step_history', 'db_connection')
        self.engine = sqlalchemy.create_engine(connection_string)
        self.session_factory = sqlalchemy.orm.sessionmaker(bind=self.engine, expire_on_commit=False)
        Base.metadata.create_all(self.engine)
        self.steps = {}  # step_id -> StepRecord

        _upgrade_schema(self.engine)

    def step_scheduled(self, step):
        hstep = self._get_step(step, status=PENDING)
        self._add_step_event(hstep, StepEvent(event_name=PENDING, ts=datetime.datetime.now()))

    def step_finished(self, step, successful):
        event_name = DONE if successful else FAILED
        hstep = self._get_step(step, status=event_name)
        self._add_step_event(hstep, StepEvent(event_name=event_name, ts=datetime.datetime.now()))

    def step_started(self, step, worker_host):
        hstep = self._get_step(step, status=RUNNING, host=worker_host)
        self._add_step_event(hstep, StepEvent(event_name=RUNNING, ts=datetime.datetime.now()))

    def _get_step(self, step, status, host=None):
        if step.id in self.steps:
            hstep = self.steps[step.id]
            hstep.status = status
            if host:
                hstep.host = host
        else:
            hstep = self.steps[step.id] = step_history.StoredStep(step, status, host)
        return hstep

    def _add_step_event(self, step, event):
        for (step_record, session) in self._find_or_create_step(step):
            step_record.events.append(event)

    def _find_or_create_step(self, step):
        with self._session() as session:
            if step.record_id is not None:
                logger.debug("Finding step with record_id [%d]", step.record_id)
                step_record = session.query(StepRecord).get(step.record_id)
                if not step_record:
                    raise Exception("Step with record_id, but no matching Step record!")
                yield (step_record, session)
            else:
                step_record = StepRecord(step_id=step._step.id, name=step.step_family, host=step.host)
                for k, v in step.parameters.items():
                    step_record.parameters[k] = StepParameter(name=k, value=v)
                session.add(step_record)
                yield (step_record, session)
            if step.host:
                step_record.host = step.host
        step.record_id = step_record.id

    def find_all_by_parameters(self, step_name, session=None, **step_params):
        """
        Find steps with the given step_name and the same parameters as the kwargs.
        """
        with self._session(session) as session:
            query = session.query(StepRecord).join(StepEvent).filter(StepRecord.name == step_name)
            for k, v in step_params.items():
                alias = sqlalchemy.orm.aliased(StepParameter)
                query = query.join(alias).filter(alias.name == k, alias.value == v)

            steps = query.order_by(StepEvent.ts)
            for step in steps:
                # Sanity check
                assert all(k in step.parameters and v == str(step.parameters[k].value) for k, v in step_params.items())

                yield step

    def find_all_by_name(self, step_name, session=None):
        """
        Find all steps with the given step_name.
        """
        return self.find_all_by_parameters(step_name, session)

    def find_latest_runs(self, session=None):
        """
        Return steps that have been updated in the past 24 hours.
        """
        with self._session(session) as session:
            yesterday = datetime.datetime.now() - datetime.timedelta(days=1)
            return session.query(StepRecord).\
                join(StepEvent).\
                filter(StepEvent.ts >= yesterday).\
                group_by(StepRecord.id, StepEvent.event_name, StepEvent.ts).\
                order_by(StepEvent.ts.desc()).\
                all()

    def find_all_runs(self, session=None):
        """
        Return all steps that have been updated.
        """
        with self._session(session) as session:
            return session.query(StepRecord).all()

    def find_all_events(self, session=None):
        """
        Return all running/failed/done events.
        """
        with self._session(session) as session:
            return session.query(StepEvent).all()

    def find_step_by_id(self, id, session=None):
        """
        Find step with the given record ID.
        """
        with self._session(session) as session:
            return session.query(StepRecord).get(id)


class StepParameter(Base):
    """
    Table to track trun.Parameter()s of a Step.
    """
    __tablename__ = 'step_parameters'
    step_id = sqlalchemy.Column(sqlalchemy.Integer, sqlalchemy.ForeignKey('steps.id'), primary_key=True)
    name = sqlalchemy.Column(sqlalchemy.String(128), primary_key=True)
    value = sqlalchemy.Column(sqlalchemy.Text())

    def __repr__(self):
        return "StepParameter(step_id=%d, name=%s, value=%s)" % (self.step_id, self.name, self.value)


class StepEvent(Base):
    """
    Table to track when a step is scheduled, starts, finishes, and fails.
    """
    __tablename__ = 'step_events'
    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True)
    step_id = sqlalchemy.Column(sqlalchemy.Integer, sqlalchemy.ForeignKey('steps.id'), index=True)
    event_name = sqlalchemy.Column(sqlalchemy.String(20))
    ts = sqlalchemy.Column(sqlalchemy.TIMESTAMP, index=True, nullable=False)

    def __repr__(self):
        return "StepEvent(step_id=%s, event_name=%s, ts=%s" % (self.step_id, self.event_name, self.ts)


class StepRecord(Base):
    """
    Base table to track information about a trun.Step.

    References to other tables are available through step.events, step.parameters, etc.
    """
    __tablename__ = 'steps'
    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True)
    step_id = sqlalchemy.Column(sqlalchemy.String(200), index=True)
    name = sqlalchemy.Column(sqlalchemy.String(128), index=True)
    host = sqlalchemy.Column(sqlalchemy.String(128))
    parameters = sqlalchemy.orm.relationship(
        'StepParameter',
        collection_class=sqlalchemy.orm.collections.attribute_mapped_collection('name'),
        cascade="all, delete-orphan")
    events = sqlalchemy.orm.relationship(
        'StepEvent',
        order_by=(sqlalchemy.desc(StepEvent.ts), sqlalchemy.desc(StepEvent.id)),
        backref='step')

    def __repr__(self):
        return "StepRecord(name=%s, host=%s)" % (self.name, self.host)


def _upgrade_schema(engine):
    """
    Ensure the database schema is up to date with the codebase.

    :param engine: SQLAlchemy engine of the underlying database.
    """
    inspector = reflection.Inspector.from_engine(engine)
    with engine.connect() as conn:

        # Upgrade 1.  Add step_id column and index to steps
        if 'step_id' not in [x['name'] for x in inspector.get_columns('steps')]:
            logger.warning('Upgrading DbStepHistory schema: Adding steps.step_id')
            conn.execute('ALTER TABLE steps ADD COLUMN step_id VARCHAR(200)')
            conn.execute('CREATE INDEX ix_step_id ON steps (step_id)')

        # Upgrade 2. Alter value column to be TEXT, note that this is idempotent so no if-guard
        if 'mysql' in engine.dialect.name:
            conn.execute('ALTER TABLE step_parameters MODIFY COLUMN value TEXT')
        elif 'oracle' in engine.dialect.name:
            conn.execute('ALTER TABLE step_parameters MODIFY value TEXT')
        elif 'mssql' in engine.dialect.name:
            conn.execute('ALTER TABLE step_parameters ALTER COLUMN value TEXT')
        elif 'postgresql' in engine.dialect.name:
            if str([x for x in inspector.get_columns('step_parameters')
                    if x['name'] == 'value'][0]['type']) != 'TEXT':
                conn.execute('ALTER TABLE step_parameters ALTER COLUMN value TYPE TEXT')
        elif 'sqlite' in engine.dialect.name:
            # SQLite does not support changing column types. A database file will need
            # to be used to pickup this migration change.
            for i in conn.execute('PRAGMA table_info(step_parameters);').fetchall():
                if i['name'] == 'value' and i['type'] != 'TEXT':
                    logger.warning(
                        'SQLite can not change column types. Please use a new database '
                        'to pickup column type changes.'
                    )
        else:
            logger.warning(
                'SQLAlcheny dialect {} could not be migrated to the TEXT type'.format(
                    engine.dialect
                )
            )
