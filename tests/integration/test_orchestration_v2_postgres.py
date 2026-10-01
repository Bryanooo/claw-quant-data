"""Read-only integration checks for the active V2 control plane."""

import os
from datetime import date

import psycopg2
import pytest

from service.config import DB_CONFIG
from service.orchestration_v2.repository import OrchestrationV2Repository


pytestmark = pytest.mark.skipif(
    os.getenv("RUN_DB_INTEGRATION") != "1",
    reason="set RUN_DB_INTEGRATION=1 to run PostgreSQL contract tests",
)


def test_orchestration_v2_has_exactly_the_five_control_tables():
    connection = psycopg2.connect(**DB_CONFIG)
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema='orchestration_v2'
                  AND table_type='BASE TABLE'
                ORDER BY table_name
                """
            )
            tables = {row[0] for row in cursor.fetchall()}
    finally:
        connection.close()

    assert tables == {
        "acquisition_endpoint",
        "dataset_state",
        "task_definition",
        "task_execution",
        "task_execution_event",
    }


def test_orchestration_v2_enforces_single_active_versions_and_append_only_events():
    connection = psycopg2.connect(**DB_CONFIG)
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT index_relation.relname,
                       pg_get_expr(index_meta.indpred, index_meta.indrelid)
                FROM pg_index AS index_meta
                JOIN pg_class AS index_relation
                  ON index_relation.oid=index_meta.indexrelid
                JOIN pg_namespace AS namespace
                  ON namespace.oid=index_relation.relnamespace
                WHERE namespace.nspname='orchestration_v2'
                  AND index_relation.relname IN (
                    'uq_orchestration_v2_endpoint_active',
                    'uq_orchestration_v2_task_definition_active'
                  )
                """
            )
            indexes = {name: definition for name, definition in cursor.fetchall()}
            cursor.execute(
                """
                SELECT event_object_table, trigger_name
                FROM information_schema.triggers
                WHERE trigger_schema='orchestration_v2'
                """
            )
            triggers = set(cursor.fetchall())
    finally:
        connection.close()

    assert set(indexes) == {
        "uq_orchestration_v2_endpoint_active",
        "uq_orchestration_v2_task_definition_active",
    }
    assert all(
        "lifecycle_status" in predicate and "active" in predicate
        for predicate in indexes.values()
    )
    assert (
        "task_execution_event",
        "trg_orchestration_v2_execution_event_append_only",
    ) in triggers


def test_orchestration_v2_read_model_handles_an_installed_control_plane():
    repository = OrchestrationV2Repository()

    summary = repository.control_plane_summary()

    assert summary["status"] == "installed"
    assert summary["missing_tables"] == []
    assert set(summary) == {
        "status",
        "missing_tables",
        "endpoints",
        "definitions",
            "executions",
            "dataset_states",
            "engine",
        }
    assert all(
        isinstance(summary[key], dict)
        for key in (
            "endpoints", "definitions", "executions", "dataset_states",
        )
    )
    definitions = repository.list_definitions(limit=51)
    assert len(definitions) <= 51
    assert all(
        {"task_definition_id", "task_key", "version", "lifecycle_status"}
        <= set(item)
        for item in definitions
    )
    executions = repository.list_executions(limit=51)
    assert len(executions) <= 51
    assert all(
        {"task_execution_id", "task_key", "purpose", "status"} <= set(item)
        for item in executions
    )
    dataset_states = repository.list_dataset_states(limit=51)
    assert len(dataset_states) <= 51
    assert all(
        {"dataset_state_id", "dataset_name", "data_status", "ready"}
        <= set(item)
        for item in dataset_states
    )


def test_today_delivery_is_definition_driven_before_dispatch():
    view = OrchestrationV2Repository().today_delivery(date(2099, 1, 2))

    assert view["engine"] == "orchestration_v2"
    assert view["summary"]["expected"] > 0
    assert view["summary"]["not_dispatched"] == view["summary"]["expected"]
