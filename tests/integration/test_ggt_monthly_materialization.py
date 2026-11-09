import os
from contextlib import contextmanager
from datetime import date
from types import SimpleNamespace

import pytest

from service import ggt_monthly
from service.data_coverage.registry import COVERAGE_RULES
from service.data_coverage.repository import CoverageRepository
from service.db import get_conn


@pytest.mark.skipif(os.getenv('RUN_DB_INTEGRATION') != '1',reason='requires PostgreSQL')
def test_monthly_writer_and_independent_reaudit_use_database_sources(monkeypatch):
    conn=get_conn()
    class FixtureConnection:
        def cursor(self, **kwargs): return conn.cursor(**kwargs)
        def set_session(self, **kwargs): pass
        def commit(self): pass
        def close(self): pass
        def rollback(self): conn.rollback()
    class Repository(CoverageRepository):
        @contextmanager
        def _connection(self): yield FixtureConnection()
    monkeypatch.setattr(ggt_monthly,'get_conn',lambda:FixtureConnection())
    monkeypatch.setattr(ggt_monthly,'source_audit',lambda *args:SimpleNamespace(status='complete'))
    try:
        with conn.cursor() as cur:
            cur.execute('CREATE TEMP TABLE ggt_daily(trade_date date,buy_amount numeric,buy_volume numeric,sell_amount numeric,sell_volume numeric)')
            cur.execute('CREATE TEMP TABLE ggt_monthly(month text PRIMARY KEY,'+','.join(name+' numeric' for name in ggt_monthly.OUTPUT_FIELDS)+')')
            cur.execute("INSERT INTO ggt_daily VALUES ('2026-10-29',10,20,30,40),('2026-10-30',20,30,40,50)")
            result=ggt_monthly.materialize_ggt_monthly(date(2026,10,31))
            assert result['publishable'] and result['source_rows']==2
            cur.execute('SELECT day_buy_amt,total_sell_vol FROM ggt_monthly')
            assert cur.fetchone()==(15,90)
            repo=Repository();rule=COVERAGE_RULES.get('ggt_monthly')
            assert not repo.actual_partitions(rule,date(2026,10,1),date(2026,10,31))[0].known_incomplete
            cur.execute('UPDATE ggt_monthly SET total_sell_vol=91')
            bad=repo.actual_partitions(rule,date(2026,10,1),date(2026,10,31))[0]
            assert bad.known_incomplete and 'monthly_aggregate_mismatch' in bad.issues
    finally:
        conn.rollback();conn.close()
