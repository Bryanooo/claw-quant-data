import os
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

import psycopg2
import pytest
import pandas as pd

from service.collector_catalog import discover_collectors
from service.config import DB_CONFIG
from service.collection_jobs.repository import JobRepository
from service.collection_jobs.fanout_campaigns import (
    FanoutCampaignRepository,
    FanoutCampaignService,
)
from service.collection_jobs.fanout import FANOUT_DEFINITIONS
from service.collection_jobs.models import BatchChildSpec
from service.collection_jobs.registry import TASKS
from service.collection_jobs.schedules import ScheduleCursorRepository
from service.data_coverage.models import (
    CoverageAuditResult,
    CoverageRule,
    CoverageStrategy,
)
from service.data_coverage.repository import CoverageRepository
from service.data_coverage.registry import COVERAGE_RULES
from service.data_service.registry import DATASETS
from service.data_service.database import Database
from service.data_service.models import DatasetQuery, DatasetSpec, DateStorage
from service.data_service.repository import DatasetRepository
from service.delivery_monitor import DeliveryPlanRepository
from service.tushare_normalization import NORMALIZATION_CONTRACTS, TushareNormalizer
from service.initialization.repository import InitializationRepository
from service.collection_monitor import CollectionMonitorRepository
from collectors.base import BaseCollector


pytestmark = pytest.mark.skipif(
    os.getenv("RUN_DB_INTEGRATION") != "1",
    reason="set RUN_DB_INTEGRATION=1 to run PostgreSQL contract tests",
)


def test_every_coverage_rule_references_real_source_columns():
    connection = psycopg2.connect(**DB_CONFIG)
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT table_name, column_name
                FROM information_schema.columns
                WHERE table_schema = 'public'
                """
            )
            columns: dict[str, set[str]] = {}
            for table_name, column_name in cursor.fetchall():
                columns.setdefault(table_name, set()).add(column_name)
    finally:
        connection.close()

    for rule in COVERAGE_RULES.list():
        assert rule.table in columns, rule.dataset_name
        if rule.date_column:
            assert rule.date_column in columns[rule.table], rule.dataset_name
        if rule.entity_column:
            assert rule.entity_column in columns[rule.table], rule.dataset_name


def test_coverage_queue_counts_only_unresolved_failures():
    suffix = uuid4().hex
    dataset_name = "stock_daily"
    repository = CoverageRepository()
    failed, _ = repository.create_job(
        dataset_name,
        date(2026, 8, 27),
        date(2026, 8, 28),
        idempotency_key=f"integration-coverage-failed-{suffix}",
        max_attempts=1,
    )
    recovered = None
    connection = psycopg2.connect(**DB_CONFIG)
    try:
        baseline = repository.queue_counts()["failed"]
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE sys_data_coverage_job
                SET status='failed', attempt=1, finished_at=NOW()
                WHERE job_id=%s
                """,
                (failed["job_id"],),
            )
        connection.commit()
        assert repository.queue_counts()["failed"] == baseline + 1

        recovered, _ = repository.create_job(
            dataset_name,
            date(2026, 8, 27),
            date(2026, 8, 28),
            idempotency_key=f"integration-coverage-recovered-{suffix}",
            max_attempts=1,
        )
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE sys_data_coverage_job
                SET status='success', attempt=1, finished_at=NOW()
                WHERE job_id=%s
                """,
                (recovered["job_id"],),
            )
        connection.commit()
        assert repository.queue_counts()["failed"] == baseline
    finally:
        with connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM sys_data_coverage_job WHERE job_id = ANY(%s)",
                ([item for item in (
                    failed["job_id"],
                    recovered["job_id"] if recovered else None,
                ) if item is not None],),
            )
        connection.commit()
        connection.close()


def test_verified_policy_scope_is_reused_across_handler_versions():
    suffix = uuid4().hex
    repository = JobRepository()
    parameters = {
        "api_name": "cn_cpi",
        "parameters": {"start_m": "202601", "end_m": "202601"},
        "complete": True,
    }
    first, created = repository.create(
        "tushare_interface",
        parameters,
        max_attempts=3,
        idempotency_key=f"integration-scope-v1-{suffix}",
        api_name="cn_cpi",
        cadence="monthly",
        period_key="2026-01",
        expected_for=date(2026, 1, 31),
        handler_type="generic",
        handler_key="catalog_typed:cn_cpi",
        handler_version="1",
    )
    connection = psycopg2.connect(**DB_CONFIG)
    try:
        assert created is True
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE sys_collection_job
                SET status='success', completion_status='complete',
                    completion_evidence='{"verified": true}'::jsonb,
                    rows_fetched=1, rows_inserted=1, finished_at=NOW()
                WHERE job_id=%s
                """,
                (first["job_id"],),
            )
        connection.commit()

        reused, created = repository.create(
            "tushare_interface",
            parameters,
            max_attempts=3,
            idempotency_key=f"integration-scope-v2-{suffix}",
            api_name="cn_cpi",
            cadence="monthly",
            period_key="2026-01",
            expected_for=date(2026, 1, 31),
            handler_type="generic",
            handler_key="catalog_typed:cn_cpi",
            handler_version="2",
            reuse_verified_scope=True,
        )
        assert created is False
        assert reused["job_id"] == first["job_id"]
    finally:
        with connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM sys_collection_job WHERE idempotency_key LIKE %s",
                (f"integration-scope-%-{suffix}",),
            )
        connection.commit()
        connection.close()


def test_physical_partition_does_not_hide_known_incomplete_collection():
    suffix = uuid4().hex[:12]
    table_name = f"coverage_incomplete_{suffix}"
    api_name = f"coverage_incomplete_{suffix}"
    expected_for = date(2026, 8, 28)
    repository = JobRepository()
    job_ids = []
    connection = psycopg2.connect(**DB_CONFIG)
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                f'CREATE TABLE "{table_name}" '
                '(trade_date TEXT NOT NULL, ts_code TEXT NOT NULL)'
            )
            cursor.execute(
                f'INSERT INTO "{table_name}" VALUES (%s, %s)',
                ("20260828", "000001.SZ"),
            )
        connection.commit()

        failed, created = repository.create(
            "tushare_interface",
            {"api_name": api_name, "parameters": {"trade_date": "20260828"}},
            max_attempts=1,
            idempotency_key=f"integration-known-incomplete-{suffix}",
            api_name=api_name,
            cadence="daily",
            period_key="2026-08-28",
            expected_for=expected_for,
        )
        assert created
        job_ids.append(failed["job_id"])
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE sys_collection_job
                SET status='failed', completion_status='incomplete',
                    finished_at=NOW()
                WHERE job_id=%s
                """,
                (failed["job_id"],),
            )
        connection.commit()

        rule = CoverageRule(
            dataset_name=api_name,
            table=table_name,
            date_column="trade_date",
            date_storage=DateStorage.COMPACT,
            strategy=CoverageStrategy.TRADING_DAILY,
        )
        partitions = CoverageRepository().actual_partitions(
            rule, expected_for, expected_for
        )
        assert len(partitions) == 1
        assert partitions[0].known_incomplete is True

        recovered, created = repository.create(
            "tushare_interface",
            {"api_name": api_name, "parameters": {"trade_date": "20260828"}},
            max_attempts=1,
            idempotency_key=f"integration-known-complete-{suffix}",
            api_name=api_name,
            cadence="daily",
            period_key="2026-08-28",
            expected_for=expected_for,
        )
        assert created
        job_ids.append(recovered["job_id"])
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE sys_collection_job
                SET status='success', completion_status='verifying',
                    finished_at=NOW()
                WHERE job_id=%s
                """,
                (recovered["job_id"],),
            )
        connection.commit()

        partitions = CoverageRepository().actual_partitions(
            rule, expected_for, expected_for
        )
        assert partitions[0].known_incomplete is False

        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE sys_collection_job
                SET completion_status='complete'
                WHERE job_id=%s
                """,
                (recovered["job_id"],),
            )
        connection.commit()
    finally:
        connection.rollback()
        with connection.cursor() as cursor:
            if job_ids:
                cursor.execute(
                    "DELETE FROM sys_collection_job WHERE job_id = ANY(%s)",
                    (job_ids,),
                )
            cursor.execute(f'DROP TABLE IF EXISTS "{table_name}"')
        connection.commit()
        connection.close()


def test_base_collector_sanitizes_postgres_nul_bytes_with_evidence():
    table_name = f"collector_nul_{uuid4().hex[:12]}"
    connection = psycopg2.connect(**DB_CONFIG)
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                f'CREATE TABLE "{table_name}" (id INTEGER PRIMARY KEY, label TEXT)'
            )
        connection.commit()

        collector = BaseCollector.__new__(BaseCollector)
        collector.table_name = table_name
        collector.pk_columns = ["id"]
        collector._sanitization_nul_characters = 0
        collector._sanitization_fields = set()
        assert collector.store(
            pd.DataFrame([{"id": 1, "label": "概念\x00板块"}])
        ) == 1

        with connection.cursor() as cursor:
            cursor.execute(f'SELECT label FROM "{table_name}" WHERE id=1')
            assert cursor.fetchone()[0] == "概念板块"
        assert collector._sanitization_evidence() == {
            "nul_characters_removed": 1,
            "affected_fields": ["label"],
        }
    finally:
        connection.rollback()
        with connection.cursor() as cursor:
            cursor.execute(f'DROP TABLE IF EXISTS "{table_name}"')
        connection.commit()
        connection.close()


def test_long_quota_delay_defers_sibling_interface_jobs():
    suffix = uuid4().hex
    repository = JobRepository()
    job_ids = []
    try:
        for index in range(2):
            job, created = repository.create(
                "tushare_interface",
                {"api_name": "factor_value", "parameters": {"ts_code": str(index)}},
                max_attempts=3,
                idempotency_key=f"integration-quota-defer-{index}-{suffix}",
                api_name="factor_value",
                resource_class=f"quota-test-{suffix[:8]}",
            )
            assert created
            job_ids.append(job["job_id"])

        claimed = repository.claim_next(
            "integration-quota-worker",
            resource_classes=(f"quota-test-{suffix[:8]}",),
        )
        repository.fail_or_requeue(
            claimed,
            "daily quota exhausted",
            retry_after_seconds=4000,
        )

        connection = psycopg2.connect(**DB_CONFIG)
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT status, available_at > NOW() + INTERVAL '3900 seconds'
                    FROM sys_collection_job WHERE job_id = ANY(%s)
                    ORDER BY job_id
                    """,
                    (job_ids,),
                )
                rows = cursor.fetchall()
            assert rows == [("queued", True), ("queued", True)]
        finally:
            connection.close()
    finally:
        connection = psycopg2.connect(**DB_CONFIG)
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM sys_collection_job WHERE job_id = ANY(%s)",
                    (job_ids,),
                )
            connection.commit()
        finally:
            connection.close()


