"""Opt-in integration against an isolated, migrated PostgreSQL database.

CLAW_FACTOR_TEST_DB must start with claw_factor_migration_test_; never targets
the live data plane. Source panels are deterministic; publication is real SQL.
"""
import os
from datetime import date

import psycopg2
import pytest

from service.config import DB_CONFIG
from service.research.local_factors import materializer, service
from service.research.local_factors.ownership import SHARED_TECHNICAL_FIELDS, canonical_position
from service.orchestration_v2.transformations import build_technical_factor_snapshot_row
from test_local_factor_272 import _market_panel, _financial_panel
import pandas as pd
from service.research.local_factors.catalog import FACTOR_SCHEMA_VERSION, FACTOR_BY_NAME
from service.research.local_factors.provider_validation import (
    DEFAULT_SAMPLE_SIZE,
    SAMPLE_METHOD,
    VALIDATION_SQL,
)


@pytest.mark.skipif(not os.getenv("CLAW_FACTOR_TEST_DB"), reason="isolated PostgreSQL required")
def test_unified_publication_is_idempotent_and_shared_values_are_one_copy(monkeypatch):
    database = os.environ["CLAW_FACTOR_TEST_DB"]
    assert database.startswith("claw_factor_migration_test_")
    connect = lambda: psycopg2.connect(**{**DB_CONFIG, "dbname": database})
    panel = _market_panel(days=320, securities=5)
    codes = panel.alpha101.close.columns
    target = date(2026, 10, 22)
    technical = []
    for code in codes:
        bars = [dict(trade_date=timestamp.date(), open=float(panel.alpha101.open.loc[timestamp,code]),
                     high=float(panel.alpha101.high.loc[timestamp,code]), low=float(panel.alpha101.low.loc[timestamp,code]),
                     close=float(panel.alpha101.close.loc[timestamp,code]), vol=1000.0, amount=10000.0,
                     adj_factor=1.0) for timestamp in panel.alpha101.close.index]
        technical.append(build_technical_factor_snapshot_row(code,target,bars))
    monkeypatch.setattr(materializer,"get_conn",connect)
    monkeypatch.setattr(service,"get_conn",connect)
    monkeypatch.setattr(materializer,"_load_market_panel",lambda *args: (panel,codes,{}))
    monkeypatch.setattr(materializer,"_load_financial_panel",lambda *args: (_financial_panel(codes),{}))
    monkeypatch.setattr("service.orchestration_v2.transformations.build_technical_factor_rows",lambda *args,**kwargs: technical)
    with connect() as connection, connection.cursor() as cursor:
        cursor.execute("""CREATE TABLE IF NOT EXISTS tushare_norm_factor_value
            (factor_name text,ts_code text,factor_value double precision,trade_date date,
             _last_seen_at timestamptz,_record_hash text)""")
    first = materializer.materialize_local_factor_snapshot(target)
    second = materializer.materialize_local_factor_snapshot(target)
    assert first["rows_written"] == second["rows_written"] == 5
    with connect() as connection, connection.cursor() as cursor:
        cursor.execute(
            "SELECT count(*) FROM local_factor_snapshot "
            "WHERE schema_version=%s AND trade_date=%s",
            (FACTOR_SCHEMA_VERSION, target),
        )
        assert cursor.fetchone()[0] == 5
        cursor.execute("SELECT relkind FROM pg_class WHERE oid='technical_factor_snapshot'::regclass")
        assert cursor.fetchone()[0] == "v"
        cursor.execute(
            "SELECT factor_values,technical_values FROM local_factor_snapshot "
            "WHERE schema_version=%s AND trade_date=%s ORDER BY ts_code",
            (FACTOR_SCHEMA_VERSION, target),
        )
        for values, extras in cursor.fetchall():
            assert not set(SHARED_TECHNICAL_FIELDS) & set(extras)
        with pytest.raises(psycopg2.errors.CheckViolation):
            cursor.execute(
                "UPDATE local_factor_snapshot "
                "SET technical_values=technical_values || '{\"rsi_14\": 99}' "
                "WHERE schema_version=%s AND trade_date=%s",
                (FACTOR_SCHEMA_VERSION, target),
            )
        connection.rollback()
    row = service.query_local_factor_values(str(codes[0]),names=["rsi","rsi_14","dif","macd_dif_12_26","return_5d","roc_5"],limit=1)["rows"][0]
    assert row["rsi"] == row["rsi_14"]
    assert row["dif"] == row["macd_dif_12_26"]
    assert row["roc_5"] == pytest.approx(row["return_5d"]*100)

    # A populated date is not a completed date: readiness and exact security
    # coverage both participate in the batch resume contract.
    from service.research.local_factors import batch
    monkeypatch.setattr(batch, "get_conn", connect)
    with connect() as connection, connection.cursor() as cursor:
        for code in codes:
            cursor.execute("INSERT INTO daily(ts_code,trade_date) VALUES(%s,%s) ON CONFLICT DO NOTHING", (code, target))
        materializer._write_provider_validation(cursor, target)
        cursor.execute("UPDATE local_factor_snapshot SET audit_status='ready', technical_audit_status='ready' WHERE trade_date=%s", (target,))
    assert batch.published_dates([target]) == {target}
    with connect() as connection, connection.cursor() as cursor:
        cursor.execute("UPDATE local_factor_snapshot SET audit_status='partial' WHERE trade_date=%s AND ts_code=%s", (target, str(codes[0])))
    assert batch.published_dates([target]) == set()
    with connect() as connection, connection.cursor() as cursor:
        cursor.execute("UPDATE local_factor_snapshot SET audit_status='ready', ts_code='WRONG.TEST' WHERE trade_date=%s AND ts_code=%s", (target, str(codes[0])))
    assert batch.published_dates([target]) == set()
    assert materializer._reuse_certified_snapshot(target, source_execution_id=None) is None


