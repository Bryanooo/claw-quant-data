import os
from datetime import date

import psycopg2
import pytest

from service.config import DB_CONFIG
from service.data_coverage.registry import COVERAGE_RULES
from service.data_coverage.repository import CoverageRepository


pytestmark = pytest.mark.skipif(
    os.getenv("RUN_DB_INTEGRATION") != "1",
    reason="set RUN_DB_INTEGRATION=1 for PostgreSQL integration tests",
)


def test_v2_control_plane_is_complete_and_v1_tables_are_absent():
    with psycopg2.connect(**DB_CONFIG) as connection, connection.cursor() as cursor:
        cursor.execute("""
            SELECT table_schema, table_name FROM information_schema.tables
            WHERE (table_schema='orchestration_v2')
               OR (table_schema='public' AND table_name LIKE 'sys_collection%')
        """)
        rows=set(cursor.fetchall())
    assert {
        ("orchestration_v2","acquisition_endpoint"),
        ("orchestration_v2","task_definition"),
        ("orchestration_v2","task_execution"),
        ("orchestration_v2","task_execution_event"),
        ("orchestration_v2","dataset_state"),
    } <= rows
    assert not {row for row in rows if row[0] == "public"}


def test_no_duplicate_active_v2_scope():
    with psycopg2.connect(**DB_CONFIG) as connection, connection.cursor() as cursor:
        cursor.execute("""
            SELECT count(*) FROM (
              SELECT task_key, observation_key
              FROM orchestration_v2.task_execution
              WHERE status IN (
                'created','queued','running','waiting_dependency','retrying',
                'validating','publishing'
              )
              GROUP BY task_key, observation_key HAVING count(*) > 1
            ) duplicates
        """)
        assert cursor.fetchone()[0] == 0


def test_coverage_queue_has_no_v1_foreign_key_or_column():
    with psycopg2.connect(**DB_CONFIG) as connection, connection.cursor() as cursor:
        cursor.execute("""
            SELECT count(*) FROM information_schema.columns
            WHERE table_schema='public'
              AND table_name='sys_data_coverage_job'
              AND column_name='collection_job_id'
        """)
        assert cursor.fetchone()[0] == 0


def test_quarterly_verified_empty_uses_period_end_partition_key():
    """A verified empty quarter must satisfy the next independent audit."""
    marker = "integration:verified-empty-quarter:1990-Q1"
    execution_id = None
    try:
        with psycopg2.connect(**DB_CONFIG) as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO orchestration_v2.task_execution (
                    task_definition_id, task_key, definition_version,
                    definition_digest, purpose, trigger_source, status,
                    idempotency_key, observation_key, observation_start,
                    observation_end, observation_period, scope_digest,
                    attempt_count, max_attempts, finished_at
                )
                SELECT task_definition_id, task_key, version,
                       definition_digest, 'repair', 'recovery', 'success',
                       %s, '1990-Q1', DATE '1990-01-01', DATE '1990-03-31',
                       '1990-Q1', repeat('0', 64), 1, 3, now()
                FROM orchestration_v2.task_definition
                WHERE task_key='income' AND lifecycle_status='active'
                RETURNING task_execution_id
                """,
                (marker,),
            )
            execution_id = cursor.fetchone()[0]
            cursor.execute(
                """
                INSERT INTO orchestration_v2.task_execution_event (
                    task_execution_id, sequence_number, event_type, node_key,
                    attempt_number, payload
                ) VALUES (%s, 1, 'node.validate.completed', 'validate', 1, '{}')
                RETURNING event_id
                """,
                (execution_id,),
            )
            validation_event_id = cursor.fetchone()[0]
            cursor.execute(
                """
                INSERT INTO orchestration_v2.dataset_state (
                    dataset_name, observation_key, observation_start,
                    observation_end, observation_period, scope_digest,
                    contract_version, expectation_status, data_status, ready,
                    expected_count, actual_count, source_execution_id,
                    validation_event_id, published_at
                ) VALUES (
                    'income', '1990-Q1', DATE '1990-01-01', DATE '1990-03-31',
                    '1990-Q1', repeat('0', 64), 'coverage-rule:4', 'expected',
                    'empty_verified', true, 1, 0, %s, %s, now()
                )
                """,
                (execution_id, validation_event_id),
            )

        partitions = CoverageRepository().actual_partitions(
            COVERAGE_RULES.get("income"),
            date(1990, 1, 1),
            date(1990, 3, 31),
        )
        assert [(item.partition_date, item.verified_empty) for item in partitions] == [
            (date(1990, 3, 31), True)
        ]
    finally:
        if execution_id is not None:
            with psycopg2.connect(**DB_CONFIG) as connection, connection.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM orchestration_v2.dataset_state "
                    "WHERE source_execution_id=%s",
                    (execution_id,),
                )
                # The production contract is intentionally append-only.  This
                # exact integration fixture is removed under a transaction-
                # scoped trigger disable so running the suite against a
                # non-ephemeral database cannot leave test evidence behind.
                cursor.execute(
                    "ALTER TABLE orchestration_v2.task_execution_event "
                    "DISABLE TRIGGER trg_orchestration_v2_execution_event_append_only"
                )
                cursor.execute(
                    "DELETE FROM orchestration_v2.task_execution_event "
                    "WHERE task_execution_id=%s",
                    (execution_id,),
                )
                cursor.execute(
                    "ALTER TABLE orchestration_v2.task_execution_event "
                    "ENABLE TRIGGER trg_orchestration_v2_execution_event_append_only"
                )
                cursor.execute(
                    "DELETE FROM orchestration_v2.task_execution "
                    "WHERE task_execution_id=%s",
                    (execution_id,),
                )