def test_future_rate_slot_releases_lease_without_consuming_attempt():
    suffix = uuid4().hex
    resource_class = f"slot-test-{suffix[:8]}"
    repository = JobRepository()
    job_id = None
    try:
        job, created = repository.create(
            "tushare_interface",
            {"api_name": "hk_daily", "parameters": {"trade_date": "20260907"}},
            max_attempts=3,
            idempotency_key=f"integration-rate-slot-defer-{suffix}",
            api_name="hk_daily",
            resource_class=resource_class,
        )
        assert created
        job_id = job["job_id"]
        claimed = repository.claim_next(
            "integration-rate-slot-worker",
            resource_classes=(resource_class,),
        )
        assert claimed["attempt"] == 1

        repository.defer_running(
            claimed,
            retry_after_seconds=1200,
            reason="known future rate slot",
        )

        connection = psycopg2.connect(**DB_CONFIG)
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT status, completion_status, attempt,
                           available_at > NOW() + INTERVAL '1100 seconds',
                           worker_id, error_message
                    FROM sys_collection_job WHERE job_id = %s
                    """,
                    (job_id,),
                )
                row = cursor.fetchone()
            assert row == (
                "queued", "retrying", 0, True, None, "known future rate slot"
            )
        finally:
            connection.close()
    finally:
        if job_id:
            connection = psycopg2.connect(**DB_CONFIG)
            try:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "DELETE FROM sys_collection_job WHERE job_id = %s",
                        (job_id,),
                    )
                connection.commit()
            finally:
                connection.close()


def test_network_failure_defers_the_whole_worker_resource_pool():
    suffix = uuid4().hex
    resource_class = f"network-test-{suffix[:8]}"
    repository = JobRepository()
    job_ids = []
    try:
        for index, api_name in enumerate(("factor_value", "cn_cpi")):
            job, created = repository.create(
                "tushare_interface",
                {"api_name": api_name, "parameters": {"probe": str(index)}},
                max_attempts=3,
                idempotency_key=f"integration-network-defer-{index}-{suffix}",
                api_name=api_name,
                resource_class=resource_class,
            )
            assert created
            job_ids.append(job["job_id"])

        claimed = repository.claim_next(
            "integration-network-worker",
            resource_classes=(resource_class,),
        )
        repository.fail_or_requeue(
            claimed,
            "temporary DNS resolution failure",
            retry_after_seconds=60,
            defer_resource_class_seconds=120,
        )

        connection = psycopg2.connect(**DB_CONFIG)
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT status, available_at > NOW() + INTERVAL '100 seconds'
                    FROM sys_collection_job WHERE job_id = ANY(%s)
                    ORDER BY job_id
                    """,
                    (job_ids,),
                )
                rows = cursor.fetchall()
            assert rows == [("queued", True), ("queued", True)]
        finally:
            connection.close()
    finally:
        connection = psycopg2.connect(**DB_CONFIG)
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM sys_collection_job WHERE job_id = ANY(%s)",
                    (job_ids,),
                )
            connection.commit()
        finally:
            connection.close()


def test_later_complete_coverage_audit_resolves_old_incomplete_job():
    suffix = uuid4().hex
    expected_for = date(2026, 8, 31)
    collection_job_id = None
    coverage_job_id = None
    connection = psycopg2.connect(**DB_CONFIG)
    try:
        repository = JobRepository()
        job, created = repository.create(
            "stock_limit",
            {"trade_date": "20260831"},
            max_attempts=3,
            idempotency_key=f"integration-audit-recovery-{suffix}",
            api_name="stk_limit",
            cadence="repair",
            period_key="2026-08-31",
            expected_for=expected_for,
            resource_class=f"audit-recovery-{suffix[:8]}",
        )
        assert created
        collection_job_id = job["job_id"]
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE sys_collection_job
                SET status='success', completion_status='incomplete',
                    finished_at=NOW() - INTERVAL '10 minutes'
                WHERE job_id=%s
                """,
                (collection_job_id,),
            )
            cursor.execute(
                """
                INSERT INTO sys_data_coverage_job(
                    dataset_name, start_date, end_date, status,
                    idempotency_key, finished_at
                ) VALUES ('stock_limit', %s, %s, 'success', %s, NOW())
                RETURNING job_id
                """,
                (
                    expected_for,
                    expected_for,
                    f"integration-audit-recovery-{suffix}",
                ),
            )
            coverage_job_id = cursor.fetchone()[0]
            cursor.execute(
                """
                INSERT INTO sys_data_coverage_audit(
                    job_id, dataset_name, strategy, start_date, end_date,
                    expected_partitions, present_partitions, coverage_ratio,
                    status, finished_at
                ) VALUES (%s, 'stock_limit', 'trading_daily', %s, %s,
                          1, 1, 1, 'complete', NOW())
                """,
                (coverage_job_id, expected_for, expected_for),
            )
        connection.commit()

        unresolved = CollectionMonitorRepository().unresolved_partition_failures()

        assert not (
            unresolved.get("stk_limit")
            and unresolved["stk_limit"]["job_id"] == collection_job_id
        )
    finally:
        with connection.cursor() as cursor:
            if coverage_job_id is not None:
                cursor.execute(
                    "DELETE FROM sys_data_coverage_audit WHERE job_id=%s",
                    (coverage_job_id,),
                )
                cursor.execute(
                    "DELETE FROM sys_data_coverage_job WHERE job_id=%s",
                    (coverage_job_id,),
                )
            if collection_job_id is not None:
                cursor.execute(
                    "DELETE FROM sys_collection_job WHERE job_id=%s",
                    (collection_job_id,),
                )
        connection.commit()
        connection.close()


def test_failed_fanout_plan_is_only_superseded_by_verified_replacement():
    suffix = uuid4().hex
    repository = FanoutCampaignRepository()
    original, _ = repository.create(
        api_name="factor_value",
        request={"api_name": "factor_value", "trade_date": "2026-08-28"},
        page_size=200,
        idempotency_key=f"integration-superseded-original-{suffix}",
        initialization_id=None,
        cadence="daily",
        period_key="2026-08-28",
        expected_for=date(2026, 8, 28),
    )
    replacement, _ = repository.create(
        api_name="factor_value",
        request={"api_name": "factor_value", "trade_date": "2026-08-28"},
        page_size=200,
        idempotency_key=f"integration-superseded-replacement-{suffix}",
        initialization_id=None,
        cadence="daily",
        period_key="2026-08-28",
        expected_for=date(2026, 8, 28),
    )
    campaign_ids = [original["campaign_id"], replacement["campaign_id"]]
    connection = psycopg2.connect(**DB_CONFIG)
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE sys_collection_fanout_campaign
                SET status='attention', completion_status='incomplete'
                WHERE campaign_id=%s
                """,
                (original["campaign_id"],),
            )
            cursor.execute(
                """
                UPDATE sys_collection_fanout_campaign
                SET status='success', completion_status='complete'
                WHERE campaign_id=%s
                """,
                (replacement["campaign_id"],),
            )
        connection.commit()

        repository.supersede(
            original["campaign_id"],
            replacement["campaign_id"],
            message="factor-name fan-out replaced stock fan-out",
        )
        resolved = repository.get(original["campaign_id"])
        assert resolved["status"] == "superseded"
        assert resolved["completion_status"] == "incomplete"
        assert resolved["superseded_by_campaign_id"] == replacement["campaign_id"]
        assert resolved["resolution_message"] == (
            "factor-name fan-out replaced stock fan-out"
        )
    finally:
        with connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM sys_collection_fanout_campaign WHERE campaign_id = ANY(%s)",
                (campaign_ids,),
            )
        connection.commit()
        connection.close()


def test_verified_fanout_replacement_closes_obsolete_same_period_plan():
    suffix = uuid4().hex
    repository = FanoutCampaignRepository()
    original, _ = repository.create(
        api_name="factor_value",
        request={"api_name": "factor_value", "trade_date": "2026-08-28"},
        page_size=200,
        idempotency_key=f"integration-auto-superseded-original-{suffix}",
        initialization_id=None,
        cadence="daily",
        period_key="2026-08-28",
        expected_for=date(2026, 8, 28),
    )
    replacement, _ = repository.create(
        api_name="factor_value",
        request={"api_name": "factor_value", "trade_date": "2026-08-28"},
        page_size=200,
        idempotency_key=f"integration-auto-superseded-replacement-{suffix}",
        initialization_id=None,
        cadence="daily",
        period_key="2026-08-28",
        expected_for=date(2026, 8, 28),
    )
    campaign_ids = [original["campaign_id"], replacement["campaign_id"]]
    connection = psycopg2.connect(**DB_CONFIG)
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE sys_collection_fanout_campaign "
                "SET status='attention', completion_status='incomplete' "
                "WHERE campaign_id=%s",
                (original["campaign_id"],),
            )
            cursor.execute(
                "UPDATE sys_collection_fanout_campaign "
                "SET status='success', completion_status='complete' "
                "WHERE campaign_id=%s",
                (replacement["campaign_id"],),
            )
        connection.commit()

        assert repository.supersede_resolved_predecessors(
            replacement["campaign_id"]
        ) == 1
        resolved = repository.get(original["campaign_id"])
        assert resolved["status"] == "superseded"
        assert resolved["superseded_by_campaign_id"] == replacement["campaign_id"]
    finally:
        with connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM sys_collection_fanout_campaign WHERE campaign_id = ANY(%s)",
                (campaign_ids,),
            )
        connection.commit()
        connection.close()


def test_fanout_scope_is_reused_across_backfill_and_daily_cadence():
    suffix = uuid4().hex
    api_name = f"scope_dedup_{suffix[:12]}"
    repository = FanoutCampaignRepository()
    request = {"api_name": api_name, "trade_date": "2026-08-28"}
    campaign_ids = []
    try:
        backfill, created = repository.create(
            api_name=api_name,
            request=request,
            page_size=200,
            idempotency_key=f"integration-scope-backfill-{suffix}",
            initialization_id=None,
            cadence="backfill",
            period_key="2026-08-28",
            expected_for=date(2026, 8, 28),
            plan_version=2,
            reuse_scope=True,
        )
        assert created is True
        campaign_ids.append(backfill["campaign_id"])

        routine, created = repository.create(
            api_name=api_name,
            request=request,
            page_size=100,
            idempotency_key=f"integration-scope-daily-{suffix}",
            initialization_id=None,
            cadence="daily",
            period_key="2026-08-28",
            expected_for=date(2026, 8, 28),
            plan_version=2,
            reuse_scope=True,
        )
        assert created is False
        assert routine["campaign_id"] == backfill["campaign_id"]
        assert routine["cadence"] == "backfill"

        upgraded, created = repository.create(
            api_name=api_name,
            request=request,
            page_size=200,
            idempotency_key=f"integration-scope-upgrade-{suffix}",
            initialization_id=None,
            cadence="daily",
            period_key="2026-08-28",
            expected_for=date(2026, 8, 28),
            plan_version=3,
            reuse_scope=True,
        )
        assert created is True
        assert upgraded["campaign_id"] != backfill["campaign_id"]
        campaign_ids.append(upgraded["campaign_id"])
    finally:
        if campaign_ids:
            connection = psycopg2.connect(**DB_CONFIG)
            try:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "DELETE FROM sys_collection_fanout_campaign "
                        "WHERE campaign_id = ANY(%s)",
                        (campaign_ids,),
                    )
                connection.commit()
            finally:
                connection.close()