def quality_test_connection():
    database = os.environ["CLAW_FACTOR_TEST_DB"]
    assert database.startswith("claw_factor_migration_test_")
    return psycopg2.connect(**{**DB_CONFIG,"dbname":database})


@pytest.mark.skipif(not os.getenv('CLAW_FACTOR_TEST_DB'), reason='isolated PostgreSQL required')
@pytest.mark.parametrize('task_keys', [('cyq_chips', 'cyq_chips'), ('ant_probe_a', 'ant_probe_b')])
def test_concurrent_workers_cannot_claim_two_serialized_tasks(task_keys):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from uuid import uuid4
    from service.orchestration_v2.repository import OrchestrationV2Repository
    token = uuid4().hex
    ids = []
    definitions = []
    try:
        with quality_test_connection() as connection, connection.cursor() as cursor:
            for index, task_key in enumerate(task_keys):
                cursor.execute("""INSERT INTO orchestration_v2.task_definition
                    (task_key,version,workflow_kind,definition,definition_digest,created_by)
                    VALUES (%s,%s,'acquisition','{}',repeat('0',64),'concurrency-test')
                    RETURNING task_definition_id""", (task_key, 10000 + index))
                definition_id = cursor.fetchone()[0]
                definitions.append(definition_id)
                cursor.execute("""INSERT INTO orchestration_v2.task_execution
                    (task_definition_id,task_key,definition_version,definition_digest,
                     purpose,trigger_source,status,idempotency_key,observation_key,
                     scope_digest,resource_class)
                    VALUES (%s,%s,%s,repeat('0',64),'manual','manual','queued',%s,%s,
                            repeat('0',64),%s) RETURNING task_execution_id""",
                    (definition_id, task_key, 10000 + index, f'{token}:{index}',
                     f'{token}:{index}', token))
                ids.append(cursor.fetchone()[0])
        barrier = Barrier(2)
        def claim(index):
            repository = OrchestrationV2Repository(
                connection_factory=lambda **kwargs: quality_test_connection())
            barrier.wait(timeout=10)
            return repository.claim_next(worker_id=f'test-{index}', resource_classes=(token,))
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(claim, range(2)))
        assert sum(result is not None for result in results) == 1
        with quality_test_connection() as connection, connection.cursor() as cursor:
            cursor.execute('SELECT status FROM orchestration_v2.task_execution WHERE task_execution_id=ANY(%s)', (ids,))
            assert sorted(row[0] for row in cursor.fetchall()) == ['queued', 'running']
    finally:
        with quality_test_connection() as connection, connection.cursor() as cursor:
            cursor.execute('DELETE FROM orchestration_v2.task_execution WHERE task_execution_id=ANY(%s)', (ids,))
            cursor.execute('DELETE FROM orchestration_v2.task_definition WHERE task_definition_id=ANY(%s)', (definitions,))


