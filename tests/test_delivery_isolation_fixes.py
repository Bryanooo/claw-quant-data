from copy import deepcopy
from datetime import date
from contextlib import contextmanager
import os

import pytest

from collectors.base import BaseCollector, NonRetryableCollectorError
from collectors.stock.reference.share_float import ShareFloatCollector
from service.research.group_materializer import distribution_publication
from service.research.group_valuation import summarize_valuation


def publication():
    data=summarize_valuation({"A":50,"B":50},[
        dict(ts_code="A",trade_date=date(2026,11,6),pe=10,pe_ttm=10,pb=2,ps_ttm=3,dv_ttm=0),
        dict(ts_code="B",trade_date=date(2026,11,6),pe=None,pe_ttm=-3,pb=3,ps_ttm=4,dv_ttm=None),
    ],date(2026,11,6))
    return {"data":data,"meta":{"quality":{"warnings":["some metric inputs are missing"]},
          "numerical_check":{n+"_count_median":"passed" for n in data["metrics"]}}}


def test_valid_sample_is_not_a_complete_numeric_universe():
    p=publication();proof=distribution_publication(p)
    assert proof["publishable"]
    assert not proof["full_numeric_coverage"]
    assert proof["source_nulls"]["pe"]==["B"]
    assert proof["domain_exclusions"]["pe_ttm"]==["B"]
    assert proof["source_nulls"]["dv_ttm"]==["B"]
    assert p["data"]["metrics"]["dv_ttm"]["valid_count"]==1  # real zero remains valid


@pytest.mark.parametrize("defect",["missing_row","invalid_value","no_check","membership"])
def test_bad_inputs_and_checks_still_block(defect):
    p=publication()
    if defect=="missing_row":p["data"]["metrics"]["pe"]["missing_member_rows"]=["B"]
    if defect=="invalid_value":p["data"]["metrics"]["pe"]["invalid_field_codes"]=["B"]
    if defect=="no_check":p["meta"]["numerical_check"].pop("pe_count_median")
    if defect=="membership":p["meta"]["quality"]["warnings"].append("membership truncated")
    assert not distribution_publication(p)["publishable"]


def test_share_float_mandatory_symbol_error_switches_inside_same_node(monkeypatch):
    c=object.__new__(ShareFloatCollector)
    monkeypatch.setattr(c,"_stored_partition_rows",lambda _:0)
    def rejected(*a,**k):
        raise NonRetryableCollectorError("参数校验失败, ts_code和ann_date必填一项")
    monkeypatch.setattr(BaseCollector,"run_offset_paginated",rejected)
    monkeypatch.setattr(c,"_run_stock_partitioned",lambda **k:k)
    p=c.run_offset_paginated(start_date="20261106",end_date="20261106")
    assert p["compact_date"]=="20261106"
    assert "必填" in p["fallback_reason"]
    with pytest.raises(NonRetryableCollectorError):
        c.run_offset_paginated(ts_code="000001.SZ",start_date="20261106",end_date="20261106")


def test_share_float_catchup_yields_before_market_request(monkeypatch):
    from service.clock import business_time
    from collectors.stock.reference.share_float import ShareFloatWindowDeferred
    c=object.__new__(ShareFloatCollector)
    monkeypatch.setattr(c,"_stored_partition_rows",lambda _:100001)
    monkeypatch.setattr(c,"_stock_universe",lambda _:["000001.SZ"])
    monkeypatch.setattr(c,"_completed_stock_codes",lambda *a,**kw:set())
    with business_time("2026-11-10T09:01:00+08:00"):
        with pytest.raises(ShareFloatWindowDeferred) as exc:
            c.run_offset_paginated(start_date="20261106",end_date="20261106")
    assert exc.value.defer_without_attempt
    assert exc.value.retry_after_seconds>0


def test_share_float_transport_success_cannot_skip_a_nonempty_business_write(monkeypatch):
    from collectors.stock.reference import share_float as module
    class Cursor:
        def __enter__(self): return self
        def __exit__(self,*a): pass
        def execute(self,*a): pass
        def fetchall(self):
            return [("empty",0,1000,0),("nonempty",0,1000,3),("broken",1000,1000,0)]
    class Connection:
        def cursor(self): return Cursor()
        def close(self): pass
    monkeypatch.setattr(module,"get_db_conn",Connection)
    c=object.__new__(ShareFloatCollector)
    assert c._completed_stock_codes("20261109",page_size=1000)=={"empty"}


@pytest.mark.skipif(os.getenv("RUN_DB_INTEGRATION") != "1", reason="PostgreSQL required")
def test_real_claim_reserves_capacity_for_daily_tasks(monkeypatch):
    from service.db import get_conn
    from service.orchestration_v2.repository import OrchestrationV2Repository
    from psycopg2.extras import RealDictCursor
    conn=get_conn()
    try:
        with conn.cursor() as c:
            c.execute("""
              CREATE TEMP TABLE task_definition (
                task_definition_id bigint, definition jsonb
              );
              INSERT INTO task_definition VALUES
                (9910, '{"scope_contract":{"cadence":"weekly"}}'),
                (9911, '{"scope_contract":{"cadence":"daily"}}');
              CREATE TEMP TABLE task_execution AS
                SELECT * FROM orchestration_v2.task_execution LIMIT 0;
              INSERT INTO task_execution
                (task_execution_id, task_definition_id, task_key, status,
                 resource_class, eligible_at, attempt_count, max_attempts,
                 priority, purpose)
              VALUES
                (9920,9910,'weekly_scan_test','queued','generic',now(),0,3,999,'daily'),
                (9921,9911,'daily_test','queued','generic',now(),0,3,10,'daily');
            """)
        @contextmanager
        def connection(): yield conn
        @contextmanager
        def cursor(_):
            with conn.cursor(cursor_factory=RealDictCursor) as real:
                class Routed:
                    def execute(self,sql,params=None):
                        return real.execute(sql.replace("orchestration_v2.","pg_temp."),params)
                    def fetchone(self): return real.fetchone()
                yield Routed()
        repo=OrchestrationV2Repository()
        monkeypatch.setattr(repo,"_connection",connection)
        monkeypatch.setattr(repo,"_dict_cursor",cursor)
        short=repo.claim_next(worker_id="isolation-test",resource_classes=("generic",),short_only=True)
        assert short["task_execution_id"]==9921
        regular=repo.claim_next(worker_id="bulk-test",resource_classes=("generic",))
        assert regular["task_execution_id"]==9920
    finally:
        conn.rollback();conn.close()