def test_fanout_newer_complete_scope_is_reused_for_initialization():
    suffix = uuid4().hex
    api_name = f"scope_newer_{suffix[:12]}"
    repository = FanoutCampaignRepository()
    request = {"api_name": api_name}
    campaign_ids = []
    connection = psycopg2.connect(**DB_CONFIG)
    try:
        recent, created = repository.create(
            api_name=api_name,
            request=request,
            page_size=200,
            idempotency_key=f"integration-scope-recent-{suffix}",
            initialization_id=None,
            cadence="weekly",
            period_key="2026-W36",
            expected_for=date(2026, 9, 6),
            plan_version=2,
            reuse_scope=True,
        )
        assert created is True
        campaign_ids.append(recent["campaign_id"])
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE sys_collection_fanout_campaign
                SET status='success', completion_status='complete',
                    finished_at=NOW()
                WHERE campaign_id=%s
                """,
                (recent["campaign_id"],),
            )
        connection.commit()

        initialization, created = repository.create(
            api_name=api_name,
            request=request,
            page_size=100,
            idempotency_key=f"integration-scope-initial-{suffix}",
            initialization_id=999999,
            cadence="initialization",
            period_key="initial-2026-09-05",
            expected_for=date(2026, 9, 5),
            plan_version=1,
            reuse_scope=True,
        )
        assert created is False
        assert initialization["campaign_id"] == recent["campaign_id"]
    finally:
        with connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM sys_collection_fanout_campaign "
                "WHERE campaign_id = ANY(%s)",
                (campaign_ids,),
            )
        connection.commit()
        connection.close()


def test_complete_fanout_resolves_older_market_wide_failure():
    suffix = uuid4().hex
    api_name = f"fanout_recovery_{suffix[:10]}"
    connection = psycopg2.connect(**DB_CONFIG)
    campaign_id = None
    collection_job_id = None
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO sys_collection_fanout_campaign(
                    api_name, request, page_size, idempotency_key, cadence,
                    period_key, expected_for, plan_version, status,
                    completion_status, finished_at
                ) VALUES (
                    %s, jsonb_build_object('api_name', %s), 200, %s,
                    'weekly', '2026-W36', DATE '2026-09-06', 2,
                    'success', 'complete', NOW() - INTERVAL '1 hour'
                ) RETURNING campaign_id
                """,
                (api_name, api_name, f"fanout-recovery-{suffix}"),
            )
            campaign_id = cursor.fetchone()[0]
            cursor.execute(
                """
                INSERT INTO sys_collection_job(
                    task_name, api_name, parameters, status, period_key,
                    expected_for, completion_status, error_message, finished_at
                ) VALUES (
                    'tushare_interface', %s,
                    jsonb_build_object(
                        'api_name', %s, 'parameters', '{}'::jsonb
                    ),
                    'failed', 'initial-2026-09-05', DATE '2026-09-05',
                    'incomplete', 'unsafe market-wide request', NOW()
                ) RETURNING job_id
                """,
                (api_name, api_name),
            )
            collection_job_id = cursor.fetchone()[0]
        connection.commit()

        unresolved = CollectionMonitorRepository().unresolved_partition_failures()
        assert api_name not in unresolved
    finally:
        with connection.cursor() as cursor:
            if collection_job_id is not None:
                cursor.execute(
                    "DELETE FROM sys_collection_job WHERE job_id=%s",
                    (collection_job_id,),
                )
            if campaign_id is not None:
                cursor.execute(
                    "DELETE FROM sys_collection_fanout_campaign WHERE campaign_id=%s",
                    (campaign_id,),
                )
        connection.commit()
        connection.close()


def test_dataset_repository_applies_direction_to_every_order_column():
    table_name = f"dataset_order_{uuid4().hex[:12]}"
    connection = psycopg2.connect(**DB_CONFIG)
    database = None
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                f'CREATE TABLE "{table_name}" '
                '(trade_date DATE NOT NULL, ts_code TEXT NOT NULL)'
            )
            cursor.execute(
                f'INSERT INTO "{table_name}" VALUES '
                "('2026-08-28', '000001.SZ'), "
                "('2026-08-28', '000002.SZ'), "
                "('2026-08-29', '000001.SZ')"
            )
        connection.commit()

        dataset = DatasetSpec(
            name="dataset_order",
            table=table_name,
            description="ordering contract test",
            category="test",
            primary_keys=("trade_date", "ts_code"),
            default_order=("trade_date", "ts_code"),
            default_descending=True,
        )
        database = Database(DB_CONFIG, min_connections=1, max_connections=1)
        rows = DatasetRepository(database).records(
            dataset,
            DatasetQuery(exact_filters={}, limit=3),
        )

        assert [(row["trade_date"], row["ts_code"]) for row in rows] == [
            (date(2026, 8, 29), "000001.SZ"),
            (date(2026, 8, 28), "000002.SZ"),
            (date(2026, 8, 28), "000001.SZ"),
        ]
    finally:
        if database is not None:
            database.close()
        connection.rollback()
        with connection.cursor() as cursor:
            cursor.execute(f'DROP TABLE IF EXISTS "{table_name}"')
        connection.commit()
        connection.close()


def test_initialization_campaign_atomically_gates_first_install_and_preserves_upgrades():
    repository = InitializationRepository()
    original_runtime = repository.runtime_state()
    if repository.active():
        pytest.skip("an initialization campaign is already active in this database")

    key = f"integration-initialization-{uuid4().hex}"
    initialization_ids = []
    try:
        connection = psycopg2.connect(**DB_CONFIG)
        with connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE sys_collection_runtime_state
                    SET mode='awaiting_initialization', active_initialization_id=NULL
                    WHERE singleton
                    """
                )
        connection.close()
        value, created = repository.create(
            profile="full",
            history_start=date(2026, 8, 1),
            history_end=date(2026, 8, 28),
            auto_activate=False,
            idempotency_key=key,
            options={"contract_test": True},
        )
        initialization_id = value["initialization_id"]
        initialization_ids.append(initialization_id)
        assert created is True
        assert repository.runtime_state()["mode"] == "initializing"
        assert repository.runtime_state()["active_initialization_id"] == initialization_id
        assert value["options"]["background"] is False

        duplicate, duplicate_created = repository.create(
            profile="full",
            history_start=date(2026, 8, 1),
            history_end=date(2026, 8, 28),
            auto_activate=False,
            idempotency_key=key,
            options={"contract_test": True},
        )
        assert duplicate_created is False
        assert duplicate["initialization_id"] == initialization_id

        repository.set_status(initialization_id, "ready")
        repository.activate(initialization_id)
        assert repository.runtime_state()["mode"] == "daily"
        assert repository.get(initialization_id)["status"] == "completed"

        background, created = repository.create(
            profile="full",
            history_start=date(2026, 8, 1),
            history_end=date(2026, 8, 28),
            auto_activate=False,
            idempotency_key=f"{key}-background",
            options={"contract_test": True},
        )
        background_id = background["initialization_id"]
        initialization_ids.append(background_id)
        assert created is True
        assert background["options"]["background"] is True
        assert repository.runtime_state()["mode"] == "daily"
        assert repository.runtime_state()["active_initialization_id"] == background_id
        repository.set_status(background_id, "ready")
        repository.activate(background_id)
    finally:
        connection = psycopg2.connect(**DB_CONFIG)
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE sys_collection_runtime_state
                    SET mode=%s, active_initialization_id=NULL, updated_at=NOW()
                    WHERE singleton
                    """,
                    (original_runtime["mode"],),
                )
                for initialization_id in initialization_ids:
                    cursor.execute(
                        "DELETE FROM sys_collection_initialization WHERE initialization_id=%s",
                        (initialization_id,),
                    )
            connection.commit()
        finally:
            connection.close()


def test_estimated_rows_follows_a_registered_view_to_its_base_table():
    suffix = uuid4().hex[:12]
    table_name = f"estimate_base_{suffix}"
    view_name = f"estimate_view_{suffix}"
    connection = psycopg2.connect(**DB_CONFIG)
    database = None
    try:
        with connection.cursor() as cursor:
            cursor.execute(f'CREATE TABLE "{table_name}" (id integer PRIMARY KEY)')
            cursor.execute(
                f'INSERT INTO "{table_name}" SELECT generate_series(1, 200)'
            )
            cursor.execute(f'ANALYZE "{table_name}"')
            cursor.execute(
                f'CREATE VIEW "{view_name}" AS SELECT * FROM "{table_name}"'
            )
        connection.commit()
        dataset = DatasetSpec(
            name="estimated_view",
            table=view_name,
            description="view row-estimate contract test",
            category="test",
            primary_keys=("id",),
        )
        database = Database(DB_CONFIG, min_connections=1, max_connections=1)

        estimated = DatasetRepository(database).estimated_rows(dataset)

        assert estimated >= 200
    finally:
        if database is not None:
            database.close()
        connection.rollback()
        with connection.cursor() as cursor:
            cursor.execute(f'DROP VIEW IF EXISTS "{view_name}"')
            cursor.execute(f'DROP TABLE IF EXISTS "{table_name}"')
        connection.commit()
        connection.close()


def test_collector_tables_and_generic_upsert_keys_match_postgres():
    connection = psycopg2.connect(**DB_CONFIG)
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT tablename FROM pg_tables WHERE schemaname = 'public'"
            )
            tables = {row[0] for row in cursor.fetchall()}

            errors = []
            for contract in discover_collectors():
                if contract.table_name not in tables:
                    errors.append(f"{contract.qualified_name}: missing table {contract.table_name}")
                    continue
                if not contract.uses_generic_store:
                    continue
                cursor.execute(
                    """
                    SELECT attribute.attname
                    FROM pg_constraint constraint_row
                    CROSS JOIN LATERAL unnest(constraint_row.conkey)
                        WITH ORDINALITY key_column(attnum, position)
                    JOIN pg_attribute attribute
                      ON attribute.attrelid = constraint_row.conrelid
                     AND attribute.attnum = key_column.attnum
                    WHERE constraint_row.conrelid = %s::regclass
                      AND constraint_row.contype = 'p'
                    ORDER BY key_column.position
                    """,
                    (contract.table_name,),
                )
                database_keys = {row[0] for row in cursor.fetchall()}
                if database_keys != set(contract.primary_keys):
                    errors.append(
                        f"{contract.qualified_name}: code keys "
                        f"{sorted(contract.primary_keys)} != database keys "
                        f"{sorted(database_keys)}"
                    )
    finally:
        connection.close()

    assert errors == []


