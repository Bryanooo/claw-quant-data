"""Exercise revision reconciliation against real SQL; only temporary tables are written."""
import os
from contextlib import contextmanager
from datetime import date

import psycopg2
import pytest

from service.config import DB_CONFIG
from service.data_coverage.repository import CoverageRepository


@pytest.mark.skipif(os.getenv("RUN_DB_INTEGRATION") != "1", reason="requires PostgreSQL")
def test_obsolete_success_without_job_never_counts_as_ready():
    conn = psycopg2.connect(**DB_CONFIG)
    class Repository(CoverageRepository):
        @contextmanager
        def _connection(self):
            yield conn
    try:
        with conn.cursor() as cur:
            cur.execute("""CREATE TEMP TABLE sys_data_coverage_partition(
                LIKE public.sys_data_coverage_partition INCLUDING DEFAULTS);
                CREATE TEMP TABLE sys_data_coverage_audit(audit_id bigint, dataset_name text,evidence jsonb);
                CREATE TEMP TABLE sys_data_coverage_job(dataset_name text,start_date date,end_date date,
                    idempotency_key text UNIQUE,status text DEFAULT 'queued');
                INSERT INTO sys_data_coverage_audit VALUES (7,'stk_factor','{"rule_revision":5}');
                INSERT INTO sys_data_coverage_partition(dataset_name,partition_date,status,expected,audit_id)
                    VALUES ('stk_factor','2026-10-30','present',true,7);""")
        repo = Repository()
        day = date(2026,10,30)
        assert repo.calendar_day(day)[0]['status'] == 'pending'
        assert repo.data_calendar(day, day)[0]['ready'] == 0
        assert not repo.list_partitions('stk_factor',start_date=day,end_date=day,status='present',limit=1)
        assert repo.queue_stale_partition_audits({'stk_factor':6}) == {'stk_factor':1}
        assert repo.queue_stale_partition_audits({'stk_factor':6}) == {}
        with conn.cursor() as cur:
            cur.execute("UPDATE sys_data_coverage_job SET status='failed'")
        assert repo.queue_stale_partition_audits({'stk_factor':6}) == {}
    finally:
        conn.rollback()
        conn.close()