@pytest.mark.skipif(not os.getenv("CLAW_FACTOR_TEST_DB"), reason="isolated PostgreSQL required")
def test_comparison_materializes_metrics_once_with_fresh_unanalyzed_catalog():
    """A new version must not rescan the full cross-section per catalog row."""
    connection = quality_test_connection()
    try:
        with connection.cursor() as cursor:
            for table in ('local_factor_catalog','local_factor_snapshot','local_factor_validation'):
                cursor.execute(f'CREATE TEMP TABLE {table} (LIKE public.{table} INCLUDING DEFAULTS INCLUDING INDEXES) ON COMMIT DROP')
            cursor.execute('INSERT INTO local_factor_catalog SELECT * FROM public.local_factor_catalog WHERE schema_version=%s',(FACTOR_SCHEMA_VERSION,))
            cursor.execute('CREATE TEMP TABLE tushare_norm_factor_value (factor_name text,ts_code text,trade_date date,factor_value double precision,_last_seen_at timestamptz,_record_hash text) ON COMMIT DROP')
            cursor.execute('CREATE INDEX ON tushare_norm_factor_value(trade_date,ts_code,factor_name,_last_seen_at DESC,_record_hash DESC)')
            cursor.execute("""INSERT INTO local_factor_snapshot
                (schema_version,trade_date,ts_code,factor_values,ready_mask,ready_count,
                 unavailable_positions,calculation_status,input_revision_digest,formula_digest)
                SELECT %s,%s,'TEST'||i,array_fill(1.0::double precision,ARRAY[272]),
                       repeat('1',272)::bit(272),272,ARRAY[]::smallint[],'ready',repeat('0',64),repeat('0',64)
                FROM generate_series(1,800) AS i""",(FACTOR_SCHEMA_VERSION,date(2026,10,22)))
            day = date(2026,10,22)
            # This assertion inspects plan shape, not the production SLA. The
            # isolated Docker database can be concurrently serving full-market
            # factor recomputations, so leave bounded headroom for contention.
            cursor.execute('SET LOCAL statement_timeout=30000')
            cursor.execute('EXPLAIN (ANALYZE, FORMAT JSON) '+VALIDATION_SQL,
                           (FACTOR_SCHEMA_VERSION,day,day.isoformat(),DEFAULT_SAMPLE_SIZE,
                            day,day,FACTOR_SCHEMA_VERSION,day,SAMPLE_METHOD,
                            day.isoformat(),DEFAULT_SAMPLE_SIZE,FACTOR_SCHEMA_VERSION))
            plan = cursor.fetchone()[0][0]['Plan']
            def walk(node):
                yield node
                for child in node.get('Plans',[]):
                    yield from walk(child)
            metrics = [n for n in walk(plan) if n.get('Subplan Name')=='CTE metrics']
            assert len(metrics)==1 and metrics[0]['Actual Loops']==1
    finally:
        connection.rollback(); connection.close()


@pytest.mark.skipif(not os.getenv("CLAW_FACTOR_TEST_DB"), reason="isolated PostgreSQL required")
@pytest.mark.parametrize("dataset", ["local_factor_snapshot", "technical_factor_snapshot"])
def test_partial_factor_rows_cannot_become_ready_during_market_entity_join(dataset):
    from service.data_coverage.registry import COVERAGE_RULES
    from service.data_coverage.repository import CoverageRepository
    rule = COVERAGE_RULES.get(dataset)

    def connect(**_kwargs):
        connection = quality_test_connection()
        with connection.cursor() as cursor:
            cursor.execute(f'CREATE TEMP TABLE {rule.table} AS TABLE public.{rule.table} WITH NO DATA')
            cursor.execute('CREATE TEMP TABLE daily (trade_date date,ts_code text) ON COMMIT DROP')
            cursor.execute('CREATE TEMP TABLE stock_basic (ts_code text,list_date text,delist_date text) ON COMMIT DROP')
            for code, status in [('000001.SZ','ready'),('000002.SZ','partial')]:
                cursor.execute(f'INSERT INTO {rule.table} ({rule.date_column}, ts_code, audit_status) VALUES (%s,%s,%s)', (date(2026,10,22),code,status))
                if dataset == 'local_factor_snapshot':
                    cursor.execute(f'UPDATE {rule.table} SET schema_version=%s WHERE ts_code=%s', (FACTOR_SCHEMA_VERSION,code))
                cursor.execute('INSERT INTO daily VALUES (%s,%s)', (date(2026,10,22),code))
                cursor.execute("INSERT INTO stock_basic VALUES (%s,'19900101',NULL)", (code,))
        return connection

    rows = CoverageRepository(connection_factory=connect).actual_partitions(rule,date(2026,10,22),date(2026,10,22))
    assert len(rows) == 1
    assert rows[0].row_count == 2
    assert rows[0].entity_count == 1