def test_kpl_list_monetary_fields_have_amount_precision():
    connection = psycopg2.connect(**DB_CONFIG)
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT column_name, numeric_precision, numeric_scale
                FROM information_schema.columns
                WHERE table_schema='public' AND table_name='kpl_list'
                  AND column_name IN ('net_change', 'bid_change')
                ORDER BY column_name
                """
            )
            values = {
                name: (precision, scale)
                for name, precision, scale in cursor.fetchall()
            }
    finally:
        connection.close()

    assert values == {
        "bid_change": (18, 2),
        "net_change": (18, 2),
    }


def test_limit_cpt_list_accepts_multi_digit_streak_descriptions():
    connection = psycopg2.connect(**DB_CONFIG)
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT character_maximum_length
                FROM information_schema.columns
                WHERE table_schema='public' AND table_name='limit_cpt_list'
                  AND column_name='up_stat'
                """
            )
            maximum_length = cursor.fetchone()[0]
    finally:
        connection.close()

    assert maximum_length >= len("12天7板")


def test_unresolved_failure_is_recovered_only_by_the_same_partition():
    api_name = f"contract_{uuid4().hex[:20]}"
    connection = psycopg2.connect(**DB_CONFIG)
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO sys_collection_job
                    (task_name, api_name, parameters, status, period_key,
                     expected_for, completion_status, finished_at)
                VALUES
                    ('contract_test', %s, '{}'::jsonb, 'failed', '2026-01-01',
                     DATE '2026-01-01', 'failed', NOW()),
                    ('contract_test', %s, '{}'::jsonb, 'success', '2026-01-02',
                     DATE '2026-01-02', 'complete', NOW())
                """,
                (api_name, api_name),
            )
        connection.commit()

        unresolved = CollectionMonitorRepository().unresolved_partition_failures()
        assert unresolved[api_name]["period_key"] == "2026-01-01"

        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO sys_collection_job
                    (task_name, api_name, parameters, status, period_key,
                     expected_for, completion_status, finished_at)
                VALUES ('contract_test', %s, '{}'::jsonb, 'success', '2026-01-01',
                        DATE '2026-01-01', 'incomplete', NOW())
                """,
                (api_name,),
            )
        connection.commit()

        unresolved = CollectionMonitorRepository().unresolved_partition_failures()
        assert unresolved[api_name]["status"] == "success"
        assert unresolved[api_name]["completion_status"] == "incomplete"

        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO sys_collection_job
                    (task_name, api_name, parameters, status, period_key,
                     expected_for, completion_status, finished_at)
                VALUES ('contract_test', %s, '{}'::jsonb, 'success', 'recovery-key',
                        DATE '2026-01-01', 'complete', NOW())
                """,
                (api_name,),
            )
        connection.commit()

        assert api_name not in (
            CollectionMonitorRepository().unresolved_partition_failures()
        )
    finally:
        connection.rollback()
        with connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM sys_collection_job WHERE api_name=%s",
                (api_name,),
            )
        connection.commit()
        connection.close()


def test_partial_result_is_not_an_incident_before_delivery_deadline():
    suffix = uuid4().hex[:12]
    api_name = f"deadline_{suffix}"
    schedule_id = f"deadline_schedule_{suffix}"
    business_date = date.today()
    scheduled_for = datetime.now(timezone.utc) - timedelta(hours=2)
    connection = psycopg2.connect(**DB_CONFIG)
    job_id = None
    delivery_plan_id = None
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO sys_collection_job(
                    task_name, api_name, parameters, status, period_key,
                    expected_for, completion_status, finished_at
                ) VALUES (
                    'tushare_interface', %s,
                    jsonb_build_object(
                        'schedule_id', %s,
                        'scheduled_for', %s
                    ),
                    'success', %s, %s, 'incomplete', NOW()
                ) RETURNING job_id
                """,
                (
                    api_name,
                    schedule_id,
                    scheduled_for.isoformat(),
                    business_date.isoformat(),
                    business_date,
                ),
            )
            job_id = cursor.fetchone()[0]
            cursor.execute(
                """
                INSERT INTO sys_collection_delivery_plan(
                    business_date, plan_key, source_type, source_key,
                    api_name, title, cadence, scheduled_for, due_at,
                    expected_for, period_key
                ) VALUES (
                    %s, %s, 'dedicated', %s, %s, %s, 'daily',
                    %s, NOW() + INTERVAL '1 hour', %s, %s
                ) RETURNING delivery_plan_id
                """,
                (
                    business_date,
                    f"deadline:{suffix}",
                    schedule_id,
                    api_name,
                    api_name,
                    scheduled_for,
                    business_date,
                    business_date.isoformat(),
                ),
            )
            delivery_plan_id = cursor.fetchone()[0]
        connection.commit()

        unresolved = CollectionMonitorRepository().unresolved_partition_failures()
        assert api_name not in unresolved

        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE sys_collection_delivery_plan
                SET due_at=NOW() - INTERVAL '1 second'
                WHERE delivery_plan_id=%s
                """,
                (delivery_plan_id,),
            )
        connection.commit()

        unresolved = CollectionMonitorRepository().unresolved_partition_failures()
        assert unresolved[api_name]["job_id"] == job_id
    finally:
        connection.rollback()
        with connection.cursor() as cursor:
            if delivery_plan_id is not None:
                cursor.execute(
                    "DELETE FROM sys_collection_delivery_plan WHERE delivery_plan_id=%s",
                    (delivery_plan_id,),
                )
            if job_id is not None:
                cursor.execute(
                    "DELETE FROM sys_collection_job WHERE job_id=%s",
                    (job_id,),
                )
        connection.commit()
        connection.close()


def test_specialized_tables_match_authorized_upstream_contracts():
    connection = psycopg2.connect(**DB_CONFIG)
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT table_name, column_name, data_type,
                       numeric_precision, numeric_scale
                FROM information_schema.columns
                WHERE table_schema='public'
                  AND (
                    (table_name='moneyflow_ind_dc'
                     AND column_name='buy_sm_amount_stock')
                    OR (table_name='repurchase' AND column_name='proc')
                    OR (table_name='ths_hot'
                        AND column_name IN ('hot', 'rank_reason'))
                  )
                """
            )
            columns = {
                (table_name, column_name): (data_type, precision, scale)
                for table_name, column_name, data_type, precision, scale
                in cursor.fetchall()
            }
            cursor.execute(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema='public' AND table_name='stk_factor_pro'
                """
            )
            factor_columns = {row[0] for row in cursor.fetchall()}
    finally:
        connection.close()

    assert columns[("moneyflow_ind_dc", "buy_sm_amount_stock")][0] == "text"
    assert columns[("repurchase", "proc")][0] == "character varying"
    assert columns[("ths_hot", "hot")] == ("numeric", 20, 4)
    assert columns[("ths_hot", "rank_reason")][0] == "text"
    assert len(factor_columns) == 262  # 261 upstream fields plus created_at
    assert {
        "asi_bfq",
        "boll_upper_qfq",
        "kdj_k_hfq",
        "macd_dif_qfq",
        "rsi_qfq_24",
        "xsii_td4_qfq",
    } <= factor_columns


def test_public_dataset_contracts_match_postgres_schema():
    connection = psycopg2.connect(**DB_CONFIG)
    errors = []
    try:
        with connection.cursor() as cursor:
            for dataset in DATASETS.list():
                cursor.execute(
                    """
                    SELECT column_name, data_type
                    FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = %s
                    """,
                    (dataset.table,),
                )
                columns = dict(cursor.fetchall())
                expected = {
                    *dataset.primary_keys,
                    *dataset.exact_filters.values(),
                    *dataset.default_order,
                }
                if dataset.date_column:
                    expected.add(dataset.date_column)
                missing = sorted(expected - set(columns))
                if not columns:
                    errors.append(f"{dataset.name}: missing table {dataset.table}")
                elif missing:
                    errors.append(f"{dataset.name}: missing columns {missing}")
                elif dataset.date_column:
                    expected_type = (
                        "character varying"
                        if dataset.date_storage == DateStorage.COMPACT
                        else "date"
                    )
                    actual_type = columns[dataset.date_column]
                    if actual_type != expected_type:
                        errors.append(
                            f"{dataset.name}: date column type {actual_type} "
                            f"!= {expected_type}"
                        )
    finally:
        connection.close()

    assert errors == []


def test_reviewed_normalized_identities_have_lossless_current_views():
    reviewed = [
        contract
        for contract in NORMALIZATION_CONTRACTS.list()
        if contract.identity_confidence == "contract_reviewed"
    ]
    connection = psycopg2.connect(**DB_CONFIG)
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT table_name
                FROM information_schema.views
                WHERE table_schema='public'
                  AND table_name LIKE 'tushare_current_%'
                """
            )
            views = {row[0] for row in cursor.fetchall()}
            assert views == {
                f"tushare_current_{contract.api_name}" for contract in reviewed
            }

            suffix = uuid4().hex
            first_hash = ("d" + suffix)[:64].ljust(64, "d")
            second_hash = ("e" + suffix)[:64].ljust(64, "e")
            request_hash = ("f" + suffix)[:64].ljust(64, "f")
            cursor.execute(
                """
                INSERT INTO tushare_norm_daily_basic (
                    _record_hash, _request_hash, _source_collected_at,
                    trade_date, ts_code, close
                ) VALUES
                    (%s, %s, %s, %s, %s, %s),
                    (%s, %s, %s, %s, %s, %s)
                """,
                (
                    first_hash,
                    request_hash,
                    datetime(2026, 8, 30, 1, tzinfo=timezone.utc),
                    date(2099, 1, 2),
                    "CURRENT.TEST",
                    1,
                    second_hash,
                    request_hash,
                    datetime(2026, 8, 30, 2, tzinfo=timezone.utc),
                    date(2099, 1, 2),
                    "CURRENT.TEST",
                    2,
                ),
            )
            cursor.execute(
                """
                SELECT count(*), max(close)
                FROM tushare_current_daily_basic
                WHERE trade_date=%s AND ts_code=%s
                """,
                (date(2099, 1, 2), "CURRENT.TEST"),
            )
            assert cursor.fetchone() == (1, 2)
    finally:
        connection.rollback()
        connection.close()


