"""Real SQL identity/type boundaries; only transaction-local fixtures are written."""
import os
from datetime import date

import pytest

from service.db import get_conn
from service.research.local_factors.materializer import FULL_DAY_SUSPENSION_SQL


@pytest.mark.skipif(os.getenv('RUN_DB_INTEGRATION') != '1', reason='requires PostgreSQL')
def test_only_unambiguous_full_day_suspensions_can_fill_missing_bars():
    conn = get_conn()
    day = date(2025, 9, 16)
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TEMP TABLE suspend_d (ts_code text, trade_date date,
                    suspend_type text, suspend_timing text);
                CREATE TEMP TABLE bse_mapping (o_code text,n_code text,list_date date);
                CREATE TEMP TABLE daily (ts_code text,trade_date date);
                INSERT INTO bse_mapping VALUES ('831961.BJ','920961.BJ','2020-07-27');
                INSERT INTO suspend_d VALUES
                  ('831961.BJ','2025-09-16','S',NULL),
                  ('831961.BJ','2025-09-17','R',NULL),
                  ('831961.BJ','2025-09-18','S','09:30-10:30'),
                  ('000001.SZ','2025-09-16','S',''),
                  ('000002.SZ','2025-09-16','R','');
            """)
            params = (day, date(2025,9,18), ['920961.BJ', '000001.SZ', '000002.SZ'])
            cur.execute(FULL_DAY_SUSPENSION_SQL, params)
            assert set(cur.fetchall()) == {(day,'920961.BJ','831961.BJ'),
                                          (day,'000001.SZ','000001.SZ')}
            cur.execute("INSERT INTO bse_mapping VALUES ('831961.BJ','920962.BJ','2020-07-27')")
            cur.execute(FULL_DAY_SUSPENSION_SQL, params)
            assert cur.fetchall() == [(day,'000001.SZ','000001.SZ')]
            cur.execute("DELETE FROM bse_mapping WHERE n_code='920962.BJ'")
            cur.execute("INSERT INTO daily VALUES ('831961.BJ','2025-09-16')")
            cur.execute(FULL_DAY_SUSPENSION_SQL, params)
            assert cur.fetchall() == [(day,'000001.SZ','000001.SZ')]
            cur.execute("DELETE FROM daily")
            cur.execute("UPDATE bse_mapping SET list_date='2025-09-17'")
            cur.execute(FULL_DAY_SUSPENSION_SQL, params)
            assert cur.fetchall() == [(day,'000001.SZ','000001.SZ')]
    finally:
        conn.rollback()
        conn.close()
