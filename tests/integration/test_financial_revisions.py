"""Exercise the collector, revision store and the research read paths together."""
import os
from datetime import date
from uuid import uuid4

import pandas as pd
import pytest

from collectors.stock.finance.income import IncomeCollector
from collectors.stock.finance.fina_indicator import FinaIndicatorCollector
from collectors.stock.finance.cashflow import CashflowCollector
from service.data_service.database import Database
from service.data_service.models import DatasetQuery
from service.data_service.registry import DATASETS
from service.data_service.repository import DatasetRepository
from service.research.repository import ResearchRepository

pytestmark = [pytest.mark.integration, pytest.mark.skipif(
    os.getenv("RUN_DB_INTEGRATION") != "1", reason="requires migrated test database",
)]


def test_reconciliation_fields_roundtrip_without_backdating_or_legacy_alias():
    db = Database()
    code = 'TEST' + uuid4().hex[:12]
    identity = dict(ts_code=code, end_date='20251231', ann_date='20260310',
                    f_ann_date='20260310', report_type=1, update_flag='1')
    try:
        object.__new__(IncomeCollector).store(pd.DataFrame([
            dict(identity, fin_exp_int_exp=2734017000, fin_exp_int_inc=10594657000)]))
        object.__new__(CashflowCollector).store(pd.DataFrame([
            dict(identity, finan_exp=2470751000, amort_intang_assets=512000000,
                 lt_amort_deferred_exp=1764508000, use_right_asset_dep=337367000)]))
        row = db.fetch_one('SELECT * FROM cashflow WHERE ts_code=%s', (code,))
        assert row['finan_exp'] == 2470751000
        assert row['financian_exp'] is None
        assert row['amort_intang_assets'] == 512000000
        assert row['lt_amort_deferred_exp'] == 1764508000
        assert row['use_right_asset_dep'] == 337367000
        assert db.fetch_one('SELECT fin_exp_int_exp FROM income WHERE ts_code=%s',(code,))['fin_exp_int_exp']==2734017000
        assert not db.fetch_all("SELECT * FROM cashflow_as_of('2026-10-08',ARRAY[%s])",(code,))
        assert db.fetch_one('SELECT (row_data).finan_exp AS value FROM cashflow_revision WHERE ts_code=%s',(code,))['value']==2470751000
    finally:
        with db.writable_connection() as conn, conn.cursor() as cur:
            for table in ('income','income_revision','cashflow','cashflow_revision'):
                cur.execute(f'DELETE FROM {table} WHERE ts_code=%s',(code,))
        db.close()


def test_as_of_reads_preserve_dated_revisions_and_gate_undated_corrections():
    db = Database()
    code = "TEST" + uuid4().hex[:12]
    period = date(2024, 3, 31)
    early, late = date(2024, 4, 25), date(2024, 4, 27)
    key = dict(ts_code=code, end_date="20240331", ann_date="20240424", report_type=1)
    rows = [dict(key, f_ann_date="20240424", update_flag="0", revenue=100),
            dict(key, f_ann_date="20240426", update_flag="1", revenue=80),
            dict(key, f_ann_date="20240426", update_flag="1", revenue=200, report_type=5)]
    income = object.__new__(IncomeCollector)
    indicator = object.__new__(FinaIndicatorCollector)
    repository = DatasetRepository(db)
    research = ResearchRepository(db)

    def query(day, **filters):
        return DatasetQuery(exact_filters={"ts_code": code, **filters}, as_of=day)

    try:
        income.store(pd.DataFrame(rows))
        income.store(pd.DataFrame(rows[:1]))  # stale backfill and identical replay
        spec = DATASETS.get("income")
        assert repository.records(spec, query(early))[0]["revenue"] == 100
        assert {row["revenue"] for row in repository.records(spec, query(late))} == {80, 200}
        assert repository.count(spec, query(late, report_type="5")) == 1
        assert repository.records(spec, query(late, report_type="5"))[0]["revenue"] == 200
        assert db.fetch_one("SELECT count(*) AS n FROM income_revision WHERE ts_code=%s", (code,))["n"] == 3
        assert db.fetch_one("SELECT revenue FROM income WHERE ts_code=%s AND report_type=1", (code,))["revenue"] == 80
        assert research.industry_fundamentals([code], as_of=late)["revenue"] == 80
        assert research.industry_contributors([code], as_of=early, report_period=period)[0]["revenue"] == 100
        with db.writable_connection() as conn, conn.cursor() as cur:
            cur.execute("""INSERT INTO tushare_norm_daily_basic (
                        _record_hash,_request_hash,_source_collected_at,ts_code,trade_date,total_mv
                        ) VALUES (md5(%s), md5(%s), now(), %s, %s, 100)""", (code, code, code, late))
        [aggregate] = research.group_aggregate_inputs([code], report_period=period, as_of=late)
        assert aggregate["income_report_type"] == 1
        assert aggregate["ttm_status"] == "missing_current"
        assert aggregate["net_income_ttm"] is None
        indicator.store(pd.DataFrame([dict(key, update_flag="1", roe=99,
                                         ebit=80, ebitda=100, daa=20,
                                         fa_turn=1.23456789, total_fa_trun=1.23,
                                         fixed_assets=200)]))
        assert research.group_financial_rows([code], report_period=period, as_of=early) == []
        observed = db.fetch_one("SELECT available_on FROM fina_indicator_revision WHERE ts_code=%s", (code,))
        actual = db.fetch_one("SELECT ebit,ebitda,daa,fa_turn,total_fa_trun,fixed_assets "
                             "FROM fina_indicator_as_of(%s,ARRAY[%s])",
                             (observed['available_on'],code))
        assert [actual[k] for k in ('ebit','ebitda','daa','fixed_assets')] == [80,100,20,200]
        assert str(actual['fa_turn']) == '1.23456789'
        assert research.group_financial_rows([code], report_period=period, as_of=observed["available_on"])[0]["roe"] == 99
    finally:
        with db.writable_connection() as conn, conn.cursor() as cur:
            for table in ("income", "income_revision", "fina_indicator", "fina_indicator_revision",
                          "tushare_norm_daily_basic"):
                cur.execute(f"DELETE FROM {table} WHERE ts_code=%s", (code,))
        db.close()