def test_tushare_normalizer_types_rows_and_quarantines_invalid_identity():
    suffix = uuid4().hex
    valid_hash = ("a" + suffix)[:64].ljust(64, "a")
    invalid_hash = ("b" + suffix)[:64].ljust(64, "b")
    request_hash = ("c" + suffix)[:64].ljust(64, "c")
    extra_field = f"integration_{suffix[:12]}"
    normalizer = TushareNormalizer()
    try:
        result = normalizer.normalize(
            "adj_factor",
            request_hash,
            [
                (
                    valid_hash,
                    {
                        "ts_code": "000001.SZ",
                        "trade_date": "20260828",
                        "adj_factor": 123.456,
                        extra_field: "preserved",
                    },
                ),
                (
                    invalid_hash,
                    {
                        "ts_code": "000001.SZ",
                        "trade_date": "not-a-date",
                        "adj_factor": 1,
                    },
                ),
            ],
            source_doc_id=28,
        )
        assert result.normalized_rows == 1
        assert result.quarantined_rows == 1
        assert extra_field in result.unknown_fields

        connection = psycopg2.connect(**DB_CONFIG)
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT ts_code, trade_date, adj_factor, _extra_payload
                    FROM tushare_norm_adj_factor WHERE _record_hash=%s
                    """,
                    (valid_hash,),
                )
                row = cursor.fetchone()
                assert row[0] == "000001.SZ"
                assert row[1] == date(2026, 8, 28)
                assert str(row[2]) == "123.456"
                assert row[3][extra_field] == "preserved"
                cursor.execute(
                    """
                    SELECT error_code FROM sys_tushare_normalization_error
                    WHERE api_name='adj_factor' AND request_hash=%s
                      AND record_hash=%s AND resolved_at IS NULL
                    """,
                    (request_hash, invalid_hash),
                )
                assert cursor.fetchone()[0] == "type_conversion"
        finally:
            connection.close()
    finally:
        connection = psycopg2.connect(**DB_CONFIG)
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM tushare_norm_adj_factor WHERE _record_hash IN (%s, %s)",
                    (valid_hash, invalid_hash),
                )
                cursor.execute(
                    "DELETE FROM sys_tushare_normalization_error WHERE request_hash=%s",
                    (request_hash,),
                )
                cursor.execute(
                    "DELETE FROM sys_tushare_normalization_run WHERE request_hash=%s",
                    (request_hash,),
                )
                cursor.execute(
                    "DELETE FROM sys_tushare_schema_drift WHERE field_name=%s",
                    (extra_field,),
                )
            connection.commit()
        finally:
            connection.close()


def test_shared_collector_sink_bulk_upserts_and_skips_unchanged_updates():
    table_name = f"collector_sink_{uuid4().hex[:12]}"
    connection = psycopg2.connect(**DB_CONFIG)
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                f'CREATE TABLE "{table_name}" '
                '(id INTEGER PRIMARY KEY, value TEXT NOT NULL)'
            )
        connection.commit()

        class SinkCollector(BaseCollector):
            API_NAME = "test_sink"
            pk_columns = ["id"]

        collector = object.__new__(SinkCollector)
        collector.table_name = table_name
        import pandas as pd

        assert collector.store(pd.DataFrame([{"id": 1, "value": "a"}])) == 1
        assert collector.store(pd.DataFrame([{"id": 1, "value": "a"}])) == 1
        assert collector.store(pd.DataFrame([{"id": 1, "value": "b"}])) == 1
        assert collector.store(
            pd.DataFrame(
                [
                    {"id": 2, "value": "superseded-in-batch"},
                    {"id": 2, "value": "last-in-batch"},
                ]
            )
        ) == 1

        with connection.cursor() as cursor:
            cursor.execute(f'SELECT id, value FROM "{table_name}" ORDER BY id')
            assert cursor.fetchall() == [(1, "b"), (2, "last-in-batch")]
    finally:
        connection.rollback()
        with connection.cursor() as cursor:
            cursor.execute(f'DROP TABLE IF EXISTS "{table_name}"')
        connection.commit()
        connection.close()


def test_snapshot_sink_replaces_stale_keys_but_empty_input_is_fail_safe():
    table_name = f"collector_snapshot_{uuid4().hex[:12]}"
    connection = psycopg2.connect(**DB_CONFIG)
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                f'CREATE TABLE "{table_name}" '
                '(id INTEGER PRIMARY KEY, value TEXT NOT NULL)'
            )
            cursor.execute(
                f'INSERT INTO "{table_name}" VALUES (1, %s), (2, %s)',
                ("old", "stale"),
            )
        connection.commit()

        class SnapshotCollector(BaseCollector):
            API_NAME = "test_snapshot"
            pk_columns = ["id"]

        collector = object.__new__(SnapshotCollector)
        collector.table_name = table_name
        import pandas as pd

        assert collector.store_snapshot(
            pd.DataFrame([{"id": 1, "value": "new"}, {"id": 3, "value": "added"}])
        ) == 2
        assert collector.store_snapshot(pd.DataFrame()) == 0

        with connection.cursor() as cursor:
            cursor.execute(f'SELECT id, value FROM "{table_name}" ORDER BY id')
            assert cursor.fetchall() == [(1, "new"), (3, "added")]
    finally:
        connection.rollback()
        with connection.cursor() as cursor:
            cursor.execute(f'DROP TABLE IF EXISTS "{table_name}"')
        connection.commit()
        connection.close()


def test_partition_snapshot_reconciles_only_staged_partitions():
    table_name = f"collector_partition_{uuid4().hex[:12]}"
    connection = psycopg2.connect(**DB_CONFIG)
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                f'CREATE TABLE "{table_name}" '
                '(scope TEXT NOT NULL, id INTEGER NOT NULL, value TEXT NOT NULL, '
                'PRIMARY KEY (scope, id))'
            )
            cursor.execute(
                f'INSERT INTO "{table_name}" VALUES '
                "('a', 1, 'old'), ('a', 2, 'stale'), ('b', 1, 'preserved')"
            )
        connection.commit()

        class PartitionCollector(BaseCollector):
            API_NAME = "test_partition_snapshot"
            pk_columns = ["scope", "id"]

        collector = object.__new__(PartitionCollector)
        collector.table_name = table_name
        import pandas as pd

        assert collector.store_partition_snapshot(
            pd.DataFrame([
                {"scope": "a", "id": 1, "value": "new"},
                {"scope": "a", "id": 3, "value": "added"},
            ]),
            partition_columns=("scope",),
        ) == 2

        with connection.cursor() as cursor:
            cursor.execute(
                f'SELECT scope, id, value FROM "{table_name}" ORDER BY scope, id'
            )
            assert cursor.fetchall() == [
                ("a", 1, "new"),
                ("a", 3, "added"),
                ("b", 1, "preserved"),
            ]
    finally:
        connection.rollback()
        with connection.cursor() as cursor:
            cursor.execute(f'DROP TABLE IF EXISTS "{table_name}"')
        connection.commit()
        connection.close()


def test_collection_queue_claims_higher_priority_first():
    repository = JobRepository()
    suffix = uuid4().hex
    resource_class = f"it-priority-{suffix[:12]}"
    low, _ = repository.create(
        "tushare_interface",
        {"api_name": "cn_cpi", "parameters": {}},
        max_attempts=1,
        idempotency_key=f"priority-low-{suffix}",
        priority=10,
        resource_class=resource_class,
    )
    high, _ = repository.create(
        "stock_daily",
        {"trade_date": "20260828"},
        max_attempts=1,
        idempotency_key=f"priority-high-{suffix}",
        priority=90,
        resource_class=resource_class,
    )
    claimed = None
    try:
        claimed = repository.claim_next(
            "priority-integration",
            lease_seconds=30,
            resource_classes=(resource_class,),
        )
        assert claimed["job_id"] == high["job_id"]
        assert claimed["priority"] == 90
        assert claimed["resource_class"] == resource_class
    finally:
        connection = psycopg2.connect(**DB_CONFIG)
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM sys_collection_job WHERE job_id IN (%s, %s)",
                    (low["job_id"], high["job_id"]),
                )
            connection.commit()
        finally:
            connection.close()


def test_collection_queue_claim_respects_worker_resource_pool():
    repository = JobRepository()
    suffix = uuid4().hex
    allowed, _ = repository.create(
        "stock_daily",
        {"trade_date": "20260828"},
        max_attempts=1,
        idempotency_key=f"pool-allowed-{suffix}",
        priority=10,
        resource_class="integration-routine",
    )
    blocked, _ = repository.create(
        "tushare_interface",
        {"api_name": "cn_cpi", "parameters": {}},
        max_attempts=1,
        idempotency_key=f"pool-blocked-{suffix}",
        priority=100,
        resource_class="integration-backfill",
    )
    try:
        claimed = repository.claim_next(
            "pool-integration",
            lease_seconds=30,
            resource_classes=("integration-routine",),
        )
        assert claimed["job_id"] == allowed["job_id"]
        assert claimed["resource_class"] == "integration-routine"
        assert repository.get(blocked["job_id"])["status"] == "queued"
    finally:
        connection = psycopg2.connect(**DB_CONFIG)
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM sys_collection_job WHERE job_id IN (%s, %s)",
                    (allowed["job_id"], blocked["job_id"]),
                )
            connection.commit()
        finally:
            connection.close()


def test_tushare_raw_table_has_json_contract_and_primary_key():
    connection = psycopg2.connect(**DB_CONFIG)
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT column_name, data_type
                  FROM information_schema.columns
                 WHERE table_schema = 'public'
                   AND table_name = 'tushare_raw_record'
                """
            )
            columns = dict(cursor.fetchall())
            cursor.execute(
                """
                SELECT attribute.attname
                  FROM pg_constraint constraint_row
                  CROSS JOIN LATERAL unnest(constraint_row.conkey)
                    WITH ORDINALITY key_column(attnum, position)
                  JOIN pg_attribute attribute
                    ON attribute.attrelid = constraint_row.conrelid
                   AND attribute.attnum = key_column.attnum
                 WHERE constraint_row.conrelid = 'tushare_raw_record'::regclass
                   AND constraint_row.contype = 'p'
                 ORDER BY key_column.position
                """
            )
            primary_key = tuple(row[0] for row in cursor.fetchall())
    finally:
        connection.close()

    assert columns["request_params"] == "jsonb"
    assert columns["payload"] == "jsonb"
    assert primary_key == ("api_name", "request_hash", "record_hash")


