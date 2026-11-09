"""Exercise real coverage SQL with transaction-local output/state fixtures."""
import os
from contextlib import contextmanager
from dataclasses import replace
from datetime import date

import psycopg2.extras
import pytest

from service.data_coverage.registry import COVERAGE_RULES, CoverageRuleRegistry
from service.data_coverage.repository import CoverageRepository
from service.db import get_conn


class FixtureCursor(psycopg2.extras.RealDictCursor):
    def execute(self, query, vars=None):
        if isinstance(query, str):
            query = query.replace('orchestration_v2.dataset_state', 'pg_temp.dataset_state')
            query = query.replace('orchestration_v2.task_execution', 'pg_temp.task_execution')
        return super().execute(query, vars)


@pytest.mark.skipif(os.getenv('RUN_DB_INTEGRATION') != '1', reason='requires PostgreSQL')
def test_derived_reaudit_retires_old_failure_but_rejects_bad_output():
    conn = get_conn()

    class FixtureConnection:
        def cursor(self, **kwargs):
            return conn.cursor(cursor_factory=FixtureCursor)

    class Repository(CoverageRepository):
        @contextmanager
        def _connection(self):
            yield FixtureConnection()

    rule = COVERAGE_RULES.get('fama_french_daily')
    day = date(2026, 10, 30)
    try:
        with conn.cursor() as cur:
            cur.execute('''
                CREATE TEMP TABLE fama_french_daily (trade_date date, formula_version text,
                    status text, mkt float8, smb float8, hml float8);
                CREATE TEMP TABLE task_execution (task_execution_id bigint,status text);
                CREATE TEMP TABLE dataset_state (dataset_name text,observation_key text,
                    observation_start date,data_status text,source_execution_id bigint,
                    revision int,updated_at timestamptz,dataset_state_id bigint);
                INSERT INTO task_execution VALUES (1,'attention');
                INSERT INTO dataset_state VALUES ('fama_french_daily','2026-10-30',
                    '2026-10-30','gaps',1,1,now(),1);
                INSERT INTO fama_french_daily VALUES
                    ('2026-10-30','ff3-sh-sz-v3','ready',0.01,0.02,0.03);
            ''')
            repo = Repository()
            result = repo.actual_partitions(rule, day, day)
            assert len(result) == 1
            assert not result[0].known_incomplete
            for column, bad_value in [('status','insufficient_universe'),
                                      ('formula_version','ff3-old'), ('mkt',None),
                                      ('smb',float('nan')), ('hml',float('inf')),
                                      ('mkt',float('-inf'))]:
                cur.execute('SAVEPOINT bad_output')
                from psycopg2 import sql
                cur.execute(sql.SQL('UPDATE fama_french_daily SET {}=%s').format(
                    sql.Identifier(column)), (bad_value,))
                bad = repo.actual_partitions(rule, day, day)
                assert len(bad) == 1 and bad[0].known_incomplete, (column,bad_value)
                assert bad[0].invalid_value_rows == 1
                cur.execute('ROLLBACK TO SAVEPOINT bad_output')
            cur.execute('DELETE FROM fama_french_daily')
            assert repo.actual_partitions(rule, day, day) == []
    finally:
        conn.rollback()
        conn.close()


def test_row_readiness_opt_in_requires_independent_predicates():
    rule = COVERAGE_RULES.get('fama_french_daily')
    for changes in ({'required_values': ()}, {'finite_value_columns': ()},
                    {'require_transport_proof': True}):
        with pytest.raises(ValueError, match='independent value predicates'):
            CoverageRuleRegistry([replace(rule, **changes)])