@pytest.mark.skipif(not os.getenv("CLAW_FACTOR_TEST_DB"), reason="isolated PostgreSQL required")
def test_real_financial_loader_maps_lt_rec_and_true_lag63():
    # No loader mocks: actual production SQL against schema-identical tables.
    connection=quality_test_connection()
    try:
        with connection.cursor() as cursor:
            for table in ('dividend','trade_cal'):
                cursor.execute(f'CREATE TEMP TABLE {table} (LIKE public.{table} INCLUDING DEFAULTS) ON COMMIT DROP')
            for table in ("income", "balancesheet"):
                cursor.execute(f"CREATE TEMP TABLE input_{table} (LIKE public.{table} INCLUDING DEFAULTS) ON COMMIT DROP")
            for end,ann,profit,equity,receivable in [
                ('2025-06-30','2025-08-20',50,900,10),
                ('2025-12-31','2026-03-01',100,1000,20),
                ('2026-06-30','2026-08-20',60,1200,30),
            ]:
                cursor.execute("INSERT INTO input_income(ts_code,end_date,ann_date,f_ann_date,report_type,n_income_attr_p) VALUES('000000.SZ',%s,%s,%s,1,%s)",(end,ann,ann,profit))
                cursor.execute("INSERT INTO input_balancesheet(ts_code,end_date,ann_date,f_ann_date,report_type,total_hldr_eqy_inc_min_int,lt_rec) VALUES('000000.SZ',%s,%s,%s,1,%s,%s)",(end,ann,ann,equity,receivable))
            # Future actual disclosure and parent-only statement must not win.
            cursor.execute("INSERT INTO input_balancesheet(ts_code,end_date,ann_date,f_ann_date,report_type,lt_rec) VALUES ('000000.SZ','2026-06-30','2026-10-01','2026-11-01',4,999),('000000.SZ','2026-06-30','2026-10-01','2026-10-01',2,888)")
            cursor.executemany("INSERT INTO trade_cal(exchange,cal_date,is_open) VALUES('SSE',%s,1)",[(d.date(),) for d in pd.bdate_range(end='2026-10-22',periods=70)])
            for table in ("income", "balancesheet"):
                cursor.execute(f"UPDATE input_{table} SET update_flag='0'")
                cursor.execute("SELECT archive_financial_batch(%s, %s::regclass, false)",
                               (table, "pg_temp.input_" + table))
        market=_market_panel(days=320,securities=1)
        panel,diagnostics=materializer._load_financial_panel(connection,date(2026,10,22),market.alpha101.close.columns,market)
        assert panel.current['longterm_receivable'].iloc[0]==30
        assert panel.year_ago['longterm_receivable'].iloc[0]==10
        assert panel.roe_ttm_lag63d.iloc[0]==pytest.approx(.1)
        assert len(diagnostics['financial_input_digests'])==4
        assert diagnostics['lag63_input']['statement_rows']>0
    finally:
        connection.rollback(); connection.close()


