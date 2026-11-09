from datetime import date
import os
from pathlib import Path
from zipfile import ZipFile
import json
import pytest
import psycopg2
from fastapi import FastAPI
from fastapi.testclient import TestClient

from service.research import index_slice as slices
from scripts.export_index_slice import export


def test_http_quality_and_outage_statuses(monkeypatch):
    from service.api.routers.research import router

    app = FastAPI()
    app.include_router(router, prefix="/api")
    client = TestClient(app)
    path = "/api/v1/research/factor-slices/csi300?day=2026-10-30&factor=roe_y"
    for error, expected in [
        (slices.EvidenceUnavailable("no exact universe"), 409),
        (ValueError("invalid factor"), 422),
        (psycopg2.OperationalError("secret"), 503),
    ]:

        def fail(*args):
            raise error

        monkeypatch.setattr(slices, "build_slice", fail)
        response = client.get(path)
        assert response.status_code == expected
        assert "secret" not in response.text


def test_mask_and_missing_reasons():
    assert not slices.factor_cell("return_5d", 1, 0, {}, False)["available"]
    assert not slices.factor_cell("return_5d", float("nan"), 1, {}, False)["available"]
    assert (
        slices.factor_cell(
            "roe_y",
            None,
            0,
            {"unresolved": {"roe_y": "missing_financial_inputs:equity"}},
            False,
        )["reason"]
        == "missing_financial_inputs:equity"
    )
    assert (
        slices.factor_cell("roe_y", None, None, {}, True)["reason"]
        == "no_eligible_snapshot"
    )
    with pytest.raises(ValueError):
        slices.request_factors(["x"])


@pytest.fixture
def db(monkeypatch, tmp_path):
    # Temp relations shadow the real relations; no live data is modified.
    if dsn := os.getenv("CLAW_SLICE_TEST_DSN"):
        pass
    elif os.getenv("RUN_DB_INTEGRATION") == "1":
        dsn = None
    elif os.getenv("RUN_EMBEDDED_POSTGRES") == "1":
        pg = pytest.importorskip("pgserver")
        server = pg.get_server(tmp_path / "pg", cleanup_mode="stop")
        dsn = server.get_uri()
    else:
        pytest.skip("requires PostgreSQL")
    connect = psycopg2.connect

    def seeded(**kwargs):
        c = connect(dsn) if dsn else connect(**kwargs)
        with c, c.cursor() as q:
            q.execute("""CREATE TEMP TABLE trade_cal(exchange text,cal_date date,is_open int);
                INSERT INTO trade_cal VALUES ('SSE','20261030',1),('SSE','20261029',1),('SSE','20261028',1);
                CREATE TEMP TABLE tushare_norm_index_weight AS SELECT '000300.SH'::text index_code,
                    '20261030'::date trade_date,lpad(i::text,6,'0')||'.SZ' con_code,0.333::numeric weight,
                    ('20261030 10:00+08')::timestamptz _first_seen_at,md5(i::text) _record_hash
                    FROM generate_series(1,300) i;
                CREATE TEMP TABLE sys_data_coverage_partition(dataset_name text,partition_date date,status text,audit_id int);
                INSERT INTO tushare_norm_index_weight SELECT index_code,'20261028',con_code,weight,
                   CASE WHEN con_code='000300.SZ' THEN '20261029'::timestamptz ELSE '20261027'::timestamptz END,
                   _record_hash FROM tushare_norm_index_weight WHERE trade_date='20261030';
                CREATE TEMP TABLE local_factor_snapshot(schema_version text,trade_date date,ts_code text,
                   computed_at timestamptz, audit_status text,audit_evidence jsonb,input_revision_digest text,formula_digest text,
                   factor_values float8[],ready_mask bit(272));
            """)
            q.execute(
                """INSERT INTO local_factor_snapshot
                SELECT %s,'20261030',lpad(i::text,6,'0')||'.SZ',ts,'ready','{}','in','formula',
                    array_fill(1.25::float8,ARRAY[272]), repeat('1',272)::bit(272) FROM
                (VALUES(1,'20261030 21:00+08'::timestamptz),(2,'20261101'::timestamptz)) v(i,ts)""",
                (slices.FACTOR_SCHEMA_VERSION,),
            )
        return c

    monkeypatch.setattr(slices.psycopg2, "connect", seeded)
    yield
    if "server" in locals():
        server.cleanup()


def test_atomic_real_sql_and_round_trip(db, tmp_path):
    day = date(2026, 10, 30)
    names = ["return_5d", "roe_y"]
    then = slices.build_slice(day, names)
    now = slices.build_slice(day, names, "reconstructed")
    assert then["manifest"]["member_count"] == 300
    assert then["manifest"]["available_counts"] == dict.fromkeys(names, 1)
    assert now["manifest"]["available_counts"] == dict.fromkeys(names, 2)
    assert then["rows"][1]["factors"]["roe_y"]["reason"] == "no_eligible_snapshot"
    assert then == slices.build_slice(day, names)
    with pytest.raises(slices.EvidenceUnavailable):
        slices.build_slice(date(2026, 10, 29), names)
    with pytest.raises(slices.EvidenceUnavailable, match="observed 299"):
        slices.build_slice(date(2026, 10, 28), names)
    rebuilt = slices.build_slice(date(2026, 10, 28), names, "reconstructed")
    assert rebuilt["manifest"]["member_count"] == 300
    assert rebuilt["manifest"]["available_counts"] == dict.fromkeys(names, 0)
    pytest.importorskip("duckdb")
    path = tmp_path / "frozen.zip"
    meta = export(then, path)
    second = tmp_path / "again.zip"
    export(then, second)
    assert path.read_bytes() == second.read_bytes()
    assert meta["parquet_rows"] == 600
    with ZipFile(path) as z:
        assert json.loads(z.read("rows.json")) == then["rows"]
    with pytest.raises(FileExistsError):
        export(then, path)