def test_tushare_checkpoint_table_supports_resumable_pages():
    connection = psycopg2.connect(**DB_CONFIG)
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'sys_tushare_collection_checkpoint'
                """
            )
            columns = {row[0] for row in cursor.fetchall()}
    finally:
        connection.close()

    assert {
        "api_name",
        "scope_hash",
        "next_offset",
        "pages_completed",
        "rows_fetched",
        "rows_stored",
        "last_page_hash",
    } <= columns


def test_collection_job_queue_exposes_health_snapshot():
    snapshot = JobRepository().health_snapshot()

    assert {
        "recent_failed",
        "stale_queued",
        "stale_running",
        "queued",
        "running",
    } == set(snapshot)
    assert all(value >= 0 for value in snapshot.values())


def test_collection_job_health_does_not_count_a_recovered_execution_failure():
    api_name = f"health_recovery_{uuid4().hex[:16]}"
    repository = JobRepository()
    baseline = int(repository.health_snapshot()["recent_failed"])
    connection = psycopg2.connect(**DB_CONFIG)
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO sys_collection_job
                    (task_name, api_name, parameters, status, period_key,
                     expected_for, completion_status, finished_at)
                VALUES ('contract_test', %s, '{}'::jsonb, 'failed', '2026-01-01',
                        DATE '2026-01-01', 'failed', NOW())
                """,
                (api_name,),
            )
        connection.commit()
        assert int(repository.health_snapshot()["recent_failed"]) == baseline + 1

        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO sys_collection_job
                    (task_name, api_name, parameters, status, period_key,
                     expected_for, completion_status, finished_at)
                VALUES ('contract_test', %s, '{}'::jsonb, 'success', '2026-01-01',
                        DATE '2026-01-01', 'incomplete', NOW())
                """,
                (api_name,),
            )
        connection.commit()
        assert int(repository.health_snapshot()["recent_failed"]) == baseline
    finally:
        connection.rollback()
        with connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM sys_collection_job WHERE api_name=%s",
                (api_name,),
            )
        connection.commit()
        connection.close()


def test_collection_jobs_store_interface_period_and_completion_evidence():
    connection = psycopg2.connect(**DB_CONFIG)
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'sys_collection_job'
                """
            )
            columns = {row[0] for row in cursor.fetchall()}
    finally:
        connection.close()

    assert {
        "api_name",
        "cadence",
        "period_key",
        "expected_for",
        "rows_fetched",
        "completion_status",
        "completion_evidence",
        "handler_type",
        "handler_key",
        "handler_version",
        "code_revision",
        "heartbeat_at",
        "lease_expires_at",
    } <= columns


def test_fanout_campaign_schema_tracks_verified_and_planned_progress():
    connection = psycopg2.connect(**DB_CONFIG)
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema='public'
                  AND table_name='sys_collection_fanout_campaign'
                """
            )
            campaign_columns = {row[0] for row in cursor.fetchall()}
            cursor.execute(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema='public'
                  AND table_name='sys_collection_fanout_campaign_batch'
                """
            )
            page_columns = {row[0] for row in cursor.fetchall()}
            cursor.execute(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema='public'
                  AND table_name='sys_collection_fanout_campaign_entity'
                """
            )
            entity_columns = {row[0] for row in cursor.fetchall()}
            cursor.execute(
                """
                SELECT pg_get_constraintdef(oid)
                FROM pg_constraint
                WHERE conrelid='sys_collection_initialization_step'::regclass
                  AND conname='ck_collection_initialization_step_resource'
                """
            )
            resource_constraint = cursor.fetchone()[0]
    finally:
        connection.close()

    assert {
        "api_name", "request", "status", "completion_status",
        "universe_total", "universe_digest", "next_offset",
        "completed_offset", "pages_created", "pages_completed",
        "rows_fetched", "rows_inserted", "initialization_id",
        "cadence", "period_key", "expected_for",
    } <= campaign_columns
    assert {
        "campaign_id", "page_index", "batch_job_id", "entity_offset",
        "next_offset", "entities_selected", "selected_digest",
    } <= page_columns
    assert {"campaign_id", "entity_index", "entity_value"} <= entity_columns
    assert "fanout" in resource_constraint


def test_collection_job_handler_constraint_accepts_all_routing_modes():
    connection = psycopg2.connect(**DB_CONFIG)
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT pg_get_constraintdef(oid)
                FROM pg_constraint
                WHERE conrelid = 'sys_collection_job'::regclass
                  AND conname = 'ck_collection_job_handler_type'
                """
            )
            definition = cursor.fetchone()[0]
    finally:
        connection.close()

    assert "generic" in definition
    assert "dedicated" in definition
    assert "specialized" in definition


def test_dedicated_schedule_cursor_is_persistent():
    connection = psycopg2.connect(**DB_CONFIG)
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'sys_collection_schedule_cursor'
                """
            )
            columns = {row[0] for row in cursor.fetchall()}
    finally:
        connection.close()

    assert {
        "schedule_id",
        "last_dispatched_for",
        "last_job_id",
        "handler_key",
        "handler_version",
    } <= columns


def test_expired_leases_are_requeued_then_fail_after_final_attempt():
    key = f"integration-expired-{uuid4().hex}"
    connection = psycopg2.connect(**DB_CONFIG)
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO sys_collection_job
                    (task_name, parameters, status, attempt, max_attempts,
                     idempotency_key, worker_id, started_at, lease_expires_at)
                VALUES ('stock_basic', '{}'::jsonb, 'running', 1, 2,
                        %s, 'dead-worker', NOW() - INTERVAL '5 minutes',
                        NOW() - INTERVAL '1 minute')
                RETURNING job_id
                """,
                (key,),
            )
            job_id = cursor.fetchone()[0]
        connection.commit()

        assert JobRepository().recover_stale(3600) >= 1
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT status, completion_status FROM sys_collection_job WHERE job_id=%s",
                (job_id,),
            )
            assert cursor.fetchone() == ("queued", "retrying")
            cursor.execute(
                """
                UPDATE sys_collection_job
                SET status='running', attempt=2, worker_id='dead-again',
                    lease_expires_at=NOW() - INTERVAL '1 minute'
                WHERE job_id=%s
                """,
                (job_id,),
            )
        connection.commit()

        assert JobRepository().recover_stale(3600) >= 1
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT status, completion_status FROM sys_collection_job WHERE job_id=%s",
                (job_id,),
            )
            assert cursor.fetchone() == ("failed", "failed")
    finally:
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM sys_collection_job WHERE idempotency_key=%s", (key,))
        connection.commit()
        connection.close()


def test_empty_results_create_bounded_separately_auditable_rechecks():
    key = f"integration-empty-recheck-{uuid4().hex}"
    repository = JobRepository()
    connection = psycopg2.connect(**DB_CONFIG)
    root_job_id = None
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO sys_collection_job (
                    task_name, parameters, status, attempt, max_attempts,
                    completion_status, idempotency_key, api_name, cadence,
                    period_key, expected_for, handler_type, handler_key,
                    handler_version, code_revision, started_at, finished_at
                ) VALUES (
                    'tushare_interface', '{"api_name":"cn_cpi"}'::jsonb,
                    'success', 1, 3, 'empty', %s, 'cn_cpi', 'monthly',
                    '2026-08', DATE '2026-08-01', 'generic',
                    'catalog_typed:cn_cpi', '2', 'test',
                    NOW() - INTERVAL '10 seconds', NOW() - INTERVAL '5 seconds'
                )
                RETURNING job_id
                """,
                (key,),
            )
            root_job_id = cursor.fetchone()[0]
        connection.commit()

        first = repository.create_empty_recheck(
            root_job_id,
            min_interval_seconds=1,
            max_generations=2,
            window_days=30,
            handler=TASKS.handler_metadata(
                "tushare_interface", {"api_name": "cn_cpi", "parameters": {}}
            ),
        )
        assert first["recheck_of_job_id"] == root_job_id
        assert first["recheck_root_job_id"] == root_job_id
        assert first["recheck_generation"] == 1
        assert first["handler_version"] == "4"
        assert repository.create_empty_recheck(
            root_job_id,
            min_interval_seconds=1,
            max_generations=2,
            window_days=30,
            handler=TASKS.handler_metadata(
                "tushare_interface", {"api_name": "cn_cpi", "parameters": {}}
            ),
        ) is None

        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE sys_collection_job
                SET status='success', completion_status='empty', attempt=1,
                    started_at=NOW() - INTERVAL '10 seconds',
                    finished_at=NOW() - INTERVAL '5 seconds'
                WHERE job_id=%s
                """,
                (first["job_id"],),
            )
        connection.commit()
        second = repository.create_empty_recheck(
            root_job_id,
            min_interval_seconds=1,
            max_generations=2,
            window_days=30,
            handler=TASKS.handler_metadata(
                "tushare_interface", {"api_name": "cn_cpi", "parameters": {}}
            ),
        )
        assert second["recheck_generation"] == 2
        assert second["recheck_of_job_id"] == first["job_id"]
        assert repository.create_empty_recheck(
            root_job_id,
            min_interval_seconds=1,
            max_generations=2,
            window_days=30,
            handler=TASKS.handler_metadata(
                "tushare_interface", {"api_name": "cn_cpi", "parameters": {}}
            ),
        ) is None
    finally:
        if root_job_id is not None:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    DELETE FROM sys_collection_job
                    WHERE recheck_root_job_id=%s OR job_id=%s
                    """,
                    (root_job_id, root_job_id),
                )
            connection.commit()
        connection.close()


def test_schedule_cursor_advances_monotonically():
    suffix = uuid4().hex
    key = f"integration-schedule-job-{suffix}"
    schedule_id = f"integration_{suffix[:16]}"
    connection = psycopg2.connect(**DB_CONFIG)
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO sys_collection_job
                    (task_name, parameters, status, max_attempts, idempotency_key,
                     handler_type, handler_key, handler_version, code_revision)
                VALUES ('stock_basic', '{}'::jsonb, 'failed', 3, %s,
                        'dedicated', 'integration:stock_basic', '1', 'test')
                RETURNING job_id
                """,
                (key,),
            )
            job_id = cursor.fetchone()[0]
        connection.commit()
    finally:
        connection.close()
    cursors = ScheduleCursorRepository()
    later = datetime.now(timezone.utc)
    earlier = later - timedelta(days=1)
    try:
        cursors.advance(
            schedule_id,
            later,
            job_id=job_id,
            handler_key="schedule:test",
            handler_version="1",
        )
        cursors.advance(
            schedule_id,
            earlier,
            job_id=job_id,
            handler_key="schedule:test",
            handler_version="1",
        )
        assert cursors.get(schedule_id)["last_dispatched_for"] == later
    finally:
        connection = psycopg2.connect(**DB_CONFIG)
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM sys_collection_schedule_cursor WHERE schedule_id=%s",
                    (schedule_id,),
                )
                cursor.execute("DELETE FROM sys_collection_job WHERE job_id=%s", (job_id,))
            connection.commit()
        finally:
            connection.close()