@pytest.mark.skipif(not os.getenv("CLAW_FACTOR_TEST_DB"), reason="isolated PostgreSQL required")
def test_provider_validation_rejects_scaled_and_signed_values_but_accepts_constant_matches():
    connection=quality_test_connection()
    try:
        with connection.cursor() as cursor:
            materializer.sync_factor_catalog(connection)
            cursor.execute('CREATE TEMP TABLE local_factor_snapshot (LIKE public.local_factor_snapshot INCLUDING DEFAULTS) ON COMMIT DROP')
            cursor.execute('CREATE TEMP TABLE tushare_norm_factor_value (factor_name text,ts_code text,trade_date date,factor_value double precision,_last_seen_at timestamptz,_record_hash text) ON COMMIT DROP')
            cursor.execute('CREATE TEMP TABLE local_factor_validation (LIKE public.local_factor_validation INCLUDING DEFAULTS INCLUDING INDEXES) ON COMMIT DROP')
            for i in range(40):
                values=[None]*272
                for name,value in [('amount_ma_20d',(i+1)/1000),('alpha101_1',-(i+1)),('size',1.)]:
                    values[FACTOR_BY_NAME[name].position-1]=value
                    cursor.execute('INSERT INTO tushare_norm_factor_value VALUES(%s,%s,%s,%s,now(),%s)',(name,str(i),date(2026,10,22),1. if name=='size' else i+1,str(i)))
                cursor.execute("INSERT INTO local_factor_snapshot(schema_version,trade_date,ts_code,factor_values,ready_mask,ready_count,unavailable_positions,calculation_status,input_revision_digest,formula_digest) VALUES(%s,'2026-10-22',%s,%s,%s::bit(272),3,'{}','partial',%s,%s)",(FACTOR_SCHEMA_VERSION,str(i),values,'0'*272,'a'*64,materializer.FORMULA_DIGEST))
            materializer._write_provider_validation(cursor,date(2026,10,22))
            cursor.execute('SELECT c.factor_name,v.validation_status,v.validation_reason FROM local_factor_validation v JOIN local_factor_catalog c USING(schema_version,factor_position)')
            results={r[0]:r[1:] for r in cursor.fetchall()}
            assert results['amount_ma_20d'][0]=='correlated'
            assert results['alpha101_1'][0]=='review_required'
            assert results['size'][0]=='matched'
            assert results['lra_yoy']==(
                'provider_pending', 'no_reference_values_for_factor_in_local_sample'
            )
            cursor.execute("""SELECT distinct sample_method,sample_seed,
                sample_target_size,sampled_security_count
                FROM local_factor_validation""")
            assert cursor.fetchall()==[(SAMPLE_METHOD,'2026-10-22',DEFAULT_SAMPLE_SIZE,40)]
    finally:
        connection.rollback(); connection.close()


@pytest.mark.skipif(not os.getenv("CLAW_FACTOR_TEST_DB"), reason="isolated PostgreSQL required")
def test_provider_validation_marks_whole_unpublished_date_pending():
    connection=quality_test_connection()
    try:
        with connection.cursor() as cursor:
            materializer.sync_factor_catalog(connection)
            cursor.execute('CREATE TEMP TABLE local_factor_snapshot (LIKE public.local_factor_snapshot INCLUDING DEFAULTS) ON COMMIT DROP')
            cursor.execute('CREATE TEMP TABLE tushare_norm_factor_value (factor_name text,ts_code text,trade_date date,factor_value double precision,_last_seen_at timestamptz,_record_hash text) ON COMMIT DROP')
            cursor.execute('CREATE TEMP TABLE local_factor_validation (LIKE public.local_factor_validation INCLUDING DEFAULTS INCLUDING INDEXES) ON COMMIT DROP')
            for i in range(40):
                cursor.execute("INSERT INTO local_factor_snapshot(schema_version,trade_date,ts_code,factor_values,ready_mask,ready_count,unavailable_positions,calculation_status,input_revision_digest,formula_digest) VALUES(%s,'2026-10-27',%s,%s,%s::bit(272),1,'{}','partial',%s,%s)",(FACTOR_SCHEMA_VERSION,str(i),[1.]+[None]*271,'0'*272,'a'*64,materializer.FORMULA_DIGEST))
            summary=materializer._write_provider_validation(cursor,date(2026,10,27))
            assert summary['validation_provider_pending']==272
            cursor.execute("SELECT count(*) FROM local_factor_validation WHERE validation_status='provider_pending' AND validation_reason='no_reference_values_in_local_date_sample'")
            assert cursor.fetchone()[0]==272
    finally:
        connection.rollback(); connection.close()


@pytest.mark.skipif(not os.getenv("CLAW_FACTOR_TEST_DB"), reason="isolated PostgreSQL required")
def test_market_history_counts_distinct_observed_sessions(monkeypatch):
    from contextlib import closing

    monkeypatch.setattr(materializer, "MAX_MARKET_LOOKBACK", 2)
    with closing(quality_test_connection()) as connection, connection.cursor() as cursor:
        cursor.execute("CREATE TEMP TABLE daily (trade_date date) ON COMMIT DROP")
        cursor.execute("""INSERT INTO daily VALUES ('2026-10-27'), ('2026-10-29'),
                       ('2026-10-30'), ('2026-10-30'), ('2026-11-02')""")
        assert materializer._market_history_dates(connection, date(2026, 10, 31)) == [
            date(2026, 10, 30), date(2026, 10, 29)
        ]
        assert materializer._market_history_dates(connection, date(2026, 10, 26)) == []