def test_data_coverage_tables_support_independent_audits_and_partitions():
    connection = psycopg2.connect(**DB_CONFIG)
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT table_name, column_name
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name IN (
                    'sys_data_coverage_job',
                    'sys_data_coverage_audit',
                    'sys_data_coverage_partition'
                  )
                """
            )
            columns: dict[str, set[str]] = {}
            for table_name, column_name in cursor.fetchall():
                columns.setdefault(table_name, set()).add(column_name)
    finally:
        connection.close()

    assert {
        "dataset_name", "start_date", "end_date", "status", "collection_job_id"
    } <= columns[
        "sys_data_coverage_job"
    ]
    assert {"coverage_ratio", "missing_partitions", "evidence"} <= columns[
        "sys_data_coverage_audit"
    ]
    assert {"partition_date", "row_count", "entity_count", "expected"} <= columns[
        "sys_data_coverage_partition"
    ]


def test_daily_delivery_plan_is_persistent_without_an_execution_job():
    suffix = uuid4().hex[:10]
    day = date(2099, 1, 5)
    repository = DeliveryPlanRepository()
    plan_key = f"policy:integration_{suffix}:daily"
    scheduled_for = datetime(2099, 1, 5, 19, 15, tzinfo=timezone.utc)
    try:
        assert repository.upsert([
            {
                "business_date": day,
                "plan_key": plan_key,
                "source_type": "policy",
                "source_key": f"integration_{suffix}",
                "api_name": f"integration_{suffix}",
                "title": "integration delivery",
                "cadence": "daily",
                "scheduled_for": scheduled_for,
                "due_at": scheduled_for + timedelta(hours=4),
                "expected_for": day,
                "period_key": day.isoformat(),
                "metadata": {"test": True},
            }
        ]) == 1

        rows = repository.list_with_execution(day)
        row = next(item for item in rows if item["plan_key"] == plan_key)
        assert row["job_id"] is None
        assert row["campaign_id"] is None
        assert row["metadata"] == {"test": True}
    finally:
        connection = psycopg2.connect(**DB_CONFIG)
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM sys_collection_delivery_plan WHERE plan_key=%s",
                    (plan_key,),
                )
            connection.commit()
        finally:
            connection.close()


def test_collection_leaves_can_be_idempotently_bulk_enqueued():
    suffix = uuid4().hex
    repository = JobRepository()
    handler = TASKS.handler_metadata("stock_daily", {"trade_date": "20260828"})
    children = [
        BatchChildSpec(
            task_name="stock_daily",
            parameters={"trade_date": f"2026082{day}"},
            idempotency_key=f"integration-bulk-{suffix}-{day}",
            api_name="daily",
            cadence="repair",
            period_key=f"2026-08-2{day}",
            expected_for=date(2026, 8, 20 + day),
            handler=handler,
            resource_class="integration",
        )
        for day in (7, 8)
    ]

    try:
        created = repository.create_many(children)
        duplicate = repository.create_many(children)

        assert len(created) == 2
        assert duplicate == []
    finally:
        connection = psycopg2.connect(**DB_CONFIG)
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM sys_collection_job WHERE idempotency_key LIKE %s",
                    (f"integration-bulk-{suffix}-%",),
                )
            connection.commit()
        finally:
            connection.close()


def test_collection_finish_atomically_enqueues_and_applies_verification():
    key = f"integration-verification-{uuid4().hex}"
    repository = JobRepository()
    job, created = repository.create(
        "stock_daily",
        {"trade_date": "20260828"},
        max_attempts=2,
        idempotency_key=key,
    )
    assert created is True
    connection = psycopg2.connect(**DB_CONFIG)
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE sys_collection_job
                SET status='running', completion_status='running',
                    worker_id='integration-verifier', attempt=1,
                    started_at=NOW(), lease_expires_at=NOW() + INTERVAL '2 minutes'
                WHERE job_id=%s
                """,
                (job["job_id"],),
            )
        connection.commit()
    finally:
        connection.close()

    try:
        repository.finish(
            job["job_id"],
            rows_inserted=5000,
            rows_fetched=5000,
            worker_id="integration-verifier",
            verification={
                "dataset_name": "stock_daily",
                "start_date": date(2026, 8, 28),
                "end_date": date(2026, 8, 28),
                "idempotency_key": f"verify-collection-job-{job['job_id']}",
            },
        )

        connection = psycopg2.connect(**DB_CONFIG)
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT status, completion_status FROM sys_collection_job WHERE job_id=%s",
                    (job["job_id"],),
                )
                assert cursor.fetchone() == ("success", "verifying")
                cursor.execute(
                    """
                    SELECT job_id, dataset_name, status
                    FROM sys_data_coverage_job
                    WHERE collection_job_id=%s
                    """,
                    (job["job_id"],),
                )
                coverage_job_id, dataset_name, status = cursor.fetchone()
                assert (dataset_name, status) == ("stock_daily", "queued")
        finally:
            connection.close()

        repository.apply_verification_result(
            job["job_id"],
            audit_id=12345,
            audit_status="complete",
            dataset_name="stock_daily",
            missing_partitions=0,
            partial_partitions=0,
            coverage_ratio=1.0,
        )
        assert repository.get(job["job_id"])["completion_status"] == "complete"
    finally:
        connection = psycopg2.connect(**DB_CONFIG)
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM sys_data_coverage_job WHERE collection_job_id=%s",
                    (job["job_id"],),
                )
                cursor.execute(
                    "DELETE FROM sys_collection_job WHERE job_id=%s",
                    (job["job_id"],),
                )
            connection.commit()
        finally:
            connection.close()


def test_collection_batch_parent_is_aggregated_and_failed_child_can_requeue():
    suffix = uuid4().hex
    repository = JobRepository()
    handler = TASKS.handler_metadata(
        "tushare_interface",
        {"api_name": "fut_basic", "parameters": {"exchange": "CFFEX"}},
    )
    children = [
        BatchChildSpec(
            task_name="tushare_interface",
            parameters={
                "api_name": "fut_basic",
                "parameters": {"exchange": exchange},
                "complete": True,
                "resume": True,
            },
            idempotency_key=f"integration-batch-child-{exchange}-{suffix}",
            api_name="fut_basic",
            cadence="backfill",
            period_key=None,
            expected_for=None,
            handler=handler,
            max_attempts=1,
        )
        for exchange in ("CFFEX", "DCE")
    ]
    parent, created = repository.create_batch(
        {"api_name": "fut_basic", "test": suffix},
        children,
        idempotency_key=f"integration-batch-{suffix}",
        api_name="fut_basic",
        period_key=None,
        expected_for=None,
    )
    assert created is True

    connection = psycopg2.connect(**DB_CONFIG)
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT job_id FROM sys_collection_job
                WHERE parent_job_id=%s ORDER BY job_id
                """,
                (parent["job_id"],),
            )
            child_ids = [row[0] for row in cursor.fetchall()]
            cursor.execute(
                """
                UPDATE sys_collection_job SET status='success',
                    completion_status='complete', rows_inserted=8,
                    rows_fetched=8, finished_at=NOW(),
                    completion_evidence='{"verified": true}'::jsonb
                WHERE job_id=%s
                """,
                (child_ids[0],),
            )
            cursor.execute(
                """
                UPDATE sys_collection_job SET status='failed',
                    completion_status='failed', attempt=1, max_attempts=1,
                    finished_at=NOW(), error_message='integration failure'
                WHERE job_id=%s
                """,
                (child_ids[1],),
            )
        connection.commit()

        failed_parent = repository.get(parent["job_id"])
        assert failed_parent["status"] == "failed"
        assert failed_parent["completion_status"] == "incomplete"
        assert failed_parent["child_total"] == 2
        assert failed_parent["child_succeeded"] == 1
        assert failed_parent["child_failed"] == 1
        assert failed_parent["rows_inserted"] == 8

        requeued = repository.requeue_failed_batch_child(child_ids[1])
        assert requeued["status"] == "queued"
        running_parent = repository.get(parent["job_id"])
        assert running_parent["status"] == "running"
        assert running_parent["child_queued"] == 1

        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE sys_collection_job SET status='success',
                    completion_status='complete', rows_inserted=5,
                    rows_fetched=5, finished_at=NOW(),
                    completion_evidence='{"verified": true}'::jsonb
                WHERE job_id=%s
                """,
                (child_ids[1],),
            )
        connection.commit()
        complete_parent = repository.get(parent["job_id"])
        assert complete_parent["status"] == "success"
        assert complete_parent["completion_status"] == "complete"
        assert complete_parent["completion_evidence"]["verified"] is True
        assert complete_parent["child_succeeded"] == 2
        assert complete_parent["rows_inserted"] == 13
    finally:
        with connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM sys_collection_job WHERE parent_job_id=%s",
                (parent["job_id"],),
            )
            cursor.execute(
                "DELETE FROM sys_collection_job WHERE job_id=%s",
                (parent["job_id"],),
            )
        connection.commit()
        connection.close()


def test_partial_fanout_batch_cannot_claim_whole_universe_complete():
    suffix = uuid4().hex
    repository = JobRepository()
    handler = TASKS.handler_metadata(
        "tushare_interface",
        {"api_name": "fut_basic", "parameters": {"exchange": "CFFEX"}},
    )
    child = BatchChildSpec(
        task_name="tushare_interface",
        parameters={
            "api_name": "fut_basic",
            "parameters": {"exchange": "CFFEX"},
            "complete": True,
            "resume": True,
        },
        idempotency_key=f"integration-partial-child-{suffix}",
        api_name="fut_basic",
        cadence="backfill",
        period_key=None,
        expected_for=None,
        handler=handler,
        max_attempts=1,
    )
    parent, _ = repository.create_batch(
        {
            "plan": {
                "entity_offset": 0,
                "entities_selected": 1,
                "universe_total": 2,
                "has_more": True,
            }
        },
        [child],
        idempotency_key=f"integration-partial-{suffix}",
        api_name="fut_basic",
        period_key=None,
        expected_for=None,
    )
    connection = psycopg2.connect(**DB_CONFIG)
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE sys_collection_job SET status='success',
                    completion_status='complete', rows_inserted=1,
                    rows_fetched=1, finished_at=NOW(),
                    completion_evidence='{"verified": true}'::jsonb
                WHERE parent_job_id=%s
                """,
                (parent["job_id"],),
            )
        connection.commit()

        refreshed = repository.get(parent["job_id"])
        assert refreshed["status"] == "success"
        assert refreshed["completion_status"] == "incomplete"
        assert refreshed["completion_evidence"]["verified"] is False
        assert refreshed["completion_evidence"]["universe_complete"] is False
    finally:
        with connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM sys_collection_job WHERE parent_job_id=%s",
                (parent["job_id"],),
            )
            cursor.execute(
                "DELETE FROM sys_collection_job WHERE job_id=%s",
                (parent["job_id"],),
            )
        connection.commit()
        connection.close()


def test_fanout_campaign_resumes_pages_and_only_completes_whole_universe(monkeypatch):
    suffix = uuid4().hex
    service = FanoutCampaignService()
    campaign, created = service.submit(
        {"api_name": "fut_basic", "page_size": 2},
        idempotency_key=f"integration-fanout-campaign-{suffix}",
    )
    assert created is True
    campaign_id = campaign["campaign_id"]
    original_definition = FANOUT_DEFINITIONS["fut_basic"]
    monkeypatch.setitem(
        FANOUT_DEFINITIONS,
        "fut_basic",
        replace(
            original_definition,
            static_values=original_definition.static_values + ("NEW_EXCHANGE",),
        ),
    )
    batch_ids: list[int] = []
    connection = psycopg2.connect(**DB_CONFIG)
    try:
        while campaign["status"] == "running":
            pages = campaign["pages"]
            assert pages
            latest = pages[-1]
            if latest["batch_job_id"] not in batch_ids:
                batch_ids.append(latest["batch_job_id"])
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        UPDATE sys_collection_job
                        SET status='success', completion_status='complete',
                            rows_fetched=1, rows_inserted=1,
                            completion_evidence='{"verified": true}'::jsonb,
                            finished_at=NOW()
                        WHERE parent_job_id=%s
                        """,
                        (latest["batch_job_id"],),
                    )
                connection.commit()
            campaign = service.reconcile(campaign_id)

        assert campaign["status"] == "success"
        assert campaign["completion_status"] == "complete"
        assert campaign["universe_total"] == 6
        assert campaign["completed_offset"] == 6
        assert campaign["next_offset"] == 6
        assert campaign["pages_created"] == 3
        assert campaign["pages_completed"] == 3
        assert campaign["progress_ratio"] == 1.0
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT entity_value
                FROM sys_collection_fanout_campaign_entity
                WHERE campaign_id=%s ORDER BY entity_index
                """,
                (campaign_id,),
            )
            assert [row[0] for row in cursor.fetchall()] == list(
                original_definition.static_values
            )

        duplicate, duplicate_created = service.submit(
            {"api_name": "fut_basic", "page_size": 2},
            idempotency_key=f"integration-fanout-campaign-{suffix}",
        )
        assert duplicate_created is False
        assert duplicate["campaign_id"] == campaign_id
    finally:
        with connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM sys_collection_fanout_campaign WHERE campaign_id=%s",
                (campaign_id,),
            )
            if batch_ids:
                cursor.execute(
                    "DELETE FROM sys_collection_job WHERE parent_job_id=ANY(%s)",
                    (batch_ids,),
                )
                cursor.execute(
                    "DELETE FROM sys_collection_job WHERE job_id=ANY(%s)",
                    (batch_ids,),
                )
        connection.commit()
        connection.close()


def test_coverage_audit_retry_updates_one_idempotent_record():
    suffix = uuid4().hex
    dataset_name = f"integration_coverage_{suffix[:8]}"
    repository = CoverageRepository()
    job, created = repository.create_job(
        dataset_name,
        date(2026, 8, 28),
        date(2026, 8, 28),
        idempotency_key=f"integration-audit-{suffix}",
    )
    assert created is True
    result = CoverageAuditResult(
        dataset_name=dataset_name,
        strategy="trading_daily",
        start_date=date(2026, 8, 28),
        end_date=date(2026, 8, 28),
        status="complete",
        expected_partitions=1,
        present_partitions=1,
        missing_partitions=0,
        observed_partitions=1,
        coverage_ratio=1.0,
        partitions=(),
        evidence={"attempt": 1},
    )

    try:
        first_id = repository.save_audit(job["job_id"], result)
        second_id = repository.save_audit(job["job_id"], result)
        assert second_id == first_id
        assert repository.covering_audit(
            dataset_name,
            start_date=date(2026, 8, 28),
            end_date=date(2026, 8, 28),
        )["audit_id"] == first_id
        assert repository.covering_audit(
            dataset_name,
            start_date=date(2026, 8, 27),
            end_date=date(2026, 8, 28),
        ) is None

        connection = psycopg2.connect(**DB_CONFIG)
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT count(*) FROM sys_data_coverage_audit WHERE job_id=%s",
                    (job["job_id"],),
                )
                assert cursor.fetchone()[0] == 1
        finally:
            connection.close()
    finally:
        connection = psycopg2.connect(**DB_CONFIG)
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM sys_data_coverage_audit WHERE job_id=%s",
                    (job["job_id"],),
                )
                cursor.execute(
                    "DELETE FROM sys_data_coverage_job WHERE job_id=%s",
                    (job["job_id"],),
                )
            connection.commit()
        finally:
            connection.close()


def test_scheduled_completion_recovery_is_atomic_and_idempotent():
    suffix = uuid4().hex
    repository = JobRepository()
    job, created = repository.create(
        "scheduled_collector",
        {
            "schedule_id": "index_daily_finalize",
            "scheduled_for": "2026-09-08T09:35:00+08:00",
        },
        max_attempts=3,
        idempotency_key=f"integration-scheduled-verification-{suffix}",
        api_name="index_daily",
        cadence="scheduled",
        period_key="20260908T0935+0800",
        expected_for=date(2026, 9, 8),
        resource_class="scheduled",
    )
    assert created is True
    connection = psycopg2.connect(**DB_CONFIG)
    coverage_job_id = None
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE sys_collection_job
                SET status='success', completion_status='unverified',
                    rows_fetched=100, rows_inserted=100, finished_at=NOW()
                WHERE job_id=%s
                """,
                (job["job_id"],),
            )
        connection.commit()

        verification = {
            "dataset_name": "index_daily",
            "start_date": date(2026, 9, 5),
            "end_date": date(2026, 9, 5),
            "idempotency_key": f"integration-scheduled-audit-{suffix}",
        }
        coverage_job_id = repository.queue_verification(job["job_id"], verification)
        assert coverage_job_id is not None
        assert repository.queue_verification(job["job_id"], verification) is None
        queued = repository.get(job["job_id"])
        assert queued["completion_status"] == "verifying"
        assert queued["completion_evidence"]["verification"]["coverage_job_id"] == coverage_job_id

        with connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM sys_data_coverage_job WHERE job_id=%s",
                (coverage_job_id,),
            )
            cursor.execute(
                """
                UPDATE sys_collection_job
                SET completion_status='unverified', completion_evidence='{}'::jsonb
                WHERE job_id=%s
                """,
                (job["job_id"],),
            )
        connection.commit()
        assert repository.apply_transport_verification(
            job["job_id"], {"verified": True, "verification_type": "test"}
        ) is True
        assert repository.apply_transport_verification(
            job["job_id"], {"verified": True}
        ) is False
        assert repository.get(job["job_id"])["completion_status"] == "complete"
    finally:
        with connection.cursor() as cursor:
            if coverage_job_id is not None:
                cursor.execute(
                    "DELETE FROM sys_data_coverage_job WHERE job_id=%s",
                    (coverage_job_id,),
                )
            cursor.execute(
                "DELETE FROM sys_collection_job WHERE job_id=%s",
                (job["job_id"],),
            )
        connection.commit()
        connection.close()


def test_coverage_rule_upgrade_requeues_only_the_database_audit_atomically():
    suffix = uuid4().hex
    dataset_name = f"integration_revision_{suffix}"
    collection_repository = JobRepository()
    coverage_repository = CoverageRepository()
    collection, created = collection_repository.create(
        "tushare_interface",
        {
            "api_name": "index_daily",
            "parameters": {"trade_date": "20260901"},
            "complete": True,
        },
        max_attempts=1,
        idempotency_key=f"integration-revision-collection-{suffix}",
        api_name="index_daily",
        cadence="test",
        period_key="20260901",
        expected_for=date(2026, 9, 1),
    )
    assert created is True
    coverage, created = coverage_repository.create_job(
        dataset_name,
        date(2026, 9, 1),
        date(2026, 9, 1),
        idempotency_key=f"integration-revision-audit-{suffix}",
        max_attempts=2,
        collection_job_id=collection["job_id"],
    )
    assert created is True
    connection = psycopg2.connect(**DB_CONFIG)
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE sys_collection_job
                SET status='success', completion_status='incomplete',
                    completion_evidence=%s::jsonb, finished_at=NOW()
                WHERE job_id=%s
                """,
                (
                    '{"verified":true,"verification":{"status":"gaps"}}',
                    collection["job_id"],
                ),
            )
            cursor.execute(
                """
                UPDATE sys_data_coverage_job
                SET status='success', attempt=1, finished_at=NOW()
                WHERE job_id=%s
                """,
                (coverage["job_id"],),
            )
            cursor.execute(
                """
                INSERT INTO sys_data_coverage_audit(
                    job_id,dataset_name,strategy,start_date,end_date,
                    expected_partitions,present_partitions,missing_partitions,
                    observed_partitions,partial_partitions,coverage_ratio,
                    status,evidence
                ) VALUES (%s,%s,'trading_daily',%s,%s,1,0,0,1,1,0,'gaps',
                          '{"rule_revision":1}'::jsonb)
                """,
                (
                    coverage["job_id"],
                    dataset_name,
                    date(2026, 9, 1),
                    date(2026, 9, 1),
                ),
            )
        connection.commit()

        assert coverage_repository.requeue_stale_rule_audits(
            dataset_name, rule_revision=2, limit=10
        ) == 1
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT coverage.status,coverage.attempt,
                       collection.completion_status,
                       collection.completion_evidence->'verification'
                              ->>'requested_rule_revision'
                FROM sys_data_coverage_job coverage
                JOIN sys_collection_job collection
                  ON collection.job_id=coverage.collection_job_id
                WHERE coverage.job_id=%s
                """,
                (coverage["job_id"],),
            )
            assert cursor.fetchone() == ("queued", 0, "verifying", "2")
    finally:
        connection.rollback()
        with connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM sys_data_coverage_audit WHERE job_id=%s",
                (coverage["job_id"],),
            )
            cursor.execute(
                "DELETE FROM sys_data_coverage_job WHERE job_id=%s",
                (coverage["job_id"],),
            )
            cursor.execute(
                "DELETE FROM sys_collection_job WHERE job_id=%s",
                (collection["job_id"],),
            )
        connection.commit()
        connection.close()
