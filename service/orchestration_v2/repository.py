"""PostgreSQL persistence for the isolated V2 orchestration control plane."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from contextlib import contextmanager
from datetime import datetime, time, timedelta
import json
import secrets
from typing import Any

import psycopg2
import psycopg2.extras

from service.config import DB_CONFIG
from service.clock import business_now
from service.orchestration_v2.contracts import (
    AcquisitionEndpointContract,
    DatasetStateUpdate,
    ExecutionRequest,
    ExecutionStatus,
    NEXT_MORNING_TASK_RELEASE_TIME,
    NEXT_MORNING_TASKS,
    US_COMPLETED_SESSION_TASKS,
    TaskDefinitionDocument,
    canonical_digest,
)
from service.orchestration_v2.recovery_policy import (
    QUOTA_GUARDED_DATASETS,
    SERIALIZED_ACQUISITION_TASKS,
)


def _input_rule_versions(names):
    from service.data_coverage.registry import COVERAGE_RULES
    return json.dumps({r.dataset_name: r.revision for r in COVERAGE_RULES.list()
                       if r.dataset_name in names})


# Historical execution success is immutable. A consumer can reuse an older
# exact-day certificate only after the current rule independently confirms it.
_CURRENT_INPUT_CERTIFICATE = """(
    EXISTS (SELECT 1 FROM orchestration_v2.task_execution producer
        WHERE producer.task_execution_id=s.source_execution_id
          AND producer.status NOT IN ('cancelled','superseded')) AND (
    substring(s.contract_version from '^coverage-rule:([0-9]+)$')::int
        >= coalesce((%s::jsonb->>s.dataset_name)::int,1)
    OR (s.observation_start=s.observation_end AND s.scope='{}'::jsonb AND EXISTS (
        SELECT 1 FROM sys_data_coverage_partition p JOIN sys_data_coverage_audit a USING(audit_id)
        WHERE p.dataset_name=s.dataset_name AND p.partition_date=s.observation_end
          AND p.expected AND p.status='present' AND s.data_status='complete'
          AND (a.evidence->>'rule_revision')::int=(%s::jsonb->>s.dataset_name)::int))))"""


class OrchestrationV2Repository:
    """Small transactional repository; it does not activate the V2 engine."""

    _CONTROL_TABLES = frozenset({
        "acquisition_endpoint",
        "task_definition",
        "task_execution",
        "task_execution_event",
        "dataset_state",
    })

    def automation_states(self) -> dict[str, dict]:
        from service.orchestration_v2.automation_status import task_automation
        with self._connection() as connection, self._dict_cursor(connection) as cursor:
            cursor.execute("SELECT task_key,definition FROM orchestration_v2.task_definition WHERE lifecycle_status='active'")
            definitions = {row['task_key']: row['definition'] for row in cursor.fetchall()}
        return {key: {**task_automation(key, document, definitions.keys()),
                      'definition_status': 'active',
                      'schedule_mode': document['schedule']['mode']}
                for key, document in definitions.items()}

    def __init__(
        self,
        connection_factory: Callable[..., Any] = psycopg2.connect,
        connection_context: Callable[[], Any] | None = None,
    ):
        self._connection_factory = connection_factory
        # Optional zero-argument context manager yielding a pooled writable
        # connection.  When provided (the API process injects the shared
        # ThreadedConnectionPool here) every method reuses that pool instead
        # of opening one TCP connection per call; commit/rollback semantics
        # are identical because the context commits on success.
        self._connection_context = connection_context

    @contextmanager
    def _connection(self):
        if self._connection_context is not None:
            with self._connection_context() as connection:
                yield connection
            return
        connection = self._connection_factory(**DB_CONFIG)
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    @staticmethod
    def _dict_cursor(connection):
        return connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    @staticmethod
    def _first_daily_schedule_at(
        expression: str | None,
        observation_date,
        *,
        tzinfo,
    ) -> datetime | None:
        """Resolve the first fixed-time occurrence from a daily cron.

        V2-generated daily definitions use explicit minute/hour lists.  If a
        future hand-authored definition uses a dynamic cron token, returning
        ``None`` deliberately avoids hiding work as not due.
        """

        fields = (expression or "").split()
        if len(fields) != 5:
            return None
        try:
            minutes = [int(value) for value in fields[0].split(",")]
            hours = [int(value) for value in fields[1].split(",")]
        except ValueError:
            return None
        candidates = [
            datetime.combine(
                observation_date,
                time(hour=hour, minute=minute),
                tzinfo=tzinfo,
            )
            for hour in hours
            for minute in minutes
            if 0 <= hour <= 23 and 0 <= minute <= 59
        ]
        return min(candidates) if candidates else None

    @staticmethod
    def _lock_version_key(cursor, namespace: int, key: str) -> None:
        cursor.execute("SELECT pg_advisory_xact_lock(%s, hashtext(%s))", (namespace, key))

    def installation_status(self) -> dict:
        """Report a complete, absent or interrupted control-plane migration."""

        with self._connection() as connection, connection.cursor() as cursor:
            cursor.execute("SELECT to_regnamespace('orchestration_v2') IS NOT NULL")
            if not bool(cursor.fetchone()[0]):
                return {
                    "status": "not_installed",
                    "missing_tables": sorted(self._CONTROL_TABLES),
                }
            cursor.execute(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema='orchestration_v2'
                  AND table_type='BASE TABLE'
                """
            )
            present = {row[0] for row in cursor.fetchall()}
        missing = sorted(self._CONTROL_TABLES - present)
        return {
            "status": "partial" if missing else "installed",
            "missing_tables": missing,
        }

    def schema_exists(self) -> bool:
        return self.installation_status()["status"] == "installed"

    def control_plane_summary(self) -> dict:
        installation = self.installation_status()
        if installation["status"] != "installed":
            return {
                **installation,
                "endpoints": {},
                "definitions": {},
                "executions": {},
                "current_executions": {},
                "current_active_tasks": {},
                "dataset_states": {},
            }
        with self._connection() as connection, self._dict_cursor(connection) as cursor:
            cursor.execute(
                """
                WITH latest AS (
                    SELECT DISTINCT ON (source_id, endpoint_key)
                           lifecycle_status
                    FROM orchestration_v2.acquisition_endpoint
                    ORDER BY source_id, endpoint_key, version DESC
                )
                SELECT lifecycle_status AS key, count(*)::INTEGER AS value
                FROM latest GROUP BY lifecycle_status
                """
            )
            endpoints = {row["key"]: row["value"] for row in cursor.fetchall()}
            cursor.execute(
                """
                WITH latest AS (
                    SELECT DISTINCT ON (task_key)
                           workflow_kind, lifecycle_status
                    FROM orchestration_v2.task_definition
                    ORDER BY task_key, version DESC
                )
                SELECT workflow_kind || ':' || lifecycle_status AS key,
                       count(*)::INTEGER AS value
                FROM latest
                GROUP BY workflow_kind, lifecycle_status
                """
            )
            definitions = {row["key"]: row["value"] for row in cursor.fetchall()}
            cursor.execute(
                """
                SELECT status AS key, count(*)::INTEGER AS value
                FROM orchestration_v2.task_execution GROUP BY status
                """
            )
            executions = {row["key"]: row["value"] for row in cursor.fetchall()}
            # ``executions`` is the immutable ledger distribution.  It is
            # useful for audits, but it must not be presented as the number of
            # currently open problems: repeated repair attempts for the same
            # logical task/date would otherwise inflate one incident into many
            # alerts.  This projection keeps only the newest attempt for every
            # logical scope and is the correct source for operational health.
            cursor.execute(
                """
                WITH latest AS (
                    SELECT DISTINCT ON (task_key, observation_key)
                           status
                    FROM orchestration_v2.task_execution
                    ORDER BY task_key, observation_key,
                             task_execution_id DESC
                )
                SELECT status AS key, count(*)::INTEGER AS value
                FROM latest GROUP BY status
                """
            )
            current_executions = {
                row["key"]: row["value"] for row in cursor.fetchall()
            }
            cursor.execute(
                """
                WITH latest AS (
                    SELECT DISTINCT ON (task_key, observation_key)
                           task_key, status
                    FROM orchestration_v2.task_execution
                    ORDER BY task_key, observation_key,
                             task_execution_id DESC
                )
                SELECT task_key AS key, count(*)::INTEGER AS value
                FROM latest
                WHERE status IN (
                    'created','queued','running','waiting_dependency',
                    'retrying','validating','publishing'
                )
                GROUP BY task_key
                """
            )
            current_active_tasks = {
                row["key"]: row["value"] for row in cursor.fetchall()
            }
            cursor.execute(
                """
                SELECT data_status || CASE WHEN ready THEN ':ready' ELSE ':not_ready' END AS key,
                       count(*)::INTEGER AS value
                FROM orchestration_v2.dataset_state
                GROUP BY data_status, ready
                """
            )
            dataset_states = {row["key"]: row["value"] for row in cursor.fetchall()}
        return {
            "status": "installed",
            "missing_tables": [],
            "endpoints": endpoints,
            "definitions": definitions,
            "executions": executions,
            "current_executions": current_executions,
            "current_active_tasks": current_active_tasks,
            "dataset_states": dataset_states,
            "engine": "orchestration_v2",
        }

    def list_definitions(
        self,
        *,
        limit: int = 50,
        before_id: int | None = None,
        lifecycle_status: str | None = None,
        workflow_kind: str | None = None,
        cadence: str | None = None,
    ) -> list[dict]:
        if not self.schema_exists():
            return []
        conditions: list[str] = []
        params: list[Any] = []
        if before_id is not None:
            conditions.append("task_definition_id < %s")
            params.append(before_id)
        if lifecycle_status is not None:
            conditions.append("lifecycle_status = %s")
            params.append(lifecycle_status)
        if workflow_kind is not None:
            conditions.append("workflow_kind = %s")
            params.append(workflow_kind)
        if cadence is not None:
            conditions.append("definition->'scope_contract'->>'cadence' = %s")
            params.append(cadence)
        where = " WHERE " + " AND ".join(conditions) if conditions else ""
        params.append(limit)
        with self._connection() as connection, self._dict_cursor(connection) as cursor:
            cursor.execute(
                """
                SELECT task_definition_id, task_key, version, lifecycle_status,
                       workflow_kind, definition_digest, app_revision, image_digest,
                       definition->'input_datasets' AS input_datasets,
                       definition->'output_datasets' AS output_datasets,
                       ARRAY(
                         SELECT DISTINCT endpoint.source_id
                         FROM orchestration_v2.acquisition_endpoint endpoint
                         WHERE endpoint.acquisition_endpoint_id IN (
                           SELECT value::bigint FROM jsonb_array_elements_text(
                             COALESCE(task_definition.definition->'acquisition_endpoint_ids','[]'::jsonb)
                           )
                         ) ORDER BY endpoint.source_id
                       ) AS source_ids,
                       definition->'scope_contract'->>'cadence' AS cadence,
                       definition->'schedule'->>'mode' AS schedule_mode,
                       definition->'schedule'->>'expression' AS schedule_expression,
                       jsonb_array_length(definition->'nodes') AS node_count,
                       created_by, activated_by, created_at, activated_at, retired_at
                FROM orchestration_v2.task_definition
                """ + where + " ORDER BY task_definition_id DESC LIMIT %s",
                tuple(params),
            )
            return [dict(row) for row in cursor.fetchall()]

    def execution_output_states(self, execution_ids: list[int]) -> list[dict]:
        """Read published evidence for the bounded execution list, not whole history."""
        if not execution_ids:
            return []
        with self._connection() as connection, self._dict_cursor(connection) as cursor:
            cursor.execute(
                """
                SELECT DISTINCT ON (source_execution_id,dataset_name,observation_key)
                       source_execution_id,dataset_name,observation_key,
                       observation_start,observation_end,data_status,ready,
                       validation_event_id,published_at
                FROM orchestration_v2.dataset_state
                WHERE source_execution_id=ANY(%s)
                ORDER BY source_execution_id,dataset_name,observation_key,revision DESC
                LIMIT 201
                """, (execution_ids,),
            )
            return [dict(row) for row in cursor.fetchall()]

    def count_executions(
        self,
        *,
        status: str | None = None,
        task_key: str | None = None,
    ) -> int:
        """Count the immutable execution ledger for operator pagination."""
        if not self.schema_exists():
            return 0
        conditions: list[str] = []
        params: list[Any] = []
        if status is not None:
            conditions.append("status = %s")
            params.append(status)
        if task_key is not None:
            conditions.append("task_key = %s")
            params.append(task_key)
        where = " WHERE " + " AND ".join(conditions) if conditions else ""
        with self._connection() as connection, self._dict_cursor(connection) as cursor:
            cursor.execute(
                "SELECT count(*)::BIGINT AS total "
                "FROM orchestration_v2.task_execution" + where,
                tuple(params),
            )
            return int(cursor.fetchone()["total"])

    def list_executions(
        self,
        *,
        limit: int = 50,
        before_id: int | None = None,
        status: str | None = None,
        task_key: str | None = None,
    ) -> list[dict]:
        if not self.schema_exists():
            return []
        conditions: list[str] = []
        params: list[Any] = []
        if before_id is not None:
            conditions.append("task_execution_id < %s")
            params.append(before_id)
        if status is not None:
            conditions.append("status = %s")
            params.append(status)
        if task_key is not None:
            conditions.append("task_key = %s")
            params.append(task_key)
        where = " WHERE " + " AND ".join(conditions) if conditions else ""
        params.append(limit)
        with self._connection() as connection, self._dict_cursor(connection) as cursor:
            cursor.execute(
                """
                SELECT execution.task_execution_id, execution.task_definition_id,
                       execution.task_key,
                       definition_version, purpose, trigger_source, status,
                       observation_key, observation_start, observation_end,
                       publication_date, data_available_at, collected_at,
                       current_node_key, node_status, priority, resource_class,
                       attempt_count, max_attempts, eligible_at, lease_owner,
                       lease_expires_at, final_error_category, final_error_message,
                       created_at, started_at, finished_at, updated_at,
                       COALESCE(acquire.rows_fetched, 0) AS rows_fetched,
                       COALESCE(acquire.rows_written, 0) AS rows_written,
                       NOT EXISTS (
                           SELECT 1
                           FROM orchestration_v2.task_execution AS newer
                           WHERE newer.task_key=execution.task_key
                             AND newer.observation_key=execution.observation_key
                             AND newer.task_execution_id>
                                 execution.task_execution_id
                       ) AS is_current_scope_execution,
                       (
                           SELECT max(newer.task_execution_id)
                           FROM orchestration_v2.task_execution AS newer
                           WHERE newer.task_key=execution.task_key
                             AND newer.observation_key=execution.observation_key
                       ) AS latest_scope_execution_id
                FROM orchestration_v2.task_execution AS execution
                LEFT JOIN LATERAL (
                    SELECT COALESCE((payload->>'rows_fetched')::bigint, 0)
                               AS rows_fetched,
                           COALESCE((payload->>'rows_inserted')::bigint, 0)
                               AS rows_written
                    FROM orchestration_v2.task_execution_event
                    WHERE task_execution_id=execution.task_execution_id
                      AND event_type='node.acquire.completed'
                    ORDER BY sequence_number DESC
                    LIMIT 1
                ) AS acquire ON true
                """ + where + " ORDER BY task_execution_id DESC LIMIT %s",
                tuple(params),
            )
            return [dict(row) for row in cursor.fetchall()]

    def list_execution_events(
        self,
        execution_id: int,
        *,
        limit: int = 200,
    ) -> list[dict]:
        if not self.schema_exists():
            return []
        if limit < 1 or limit > 1000:
            raise ValueError("limit must be between 1 and 1000")
        with self._connection() as connection, self._dict_cursor(connection) as cursor:
            cursor.execute(
                """
                SELECT event_id, task_execution_id, sequence_number, event_type,
                       node_key, attempt_number, payload, evidence_references,
                       occurred_at
                FROM orchestration_v2.task_execution_event
                WHERE task_execution_id=%s
                ORDER BY sequence_number
                LIMIT %s
                """,
                (execution_id, limit),
            )
            return [dict(row) for row in cursor.fetchall()]

    def list_verified_acquisition_evidence(
        self,
        execution_id: int,
    ) -> list[dict]:
        """Return every durable completed request partition for one execution.

        This deliberately does not reuse the UI event-list limit.  A single
        V2 acquire node may legitimately exhaust thousands of internal symbol
        partitions, and losing request keys after the first 1,000 makes a
        restarted worker replay already verified provider calls.
        """

        if not self.schema_exists():
            return []
        with self._connection() as connection, self._dict_cursor(connection) as cursor:
            cursor.execute(
                """
                SELECT DISTINCT ON (
                           COALESCE(payload->>'request_key', event_id::TEXT)
                       ) payload
                FROM orchestration_v2.task_execution_event
                WHERE task_execution_id=%s
                  AND event_type='node.acquire.request_completed'
                  AND sequence_number > COALESCE((
                      SELECT MAX(reset_event.sequence_number)
                      FROM orchestration_v2.task_execution_event AS reset_event
                      WHERE reset_event.task_execution_id=%s
                        AND reset_event.event_type='execution.operator_retry'
                        AND COALESCE(
                              (reset_event.payload->>'reset_data_nodes')::BOOLEAN,
                              false
                            )
                  ), 0)
                ORDER BY COALESCE(payload->>'request_key', event_id::TEXT),
                         sequence_number DESC
                """,
                (execution_id, execution_id),
            )
            from service.data_coverage.transport import request_verified
            return [dict(row["payload"]) for row in cursor.fetchall()
                    if request_verified(row["payload"] or {})]

    def list_dataset_states(
        self,
        *,
        limit: int = 50,
        before_id: int | None = None,
        data_status: str | None = None,
        dataset_name: str | None = None,
    ) -> list[dict]:
        if not self.schema_exists():
            return []
        conditions: list[str] = []
        params: list[Any] = []
        if before_id is not None:
            conditions.append("dataset_state_id < %s")
            params.append(before_id)
        if data_status is not None:
            conditions.append("data_status = %s")
            params.append(data_status)
        if dataset_name is not None:
            conditions.append("dataset_name = %s")
            params.append(dataset_name)
        where = " WHERE " + " AND ".join(conditions) if conditions else ""
        params.append(limit)
        with self._connection() as connection, self._dict_cursor(connection) as cursor:
            cursor.execute(
                """
                SELECT dataset_state_id, dataset_name, observation_key,
                       observation_start, observation_end, observation_period,
                       publication_date, available_at, collected_at,
                       contract_version, expectation_status, data_status, ready,
                       expected_count, actual_count, gap_summary,
                       validation_summary, source_execution_id,
                       validation_event_id, revision, published_at, updated_at
                FROM orchestration_v2.dataset_state
                """ + where + " ORDER BY dataset_state_id DESC LIMIT %s",
                tuple(params),
            )
            return [dict(row) for row in cursor.fetchall()]

    def latest_dataset_states(self) -> dict[str, dict]:
        """Return the newest published/expected state for every dataset.

        Data freshness must follow V2's validated logical observation, not
        merely the newest physical row in a table.  This bounded projection is
        intentionally separate from the paginated operator API.
        """
        if not self.schema_exists():
            return {}
        with self._connection() as connection, self._dict_cursor(connection) as cursor:
            cursor.execute(
                """
                SELECT DISTINCT ON (dataset_name)
                       dataset_state_id, dataset_name, observation_key,
                       observation_start, observation_end, observation_period,
                       expectation_status, data_status, ready, actual_count,
                       validation_summary, source_execution_id,
                       published_at, updated_at
                FROM orchestration_v2.dataset_state
                ORDER BY dataset_name,
                         observation_end DESC NULLS LAST,
                         observation_start DESC NULLS LAST,
                         updated_at DESC,
                         dataset_state_id DESC
                """
            )
            return {
                row["dataset_name"]: dict(row)
                for row in cursor.fetchall()
            }

    def latest_execution_states(self) -> dict[str, dict]:
        """Return the newest non-superseded execution for every task key.

        Read-only projection for the dashboard interface inventory: a task
        whose latest attempt still stands (success, attention, queued, ...)
        maps to that row.  Superseded rows are skipped so a replaced attempt
        is never mistaken for the current state of a task.
        """
        if not self.schema_exists():
            return {}
        with self._connection() as connection, self._dict_cursor(connection) as cursor:
            cursor.execute(
                """
                SELECT DISTINCT ON (task_key)
                       task_key, task_execution_id, status, current_node_key,
                       purpose, observation_start, observation_end,
                       attempt_count, final_error_category, updated_at
                FROM orchestration_v2.task_execution
                WHERE status <> 'superseded'
                ORDER BY task_key, task_execution_id DESC
                """
            )
            return {
                row["task_key"]: dict(row)
                for row in cursor.fetchall()
            }

    def ready_input_states(
        self,
        dataset_names: tuple[str, ...],
        observation_key: str,
    ) -> dict[str, dict]:
        """Return the latest ready state for every exact dependency scope."""

        if not dataset_names:
            return {}
        versions = _input_rule_versions(dataset_names)
        with self._connection() as connection, self._dict_cursor(connection) as cursor:
            cursor.execute(
                """
                SELECT * FROM (
                    SELECT DISTINCT ON (dataset_name)
                           dataset_state_id, dataset_name, observation_key,
                           observation_start, observation_end, revision,
                           source_execution_id, published_at,
                           (ready AND """ + _CURRENT_INPUT_CERTIFICATE + """) AS ready
                    FROM orchestration_v2.dataset_state s
                    WHERE dataset_name = ANY(%s) AND observation_key=%s
                    ORDER BY dataset_name, revision DESC,
                             updated_at DESC, dataset_state_id DESC
                ) latest WHERE ready
                """,
                (versions, versions, list(dataset_names), observation_key),
            )
            return {row["dataset_name"]: dict(row) for row in cursor.fetchall()}

    def latest_common_ready_input_states(
        self,
        dataset_names: tuple[str, ...],
    ) -> dict[str, dict]:
        """Find the newest logical period certified ready for all inputs."""

        if not dataset_names:
            return {}
        versions = _input_rule_versions(dataset_names)
        with self._connection() as connection, self._dict_cursor(connection) as cursor:
            cursor.execute(
                """
                WITH latest AS (
                    SELECT DISTINCT ON (dataset_name, observation_key)
                           dataset_state_id, dataset_name, observation_key,
                           observation_start, observation_end, revision,
                           source_execution_id, published_at, (ready AND """ + _CURRENT_INPUT_CERTIFICATE + """) AS ready
                    FROM orchestration_v2.dataset_state s
                    WHERE dataset_name = ANY(%s)
                    ORDER BY dataset_name, observation_key,
                             revision DESC, updated_at DESC,
                             dataset_state_id DESC
                ), common_scope AS (
                    SELECT observation_key, max(observation_end) AS observation_end
                    FROM latest
                    WHERE ready
                    GROUP BY observation_key
                    HAVING count(DISTINCT dataset_name)=%s
                    ORDER BY max(observation_end) DESC NULLS LAST,
                             observation_key DESC
                    LIMIT 1
                )
                SELECT latest.*
                FROM latest
                JOIN common_scope USING (observation_key)
                WHERE latest.ready
                ORDER BY latest.dataset_name
                """,
                (versions, versions, list(dataset_names), len(dataset_names)),
            )
            return {row["dataset_name"]: dict(row) for row in cursor.fetchall()}

    def auxiliary_input_revision(self, dataset_names: tuple[str, ...], observation_end) -> dict:
        """Track non-daily inputs without pretending their periods match bars.

        Coalesce a batch of financial repairs into one recomputation after the
        relevant writers drain. Readiness remains the output auditor's decision.
        """
        with self._connection() as connection, self._dict_cursor(connection) as cursor:
            cursor.execute("""
                SELECT md5(COALESCE(string_agg(
                    dataset_state_id::text || ':' || revision::text || ':' || ready::text,
                    ',' ORDER BY dataset_state_id), '')) AS revision_digest
                FROM orchestration_v2.dataset_state
                WHERE dataset_name=ANY(%s)
                  AND (observation_start IS NULL OR observation_start<=%s)
            """, (list(dataset_names), observation_end))
            result = dict(cursor.fetchone())
            cursor.execute("""
                SELECT count(*) AS pending_count
                FROM orchestration_v2.task_execution AS execution
                JOIN orchestration_v2.task_definition AS definition
                    USING (task_definition_id)
                WHERE definition.definition->'output_datasets' ?| %s
                  AND execution.status IN
                      ('created','queued','running','validating','publishing',
                       'waiting_dependency','retrying')
                  AND (execution.observation_start IS NULL OR execution.observation_start<=%s)
            """, (list(dataset_names), observation_end))
            result.update(dict(cursor.fetchone()))
            return result

    def today_delivery(self, observation_date) -> dict:
        """Return today's due V2 tasks and their validated data state."""
        with self._connection() as connection, self._dict_cursor(connection) as cursor:
            cursor.execute(
                """
                WITH active AS (
                    SELECT DISTINCT ON (task_key)
                           task_key, definition
                    FROM orchestration_v2.task_definition
                    WHERE lifecycle_status='active' AND workflow_kind='acquisition'
                      AND definition->'scope_contract'->>'cadence'='daily'
                      AND definition->'schedule'->>'mode'='cron'
                    ORDER BY task_key, version DESC
                ), task_output AS (
                    SELECT active.task_key,
                           jsonb_array_elements_text(
                               active.definition->'output_datasets'
                           ) AS dataset_name
                    FROM active
                ), latest_execution AS (
                    SELECT DISTINCT ON (task_key)
                           task_execution_id, task_key, observation_key, status,
                           current_node_key, attempt_count AS attempt,
                           max_attempts,
                           final_error_category AS failure_category,
                           final_error_message AS error_message,
                           created_at, started_at, finished_at
                    FROM orchestration_v2.task_execution
                    WHERE observation_start=%s AND observation_end=%s
                      AND purpose='daily' AND trigger_source='schedule'
                    ORDER BY task_key, task_execution_id DESC
                ), latest_acquire AS (
                    SELECT DISTINCT ON (task_execution_id)
                           task_execution_id,
                           COALESCE((payload->>'rows_fetched')::bigint, 0)
                               AS rows_fetched,
                           COALESCE((payload->>'rows_inserted')::bigint, 0)
                               AS rows_written
                    FROM orchestration_v2.task_execution_event
                    WHERE event_type='node.acquire.completed'
                    ORDER BY task_execution_id, sequence_number DESC
                ), latest_state AS (
                    SELECT DISTINCT ON (dataset_name)
                           dataset_name, data_status, ready,
                           source_execution_id, updated_at
                    FROM orchestration_v2.dataset_state
                    WHERE observation_start=%s AND observation_end=%s
                    ORDER BY dataset_name, updated_at DESC, dataset_state_id DESC
                ), state_rollup AS (
                    SELECT output.task_key,
                           count(*)::integer AS datasets,
                           array_agg(
                             output.dataset_name ORDER BY output.dataset_name
                           ) AS output_datasets,
                           count(*) FILTER (WHERE state.ready)::integer
                               AS ready_datasets,
                           count(*) FILTER (
                             WHERE state.data_status IN (
                               'gaps','partial','indeterminate'
                             )
                           )::integer AS problem_datasets
                    FROM task_output AS output
                    LEFT JOIN latest_state AS state USING (dataset_name)
                    GROUP BY output.task_key
                )
                SELECT active.task_key,
                       active.definition->'schedule'->>'expression'
                           AS schedule_expression,
                       execution.task_execution_id, execution.observation_key,
                       COALESCE(execution.status, 'not_dispatched') AS status,
                       execution.current_node_key, execution.attempt,
                       execution.max_attempts, execution.failure_category,
                       execution.error_message,
                       COALESCE(acquire.rows_fetched, 0) AS rows_fetched,
                       COALESCE(acquire.rows_written, 0) AS rows_written,
                       execution.created_at,
                       execution.started_at, execution.finished_at,
                       COALESCE(state.datasets, 0) AS datasets,
                       COALESCE(state.output_datasets, ARRAY[]::text[])
                           AS output_datasets,
                       COALESCE(state.ready_datasets, 0) AS ready_datasets,
                       COALESCE(state.problem_datasets, 0) AS problem_datasets
                FROM active
                LEFT JOIN latest_execution AS execution USING (task_key)
                LEFT JOIN latest_acquire AS acquire
                  ON acquire.task_execution_id=execution.task_execution_id
                LEFT JOIN state_rollup AS state
                  ON state.task_key=active.task_key
                ORDER BY active.task_key
                """,
                (
                    observation_date, observation_date,
                    observation_date, observation_date,
                ),
            )
            items = [dict(row) for row in cursor.fetchall()]
            cursor.execute(
                """
                SELECT COALESCE((
                    SELECT is_open=1 FROM trade_cal
                    WHERE exchange='SSE' AND cal_date=%s LIMIT 1
                ), false) AS trade_day
                """,
                (observation_date,),
            )
            trade_day = bool(cursor.fetchone()["trade_day"])
            cursor.execute(
                """
                SELECT cal_date
                FROM tushare_norm_us_tradecal
                WHERE is_open=1 AND cal_date<%s
                ORDER BY cal_date DESC LIMIT 1
                """,
                (observation_date,),
            )
            us_row = cursor.fetchone()
            us_completed_session = us_row["cal_date"] if us_row else None
        now = business_now()
        for item in items:
            next_morning_release = datetime.combine(
                observation_date + timedelta(days=1),
                NEXT_MORNING_TASK_RELEASE_TIME,
                tzinfo=now.tzinfo,
            )
            first_schedule = self._first_daily_schedule_at(
                item.get("schedule_expression"),
                observation_date,
                tzinfo=now.tzinfo,
            )
            if item["status"] == "not_dispatched":
                due_at = (
                    next_morning_release
                    if item["task_key"] in NEXT_MORNING_TASKS
                    else first_schedule
                )
                if (
                    item["task_key"] in US_COMPLETED_SESSION_TASKS
                    and us_completed_session != observation_date
                ):
                    item["status"] = "not_due"
                    item["not_due_reason"] = "different_market_calendar"
                    item["expected_observation_date"] = us_completed_session
                elif not trade_day:
                    item["status"] = "not_due"
                    item["not_due_reason"] = "non_trading_day"
                elif observation_date > now.date() or (
                    due_at is not None and now < due_at
                ):
                    item["status"] = "not_due"
                    item["not_due_reason"] = "schedule_pending"
            item["execution_status"] = item["status"]
            data_ready = (
                item["datasets"] > 0
                and item["datasets"] == item["ready_datasets"]
                and item["problem_datasets"] == 0
            )
            if data_ready:
                item["delivery_status"] = (
                    "ready"
                    if item["execution_status"] == "success"
                    else "ready_after_repair"
                )
            elif item["execution_status"] in {"not_due", "not_dispatched"}:
                item["delivery_status"] = item["execution_status"]
            elif item["execution_status"] in {
                "created", "queued", "running", "waiting_dependency",
                "retrying", "validating", "publishing",
            }:
                item["delivery_status"] = "active"
            else:
                item["delivery_status"] = "attention"
        not_due = sum(item["status"] == "not_due" for item in items)
        strictly_ready = sum(
            item["delivery_status"] in {"ready", "ready_after_repair"}
            for item in items
        )
        configured_daily_tasks = len(items)
        if not trade_day:
            # Task definitions describe what *could* run on a trading day;
            # they are not execution instances.  Returning one synthetic row
            # per definition on a closed market day made the console look as
            # if hundreds of jobs had been created.  Keep the capacity count
            # in summary metadata and expose no due/instance rows.
            items = []
            not_due = 0
            strictly_ready = 0
        return {
            "engine": "orchestration_v2",
            "data_date": observation_date,
            "trade_day": trade_day,
            "summary": {
                "configured_daily_tasks": configured_daily_tasks,
                "planned": len(items),
                "expected": len(items) - not_due,
                "success": sum(item["status"] == "success" for item in items),
                "active": sum(item["status"] in {
                    "created", "queued", "running", "waiting_dependency",
                    "retrying", "validating", "publishing",
                } and item["delivery_status"] != "ready_after_repair"
                    for item in items),
                "attention": sum(
                    item["delivery_status"] == "attention" for item in items
                ),
                "execution_attention": sum(
                    item["execution_status"] == "attention" for item in items
                ),
                "recovered": sum(
                    item["delivery_status"] == "ready_after_repair"
                    for item in items
                ),
                "not_dispatched": sum(item["status"] == "not_dispatched" for item in items),
                "not_due": not_due,
                "strictly_ready": strictly_ready,
            },
            "items": items,
        }

    def data_calendar(self, start_date, end_date) -> list[dict]:
        """Aggregate published V2 dataset state by data date, never run date."""
        with self._connection() as connection, self._dict_cursor(connection) as cursor:
            cursor.execute(
                """
                SELECT observation_start AS data_date,
                       count(*)::integer AS dataset_states,
                       count(*) FILTER (WHERE ready)::integer AS ready,
                       count(*) FILTER (WHERE data_status='complete')::integer AS complete,
                       count(*) FILTER (WHERE data_status='empty_verified')::integer AS empty_verified,
                       count(*) FILTER (
                         WHERE data_status IN ('gaps','partial','indeterminate')
                       )::integer AS problems,
                       count(*) FILTER (WHERE data_status IN ('pending','auditing'))::integer AS active
                FROM orchestration_v2.dataset_state
                WHERE observation_start=observation_end
                  AND observation_start BETWEEN %s AND %s
                GROUP BY observation_start
                ORDER BY observation_start
                """,
                (start_date, end_date),
            )
            return [dict(row) for row in cursor.fetchall()]

    def create_endpoint_draft(
        self,
        contract: AcquisitionEndpointContract,
        *,
        actor: str,
    ) -> dict:
        stored = contract.model_dump(mode="json")
        with self._connection() as connection, self._dict_cursor(connection) as cursor:
            lock_key = f"{contract.source_id}:{contract.endpoint_key}"
            self._lock_version_key(cursor, 2_026_067_001, lock_key)
            cursor.execute(
                """
                SELECT acquisition_endpoint_id, version
                FROM orchestration_v2.acquisition_endpoint
                WHERE source_id=%s AND endpoint_key=%s
                ORDER BY version DESC LIMIT 1
                """,
                (contract.source_id, contract.endpoint_key),
            )
            latest = cursor.fetchone()
            version = int(latest["version"]) + 1 if latest else 1
            cursor.execute(
                """
                INSERT INTO orchestration_v2.acquisition_endpoint(
                    source_id, endpoint_key, version, lifecycle_status,
                    acquisition_mode, handler_key, credential_ref,
                    request_contract, response_contract, pagination_policy,
                    rate_limit_policy, completeness_policy, contract_digest,
                    parent_endpoint_id, created_by
                ) VALUES (
                    %s,%s,%s,'draft',%s,%s,%s,%s::jsonb,%s::jsonb,%s::jsonb,
                    %s::jsonb,%s::jsonb,%s,%s,%s
                ) RETURNING *
                """,
                (
                    contract.source_id,
                    contract.endpoint_key,
                    version,
                    contract.acquisition_mode,
                    contract.handler_key,
                    contract.credential_ref,
                    json.dumps(contract.request_contract, ensure_ascii=False),
                    json.dumps(contract.response_contract, ensure_ascii=False),
                    json.dumps(contract.pagination_policy, ensure_ascii=False),
                    json.dumps(contract.rate_limit_policy, ensure_ascii=False),
                    json.dumps(contract.completeness_policy, ensure_ascii=False),
                    canonical_digest(stored),
                    latest["acquisition_endpoint_id"] if latest else None,
                    actor,
                ),
            )
            return dict(cursor.fetchone())

    def get_endpoint(self, endpoint_id: int) -> dict | None:
        with self._connection() as connection, self._dict_cursor(connection) as cursor:
            cursor.execute(
                """
                SELECT * FROM orchestration_v2.acquisition_endpoint
                WHERE acquisition_endpoint_id=%s
                """,
                (endpoint_id,),
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def find_endpoint_contract(
        self,
        source_id: str,
        endpoint_key: str,
        contract_digest: str,
    ) -> dict | None:
        with self._connection() as connection, self._dict_cursor(connection) as cursor:
            cursor.execute(
                """
                SELECT * FROM orchestration_v2.acquisition_endpoint
                WHERE source_id=%s AND endpoint_key=%s AND contract_digest=%s
                  AND lifecycle_status IN ('draft','active')
                ORDER BY (lifecycle_status='active') DESC, version DESC
                LIMIT 1
                """,
                (source_id, endpoint_key, contract_digest),
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def publish_endpoint(self, endpoint_id: int, *, actor: str) -> dict:
        with self._connection() as connection, self._dict_cursor(connection) as cursor:
            cursor.execute(
                """
                SELECT * FROM orchestration_v2.acquisition_endpoint
                WHERE acquisition_endpoint_id=%s FOR UPDATE
                """,
                (endpoint_id,),
            )
            candidate = cursor.fetchone()
            if not candidate:
                raise LookupError(f"endpoint draft not found: {endpoint_id}")
            if candidate["lifecycle_status"] != "draft":
                raise ValueError("only a draft endpoint can be published")
            lock_key = f"{candidate['source_id']}:{candidate['endpoint_key']}"
            self._lock_version_key(cursor, 2_026_067_001, lock_key)
            cursor.execute(
                """
                UPDATE orchestration_v2.acquisition_endpoint
                SET lifecycle_status='retired', retired_at=NOW(), updated_at=NOW()
                WHERE source_id=%s AND endpoint_key=%s
                  AND lifecycle_status='active'
                """,
                (candidate["source_id"], candidate["endpoint_key"]),
            )
            cursor.execute(
                """
                UPDATE orchestration_v2.acquisition_endpoint
                SET lifecycle_status='active', activated_by=%s,
                    activated_at=NOW(), updated_at=NOW()
                WHERE acquisition_endpoint_id=%s AND lifecycle_status='draft'
                RETURNING *
                """,
                (actor, endpoint_id),
            )
            return dict(cursor.fetchone())

    def create_definition_draft(
        self,
        document: TaskDefinitionDocument,
        *,
        actor: str,
    ) -> dict:
        stored = document.model_dump(mode="json")
        with self._connection() as connection, self._dict_cursor(connection) as cursor:
            self._lock_version_key(cursor, 2_026_067_002, document.task_key)
            cursor.execute(
                """
                SELECT task_definition_id, version
                FROM orchestration_v2.task_definition
                WHERE task_key=%s ORDER BY version DESC LIMIT 1
                """,
                (document.task_key,),
            )
            latest = cursor.fetchone()
            version = int(latest["version"]) + 1 if latest else 1
            cursor.execute(
                """
                INSERT INTO orchestration_v2.task_definition(
                    task_key, version, lifecycle_status, workflow_kind,
                    definition_schema_version, definition, definition_digest,
                    parent_definition_id, created_by
                ) VALUES (%s,%s,'draft',%s,%s,%s::jsonb,%s,%s,%s)
                RETURNING *
                """,
                (
                    document.task_key,
                    version,
                    document.workflow_kind,
                    document.schema_version,
                    json.dumps(stored, ensure_ascii=False),
                    canonical_digest(stored),
                    latest["task_definition_id"] if latest else None,
                    actor,
                ),
            )
            return dict(cursor.fetchone())

    def get_definition(self, definition_id: int) -> dict | None:
        with self._connection() as connection, self._dict_cursor(connection) as cursor:
            cursor.execute(
                """
                SELECT * FROM orchestration_v2.task_definition
                WHERE task_definition_id=%s
                """,
                (definition_id,),
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_active_definition(self, task_key: str) -> dict | None:
        with self._connection() as connection, self._dict_cursor(connection) as cursor:
            cursor.execute(
                """
                SELECT * FROM orchestration_v2.task_definition
                WHERE task_key=%s AND lifecycle_status='active'
                """,
                (task_key,),
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def find_definition_contract(
        self,
        task_key: str,
        definition_digest: str,
    ) -> dict | None:
        with self._connection() as connection, self._dict_cursor(connection) as cursor:
            cursor.execute(
                """
                SELECT * FROM orchestration_v2.task_definition
                WHERE task_key=%s AND definition_digest=%s
                  AND lifecycle_status IN ('draft','active')
                ORDER BY (lifecycle_status='active') DESC, version DESC
                LIMIT 1
                """,
                (task_key, definition_digest),
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def active_dependency_graph(self) -> dict[str, tuple[str, ...]]:
        with self._connection() as connection, self._dict_cursor(connection) as cursor:
            cursor.execute(
                """
                SELECT task_key, definition->'dependencies' AS dependencies
                FROM orchestration_v2.task_definition
                WHERE lifecycle_status='active'
                """
            )
            graph: dict[str, tuple[str, ...]] = {}
            for row in cursor.fetchall():
                dependencies = row["dependencies"] or []
                graph[row["task_key"]] = tuple(
                    item["task_key"] for item in dependencies
                )
            return graph

    def active_task_keys(self) -> set[str]:
        with self._connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT task_key FROM orchestration_v2.task_definition
                WHERE lifecycle_status='active'
                """
            )
            return {row[0] for row in cursor.fetchall()}

    def published_endpoint_tasks(self) -> dict:
        from service.source_connectors.ant_scheduled import SCHEDULED_ROUTES
        with self._connection() as conn, self._dict_cursor(conn) as cur:
            cur.execute("""
                SELECT e.source_id,e.endpoint_key,t.task_key,t.task_definition_id
                FROM orchestration_v2.task_definition t
                CROSS JOIN LATERAL jsonb_array_elements_text(
                    t.definition->'acquisition_endpoint_ids') AS ids(id)
                JOIN orchestration_v2.acquisition_endpoint e
                  ON e.acquisition_endpoint_id=ids.id::bigint
                WHERE t.lifecycle_status='active'
                ORDER BY t.task_key
            """)
            result = {}
            for row in cur.fetchall():
                source, key = row['source_id'], row['endpoint_key']
                if source == 'financial_data' and key in SCHEDULED_ROUTES:
                    key = SCHEDULED_ROUTES[key].route
                elif source not in ('financial_data', 'tushare'):
                    key = f'{source}/{key}'
                result.setdefault((source, key), []).append({
                    'task_key': row['task_key'], 'definition_id': row['task_definition_id']})
            return result

    def endpoint_registry_pairs(self) -> list[dict]:
        """Join the flat registry against the versioned contract layer.

        Both are compiled from the same code registry but neither is
        cross-checked, so the pair is exposed here for drift auditing.  The
        contract cadence is read back through the task that consumes the
        endpoint because the endpoint row itself carries no cadence.

        Endpoints of an equivalent group are alternatives or frequency
        variants of one logical product and share a single task, so a cadence
        is only comparable for an endpoint that is the sole member of its
        task; comparing group members would report their deliberate variation
        as drift.
        """

        if not self.schema_exists():
            return []
        with self._connection() as connection, self._dict_cursor(connection) as cursor:
            cursor.execute(
                """
                SELECT COALESCE(registry.source_id, endpoint.source_id) AS source_id,
                       COALESCE(registry.endpoint_key, endpoint.endpoint_key)
                           AS endpoint_key,
                       registry.acquisition_mode,
                       registry.cadence AS registry_cadence,
                       endpoint.acquisition_endpoint_id IS NOT NULL AS governed,
                       contract_cadence.cadence AS contract_cadence
                FROM public.sys_source_endpoint registry
                FULL OUTER JOIN orchestration_v2.acquisition_endpoint endpoint
                    ON endpoint.source_id = registry.source_id
                   AND endpoint.endpoint_key = registry.endpoint_key
                   AND endpoint.lifecycle_status = 'active'
                LEFT JOIN LATERAL (
                    SELECT definition->'scope_contract'->>'cadence' AS cadence
                    FROM orchestration_v2.task_definition definition
                    WHERE definition.lifecycle_status = 'active'
                      AND jsonb_array_length(
                            definition.definition->'acquisition_endpoint_ids'
                          ) = 1
                      AND definition.definition->'acquisition_endpoint_ids'->0
                          = to_jsonb(endpoint.acquisition_endpoint_id)
                    ORDER BY definition.task_definition_id DESC
                    LIMIT 1
                ) contract_cadence ON TRUE
                ORDER BY 1 NULLS LAST, 2 NULLS LAST
                """
            )
            rows = []
            for row in cursor.fetchall():
                item = dict(row)
                item["registered"] = item["source_id"] is not None
                item["governed"] = bool(item["governed"])
                rows.append(item)
            return rows

    def execution_activity_by_task(self, *, since) -> dict[str, dict]:
        """Recent execution evidence per task, independent of any definition.

        The scheduler decides dispatching from the code blueprint, not from
        ``task_definition.schedule``.  Comparing the two therefore needs a
        factual record of what actually ran, not another declarative field.

        Only routine runs (``purpose='daily'`` dispatched by the scheduler)
        count as "the scheduler is dispatching this".  Initialization,
        backfill and repair runs are one-off operator or recovery work and
        must not make a stopped task look scheduled.
        """

        if not self.schema_exists():
            return {}
        with self._connection() as connection, self._dict_cursor(connection) as cursor:
            cursor.execute(
                """
                SELECT task_key,
                       count(*) FILTER (WHERE routine) AS routine_total,
                       count(*) FILTER (WHERE routine AND status = 'success')
                           AS routine_succeeded,
                       max(finished_at) FILTER (WHERE routine) AS routine_last_finished
                FROM (
                    SELECT task_key, status, finished_at,
                           purpose = 'daily'
                               AND trigger_source IN ('schedule', 'dependency')
                               AS routine
                    FROM orchestration_v2.task_execution
                    WHERE created_at >= %s
                ) recent
                GROUP BY task_key
                """,
                (since,),
            )
            return {
                row["task_key"]: {
                    "total": int(row["routine_total"] or 0),
                    "succeeded": int(row["routine_succeeded"] or 0),
                    "last_finished": row["routine_last_finished"],
                }
                for row in cursor.fetchall()
            }

    def field_lineage_rows(self) -> list[dict] | None:
        """Return persisted field lineage reshaped like the compiler output.

        ``None`` means the lineage table is absent or unsynced; callers fall
        back to the code compiler rather than showing an empty inventory,
        because an unsynced table must not look like "no lineage exists".
        """

        if not self.schema_exists():
            return None
        try:
            with self._connection() as connection, self._dict_cursor(connection) as cursor:
                cursor.execute(
                    """
                    SELECT source_id, table_name, field_name, interface_key,
                           field_type, description
                    FROM orchestration_v2.field_lineage
                    ORDER BY table_name, field_name, interface_key
                    """
                )
                rows = [dict(row) for row in cursor.fetchall()]
        except Exception:  # pragma: no cover - table not migrated yet
            return None
        if not rows:
            return None
        tables: dict[tuple[str, str], dict] = {}
        for row in rows:
            key = (row["source_id"], row["table_name"])
            entry = tables.setdefault(key, {
                "table": row["table_name"],
                "source": row["source_id"],
                "interfaces": [],
                "fields": [],
            })
            if row["interface_key"] not in entry["interfaces"]:
                entry["interfaces"].append(row["interface_key"])
            field = next(
                (item for item in entry["fields"] if item["name"] == row["field_name"]),
                None,
            )
            if field is None:
                field = {
                    "name": row["field_name"],
                    "type": row["field_type"],
                    "description": row["description"],
                    "from_interfaces": [],
                }
                entry["fields"].append(field)
            if row["interface_key"] not in field["from_interfaces"]:
                field["from_interfaces"].append(row["interface_key"])
        return [tables[key] for key in sorted(tables)]

    def interface_registry_detail(self, source_id: str, interface_key: str) -> dict | None:
        """Return one persisted interface detail row, or ``None`` if absent."""

        if not self.schema_exists():
            return None
        try:
            with self._connection() as connection, self._dict_cursor(connection) as cursor:
                cursor.execute(
                    """
                    SELECT payload
                    FROM orchestration_v2.interface_registry
                    WHERE source_id = %s AND interface_key = %s
                    """,
                    (source_id, interface_key),
                )
                row = cursor.fetchone()
        except Exception:  # pragma: no cover - table not migrated yet
            return None
        if not row:
            return None
        payload = row["payload"]
        if isinstance(payload, str):
            payload = json.loads(payload)
        return payload if isinstance(payload, dict) else None

    def last_tushare_nonempty(self, api_name: str) -> dict | None:
        """Direct endpoint evidence only; a sibling VIP task is not proof."""
        with self._connection() as connection, self._dict_cursor(connection) as cursor:
            cursor.execute("""
                SELECT * FROM (
                  (SELECT completed_at AS observed_at, row_count AS rows_fetched,
                          'request' AS evidence_source
                   FROM tushare_raw_request WHERE api_name=%s AND status='success'
                     AND row_count>0 AND completed_at IS NOT NULL
                   ORDER BY completed_at DESC LIMIT 1)
                  UNION ALL
                  (SELECT occurred_at, (payload->>'rows_fetched')::bigint, 'acquire_event'
                   FROM orchestration_v2.task_execution_event
                   WHERE event_type='node.acquire.request_completed' AND payload->>'api_name'=%s
                     AND (payload->>'rows_fetched')::bigint>0
                   ORDER BY occurred_at DESC LIMIT 1)
                ) hits ORDER BY observed_at DESC LIMIT 1
            """, (api_name, api_name))
            row = cursor.fetchone()
            return dict(row) if row else None

    def interface_registry_rows(self) -> list[dict] | None:
        """Return the persisted interface inventory reshaped like the compiler.

        ``None`` means the registry table is absent or unsynced; callers fall
        back to the code compiler rather than showing an empty inventory,
        because an unsynced table must not look like "no interfaces exist".
        """

        if not self.schema_exists():
            return None
        try:
            with self._connection() as connection, self._dict_cursor(connection) as cursor:
                cursor.execute(
                    """
                    SELECT source_id, interface_key, payload
                    FROM orchestration_v2.interface_registry
                    ORDER BY source_id, interface_key
                    """
                )
                rows = [dict(row) for row in cursor.fetchall()]
        except Exception:  # pragma: no cover - table not migrated yet
            return None
        if not rows:
            return None
        items: list[dict] = []
        for row in rows:
            payload = row.get("payload")
            if isinstance(payload, str):
                payload = json.loads(payload)
            if not isinstance(payload, dict):
                continue
            item = dict(payload)
            item.setdefault("source", row["source_id"])
            item.setdefault("key", row["interface_key"])
            items.append(item)
        return items

    def publish_definition(
        self,
        definition_id: int,
        *,
        actor: str,
        app_revision: str,
        image_digest: str,
    ) -> dict:
        with self._connection() as connection, self._dict_cursor(connection) as cursor:
            cursor.execute(
                """
                SELECT * FROM orchestration_v2.task_definition
                WHERE task_definition_id=%s FOR UPDATE
                """,
                (definition_id,),
            )
            candidate = cursor.fetchone()
            if not candidate:
                raise LookupError(f"task definition draft not found: {definition_id}")
            if candidate["lifecycle_status"] != "draft":
                raise ValueError("only a draft task definition can be published")
            self._lock_version_key(cursor, 2_026_067_002, candidate["task_key"])
            cursor.execute(
                """
                UPDATE orchestration_v2.task_definition
                SET lifecycle_status='retired', retired_at=NOW(), updated_at=NOW()
                WHERE task_key=%s AND lifecycle_status='active'
                """,
                (candidate["task_key"],),
            )
            cursor.execute(
                """
                UPDATE orchestration_v2.task_definition
                SET lifecycle_status='active', activated_by=%s,
                    app_revision=%s, image_digest=%s,
                    activated_at=NOW(), updated_at=NOW()
                WHERE task_definition_id=%s AND lifecycle_status='draft'
                RETURNING *
                """,
                (actor, app_revision, image_digest, definition_id),
            )
            return dict(cursor.fetchone())

    def create_execution(self, request: ExecutionRequest) -> tuple[dict, bool]:
        scope_digest = canonical_digest(request.frozen_scope)
        with self._connection() as connection, self._dict_cursor(connection) as cursor:
            cursor.execute(
                """
                SELECT * FROM orchestration_v2.task_definition
                WHERE task_key=%s AND lifecycle_status='active'
                FOR UPDATE
                """,
                (request.task_key,),
            )
            definition = cursor.fetchone()
            if not definition:
                raise LookupError(f"active task definition not found: {request.task_key}")
            cursor.execute(
                """
                SELECT * FROM orchestration_v2.task_execution
                WHERE task_key=%s AND (
                    observation_key=%s OR (
                        task_key='local_factor_snapshot'
                        AND observation_start=%s AND observation_end=%s
                    )
                )
                  AND status IN (
                    'created','queued','running','waiting_dependency','retrying',
                    'validating','publishing'
                  )
                ORDER BY task_execution_id DESC
                LIMIT 1
                FOR UPDATE
                """,
                (request.task_key, request.observation_key,
                 request.observation_start, request.observation_end),
            )
            active_scope = cursor.fetchone()
            if active_scope:
                return dict(active_scope), False
            historical = request.purpose.value in {
                "initialization", "backfill", "repair"
            }
            resource_class = (
                ("factor-backfill" if request.task_key == "local_factor_snapshot" else "v2-backfill")
                if historical
                else definition["definition"]["resource"]["resource_class"]
            )
            quota_guarded_history = (
                request.task_key in QUOTA_GUARDED_DATASETS
                and request.frozen_scope.get("recovery_scope")
                == "quota_guarded_history"
            )
            priority = (
                95
                if request.purpose.value == "repair" or quota_guarded_history
                else 30
                if historical
                else definition["definition"]["resource"]["priority"]
            )
            nodes = definition["definition"].get("nodes", [])
            node_status = {node["key"]: "pending" for node in nodes}
            if nodes:
                node_status[nodes[0]["key"]] = "ready"
            cursor.execute(
                """
                INSERT INTO orchestration_v2.task_execution(
                    task_definition_id, task_key, definition_version,
                    definition_digest, purpose, trigger_source, status,
                    idempotency_key, observation_key, observation_start,
                    observation_end, observation_period, publication_date,
                    data_available_at, frozen_scope, scope_digest,
                    current_node_key, node_status, priority, resource_class,
                    max_attempts, app_revision, image_digest
                ) VALUES (
                    %s,%s,%s,%s,%s,%s,'queued',%s,%s,%s,%s,%s,%s,%s,
                    %s::jsonb,%s,%s,%s::jsonb,%s,%s,%s,%s,%s
                )
                ON CONFLICT DO NOTHING
                RETURNING *
                """,
                (
                    definition["task_definition_id"],
                    definition["task_key"],
                    definition["version"],
                    definition["definition_digest"],
                    request.purpose,
                    request.trigger_source,
                    request.idempotency_key,
                    request.observation_key,
                    request.observation_start,
                    request.observation_end,
                    request.observation_period,
                    request.publication_date,
                    request.data_available_at,
                    json.dumps(request.frozen_scope, ensure_ascii=False),
                    scope_digest,
                    nodes[0]["key"] if nodes else None,
                    json.dumps(node_status, ensure_ascii=False),
                    priority,
                    resource_class,
                    max(node["retry"]["max_attempts"] for node in nodes),
                    request.app_revision or definition["app_revision"],
                    request.image_digest or definition["image_digest"],
                ),
            )
            created = cursor.fetchone()
            if created:
                return dict(created), True
            # INSERT ... ON CONFLICT DO NOTHING reported a conflict.  The
            # winner owns the unique idempotency_key, so re-read by that exact
            # key first.  This is deterministic even when the competing
            # transaction has already committed and moved the row to a
            # terminal status.
            cursor.execute(
                """
                SELECT * FROM orchestration_v2.task_execution
                WHERE idempotency_key=%s
                ORDER BY task_execution_id DESC
                LIMIT 1
                """,
                (request.idempotency_key,),
            )
            existing = cursor.fetchone()
            if existing:
                return dict(existing), False
            # Defensive fallback for pre-migration rows created under a
            # different idempotency spelling for the same logical cycle.
            cursor.execute(
                """
                SELECT * FROM orchestration_v2.task_execution
                WHERE task_key=%s AND observation_key=%s
                  AND status IN (
                    'created','queued','running','waiting_dependency',
                    'retrying','validating','publishing'
                  )
                ORDER BY task_execution_id DESC
                LIMIT 1
                """,
                (request.task_key, request.observation_key),
            )
            existing = cursor.fetchone()
            if not existing:
                raise RuntimeError("execution insert conflicted but owner was not found")
            return dict(existing), False

    def supersede_not_expected_daily_scope(
        self,
        observation_date,
        task_keys: tuple[str, ...],
        *,
        reason: str,
    ) -> list[dict]:
        """Correct an accidentally dispatched daily scope without data loss.

        The execution and its audit trail remain queryable, while the dataset
        calendar no longer treats that logical date as an expected delivery.
        This is intentionally narrower than deleting an execution or business
        rows produced by it.
        """

        if not task_keys:
            return []
        superseded: list[dict] = []
        with self._connection() as connection, self._dict_cursor(connection) as cursor:
            cursor.execute(
                """
                SELECT *
                FROM orchestration_v2.task_execution
                WHERE purpose='daily'
                  AND observation_start=%s
                  AND observation_end=%s
                  AND task_key=ANY(%s)
                  AND status <> 'superseded'
                ORDER BY task_execution_id
                FOR UPDATE
                """,
                (observation_date, observation_date, list(task_keys)),
            )
            for candidate in cursor.fetchall():
                execution_id = int(candidate["task_execution_id"])
                cursor.execute(
                    """
                    UPDATE orchestration_v2.task_execution
                    SET status='superseded', finished_at=NOW(),
                        final_error_category='not_due',
                        final_error_message=%s,
                        final_error_detail=jsonb_build_object(
                            'observation_date', %s::text,
                            'corrective_action', 'mark_not_expected'
                        ),
                        lease_owner=NULL, lease_token=NULL,
                        lease_expires_at=NULL, updated_at=NOW()
                    WHERE task_execution_id=%s
                    RETURNING *
                    """,
                    (reason, observation_date.isoformat(), execution_id),
                )
                row = cursor.fetchone()
                cursor.execute(
                    """
                    UPDATE orchestration_v2.dataset_state
                    SET expectation_status='not_expected',
                        data_status='pending', ready=false,
                        validation_summary=validation_summary || jsonb_build_object(
                            'superseded', true,
                            'superseded_reason', %s
                        ),
                        updated_at=NOW()
                    WHERE source_execution_id=%s
                    """,
                    (reason, execution_id),
                )
                self._append_event(
                    cursor,
                    execution_id,
                    event_type="execution.superseded_not_expected",
                    node_key=candidate.get("current_node_key"),
                    attempt_number=max(1, int(candidate["attempt_count"])),
                    event_key=f"execution.superseded_not_expected:{execution_id}",
                    payload={
                        "reason": reason,
                        "observation_date": observation_date.isoformat(),
                    },
                    evidence_references=[],
                )
                superseded.append(dict(row))
        return superseded

    def requeue_due_daily_scope(
        self,
        observation_date,
        task_keys: tuple[str, ...],
        *,
        reason: str,
    ) -> list[dict]:
        """Reactivate daily T+1 work previously parked as not yet due.

        The original idempotency key and immutable definition are retained.
        Creating a second execution would either conflict on that key or hide
        the publication-gate transition behind a duplicate instance.
        """

        if not task_keys:
            return []
        requeued: list[dict] = []
        with self._connection() as connection, self._dict_cursor(connection) as cursor:
            cursor.execute(
                """
                SELECT execution.*, definition.definition
                FROM orchestration_v2.task_execution AS execution
                JOIN orchestration_v2.task_definition AS definition
                  ON definition.task_definition_id=execution.task_definition_id
                WHERE execution.purpose='daily'
                  AND execution.observation_start=%s
                  AND execution.observation_end=%s
                  AND execution.task_key=ANY(%s)
                  AND execution.status='superseded'
                  AND execution.final_error_category='not_due'
                ORDER BY execution.task_execution_id
                FOR UPDATE OF execution
                """,
                (observation_date, observation_date, list(task_keys)),
            )
            for candidate in cursor.fetchall():
                execution_id = int(candidate["task_execution_id"])
                nodes = candidate["definition"].get("nodes", [])
                node_status = {node["key"]: "pending" for node in nodes}
                if nodes:
                    node_status[nodes[0]["key"]] = "ready"
                cursor.execute(
                    """
                    UPDATE orchestration_v2.task_execution
                    SET status='queued', eligible_at=NOW(), finished_at=NULL,
                        current_node_key=%s, node_status=%s::jsonb,
                        final_error_category=NULL, final_error_message=NULL,
                        final_error_detail='{}'::jsonb,
                        lease_owner=NULL, lease_token=NULL,
                        lease_expires_at=NULL, updated_at=NOW()
                    WHERE task_execution_id=%s
                      AND status='superseded'
                      AND final_error_category='not_due'
                    RETURNING *
                    """,
                    (
                        nodes[0]["key"] if nodes else None,
                        json.dumps(node_status, ensure_ascii=False),
                        execution_id,
                    ),
                )
                row = cursor.fetchone()
                if not row:
                    continue
                cursor.execute(
                    """
                    UPDATE orchestration_v2.dataset_state
                    SET expectation_status='expected', data_status='pending',
                        ready=false,
                        validation_summary=validation_summary ||
                            jsonb_build_object(
                                'requeued_after_release', true,
                                'requeue_reason', %s
                            ),
                        updated_at=NOW()
                    WHERE source_execution_id=%s
                    """,
                    (reason, execution_id),
                )
                self._append_event(
                    cursor,
                    execution_id,
                    event_type="execution.requeued_after_release",
                    node_key=nodes[0]["key"] if nodes else None,
                    attempt_number=max(1, int(candidate["attempt_count"])),
                    event_key=(
                        f"execution.requeued_after_release:{execution_id}:"
                        f"{candidate['attempt_count']}"
                    ),
                    payload={
                        "reason": reason,
                        "observation_date": observation_date.isoformat(),
                    },
                    evidence_references=[],
                )
                requeued.append(dict(row))
        return requeued

    def reconcile_resolved_attention_executions(self, *, limit: int = 500) -> int:
        """Close stale alerts when a later execution verified the same scope.

        This never changes the successful replacement or its dataset state;
        it only preserves the older failed attempt as superseded history.
        """

        if not 1 <= limit <= 5000:
            raise ValueError("limit must be between 1 and 5000")
        reconciled = 0
        with self._connection() as connection, self._dict_cursor(connection) as cursor:
            cursor.execute(
                """
                SELECT failed.task_execution_id, failed.current_node_key,
                       failed.attempt_count, replacement.task_execution_id
                           AS replacement_execution_id
                FROM orchestration_v2.task_execution AS failed
                JOIN LATERAL (
                    SELECT candidate.task_execution_id
                    FROM orchestration_v2.task_execution AS candidate
                    WHERE candidate.task_key=failed.task_key
                      AND candidate.status='success'
                      AND candidate.task_execution_id>failed.task_execution_id
                      AND (
                        candidate.observation_key=failed.observation_key
                        OR (
                          candidate.observation_start IS NOT NULL
                          AND candidate.observation_end IS NOT NULL
                          AND failed.observation_start IS NOT NULL
                          AND failed.observation_end IS NOT NULL
                          AND candidate.observation_start<=failed.observation_start
                          AND candidate.observation_end>=failed.observation_end
                        )
                      )
                    ORDER BY candidate.task_execution_id DESC
                    LIMIT 1
                ) AS replacement ON true
                WHERE failed.status='attention'
                ORDER BY failed.task_execution_id
                LIMIT %s
                FOR UPDATE OF failed
                """,
                (limit,),
            )
            for candidate in cursor.fetchall():
                execution_id = int(candidate["task_execution_id"])
                replacement_id = int(candidate["replacement_execution_id"])
                cursor.execute(
                    """
                    UPDATE orchestration_v2.task_execution
                    SET status='superseded', finished_at=NOW(),
                        final_error_category='recovered_by_later_execution',
                        final_error_message=%s,
                        final_error_detail=final_error_detail ||
                            jsonb_build_object(
                                'recovered_by_execution_id', %s,
                                'corrective_action', 'superseded_after_verified_repair'
                            ),
                        updated_at=NOW()
                    WHERE task_execution_id=%s AND status='attention'
                    """,
                    (
                        f"recovered by successful execution {replacement_id}",
                        replacement_id,
                        execution_id,
                    ),
                )
                if cursor.rowcount != 1:
                    continue
                self._append_event(
                    cursor,
                    execution_id,
                    event_type="execution.superseded_after_verified_repair",
                    node_key=candidate.get("current_node_key"),
                    attempt_number=max(1, int(candidate["attempt_count"])),
                    event_key=(
                        "execution.superseded_after_verified_repair:"
                        f"{execution_id}:{replacement_id}"
                    ),
                    payload={"recovered_by_execution_id": replacement_id},
                    evidence_references=[{
                        "task_execution_id": replacement_id,
                        "event": "execution.success",
                    }],
                )
                reconciled += 1
        return reconciled

    def reconcile_duplicate_attention_executions(self, *, limit: int = 500) -> int:
        """Keep one actionable alert per logical task scope.

        Repeated provider patrols are execution history, not independent open
        incidents. Older attempts remain queryable as ``superseded`` while
        the newest attention row remains the sole operator action target.
        """

        if not 1 <= limit <= 5000:
            raise ValueError("limit must be between 1 and 5000")
        reconciled = 0
        with self._connection() as connection, self._dict_cursor(connection) as cursor:
            cursor.execute(
                """
                WITH ranked AS (
                    SELECT task_execution_id, task_key, observation_key,
                           current_node_key, attempt_count,
                           first_value(task_execution_id) OVER (
                               PARTITION BY task_key, observation_key
                               ORDER BY task_execution_id DESC
                           ) AS current_execution_id,
                           row_number() OVER (
                               PARTITION BY task_key, observation_key
                               ORDER BY task_execution_id DESC
                           ) AS position
                    FROM orchestration_v2.task_execution
                    WHERE status='attention'
                )
                SELECT * FROM ranked
                WHERE position > 1
                ORDER BY task_execution_id
                LIMIT %s
                """,
                (limit,),
            )
            for candidate in cursor.fetchall():
                execution_id = int(candidate["task_execution_id"])
                current_id = int(candidate["current_execution_id"])
                cursor.execute(
                    """
                    UPDATE orchestration_v2.task_execution
                    SET status='superseded', finished_at=NOW(),
                        final_error_category='duplicate_attention_attempt',
                        final_error_message=%s,
                        final_error_detail=final_error_detail ||
                            jsonb_build_object(
                                'current_attention_execution_id', %s,
                                'corrective_action', 'deduplicate_attention_attempts'
                            ),
                        lease_owner=NULL, lease_token=NULL,
                        lease_expires_at=NULL, updated_at=NOW()
                    WHERE task_execution_id=%s AND status='attention'
                    """,
                    (
                        f"superseded by current attention execution {current_id}",
                        current_id,
                        execution_id,
                    ),
                )
                if cursor.rowcount != 1:
                    continue
                self._append_event(
                    cursor,
                    execution_id,
                    event_type="execution.superseded_duplicate_attention",
                    node_key=candidate.get("current_node_key"),
                    attempt_number=max(1, int(candidate["attempt_count"])),
                    event_key=(
                        "execution.superseded_duplicate_attention:"
                        f"{execution_id}:{current_id}"
                    ),
                    payload={"current_attention_execution_id": current_id},
                    evidence_references=[{"task_execution_id": current_id}],
                )
                reconciled += 1
        return reconciled

    def attention_covered_by_active_execution_ids(
        self, *, limit: int = 5000
    ) -> tuple[int, ...]:
        """Return old incidents currently covered by a newer active scope.

        The old failure remains immutable evidence until the replacement is
        independently validated. Operators should nevertheless see it as
        recovery-in-progress rather than as a second action item.
        """

        if not 1 <= limit <= 5000:
            raise ValueError("limit must be between 1 and 5000")
        with self._connection() as connection, self._dict_cursor(connection) as cursor:
            cursor.execute(
                """
                SELECT attention.task_execution_id
                FROM orchestration_v2.task_execution AS attention
                WHERE attention.status='attention'
                  AND attention.observation_start IS NOT NULL
                  AND attention.observation_end IS NOT NULL
                  AND EXISTS (
                      SELECT 1
                      FROM orchestration_v2.task_execution AS recovery
                      WHERE recovery.task_key=attention.task_key
                        AND recovery.task_execution_id>
                            attention.task_execution_id
                        AND recovery.status IN (
                            'created','queued','running','waiting_dependency',
                            'retrying','validating','publishing'
                        )
                        AND recovery.observation_start<=
                            attention.observation_start
                        AND recovery.observation_end>=
                            attention.observation_end
                  )
                ORDER BY attention.task_execution_id
                LIMIT %s
                """,
                (limit,),
            )
            return tuple(
                int(row["task_execution_id"]) for row in cursor.fetchall()
            )

    def active_recovery_scopes(self) -> list[dict]:
        """Read actual active ranges, never infer coverage from task names."""
        with self._connection() as connection, self._dict_cursor(connection) as cursor:
            cursor.execute("""
                SELECT task_execution_id, task_key, observation_key,
                       observation_start, observation_end, status, eligible_at, updated_at
                FROM orchestration_v2.task_execution
                WHERE status IN ('created','queued','running','waiting_dependency',
                                 'retrying','validating','publishing')
            """)
            return [dict(row) for row in cursor.fetchall()]

    def overdue_empty_attempts(self, task_keys):
        with self._connection() as conn, conn.cursor() as cur:
            cur.execute("""SELECT DISTINCT task_key, observation_key
                FROM orchestration_v2.task_execution
                WHERE task_key=ANY(%s) AND observation_start=observation_end
                  AND frozen_scope->'reasons' = '["recheck_empty"]'::jsonb
                  AND (status IN ('created','queued','running','waiting_dependency',
                                  'retrying','validating','publishing')
                       OR (created_at AT TIME ZONE 'Asia/Shanghai')::date >= observation_end + 8)
            """, (sorted(task_keys),))
            return set(cur.fetchall())

    def chip_security_progress(self):
        """Aggregate the last audited security/date obligations, not request counts."""
        with self._connection() as conn, self._dict_cursor(conn) as cur:
            cur.execute("""WITH active AS MATERIALIZED (
                SELECT observation_start, observation_end FROM orchestration_v2.task_execution
                WHERE task_key='cyq_chips' AND status IN ('created','queued','running',
                    'waiting_dependency','retrying','validating','publishing')
            ) SELECT count(*) AS audited_partial_dates,
                count(*) FILTER (WHERE NOT EXISTS (SELECT 1 FROM active a
                    WHERE partition_date BETWEEN a.observation_start AND a.observation_end))
                    AS dates_without_active_window,
                count(expected_entity_count) AS dates_with_denominator,
                sum(expected_entity_count) AS expected_pairs,sum(entity_count) AS observed_pairs,
                max(checked_at) AS last_checked_at,min(checked_at) AS earliest_checked_at
                FROM sys_data_coverage_partition
                WHERE dataset_name='cyq_chips' AND status='partial'""")
            return dict(cur.fetchone())

    def factor_input_issues(self, trade_date) -> list[dict]:
        """Bounded persisted evidence; never recompute factors for the dashboard."""
        from service.research.local_factors.catalog import FACTOR_SCHEMA_VERSION
        with self._connection() as connection, self._dict_cursor(connection) as cursor:
            cursor.execute("""
                SELECT problem.key AS factor, problem.value AS reason,
                       count(*) AS affected_securities
                FROM local_factor_snapshot snapshot
                CROSS JOIN LATERAL jsonb_each_text(
                    COALESCE(snapshot.audit_evidence->'unresolved','{}'::jsonb)
                ) problem
                WHERE trade_date=%s AND schema_version=%s
                GROUP BY problem.key,problem.value
                ORDER BY count(*) DESC,problem.key LIMIT 8
            """, (trade_date, FACTOR_SCHEMA_VERSION))
            return [dict(row) for row in cursor.fetchall()]

    def latest_chip_history_window(self) -> dict | None:
        from service.data_coverage.registry import COVERAGE_RULES
        with self._connection() as connection, self._dict_cursor(connection) as cursor:
            cursor.execute("""
                SELECT execution.*, EXISTS (
                    SELECT 1 FROM orchestration_v2.dataset_state state
                    WHERE state.source_execution_id=execution.task_execution_id
                      AND state.dataset_name='cyq_chips' AND state.ready
                      AND state.validation_summary->>'rule_revision'=%s
                      AND state.observation_start<=execution.observation_start
                      AND state.observation_end>=execution.observation_end
                ) AS certified
                FROM orchestration_v2.task_execution execution
                WHERE task_key='cyq_chips'
                  AND frozen_scope->>'recovery_scope'='bounded_fanout_history'
                  AND frozen_scope->>'history_order'='newest_first'
                  AND observation_start IS NOT NULL
                ORDER BY observation_start, task_execution_id DESC LIMIT 1
            """, (str(COVERAGE_RULES.get('cyq_chips').revision),))
            row = cursor.fetchone()
            return dict(row) if row else None

    def transient_recovery_rounds(self) -> dict[int, int]:
        with self._connection() as connection, self._dict_cursor(connection) as cursor:
            cursor.execute("""
                SELECT e.task_execution_id, count(*) AS rounds
                FROM orchestration_v2.task_execution_event e
                JOIN orchestration_v2.task_execution t USING (task_execution_id)
                WHERE t.status='attention'
                  AND e.event_type='execution.auto_retry_transient'
                GROUP BY e.task_execution_id
            """)
            return {int(row['task_execution_id']): int(row['rounds'])
                    for row in cursor.fetchall()}

    def reconcile_redundant_pending_executions(self, *, limit: int = 1000) -> int:
        """Retire an older pending scope already covered by a newer one.

        Only queued/retrying executions are eligible.  An active replacement
        must have the same purpose; a successfully validated replacement may
        cross purposes (for example backfill replacing initialization).
        Running work is never interrupted, and the replacement must cover the
        complete dated scope of the older execution.
        """

        if not 1 <= limit <= 5000:
            raise ValueError("limit must be between 1 and 5000")
        reconciled = 0
        with self._connection() as connection, self._dict_cursor(connection) as cursor:
            cursor.execute(
                """
                SELECT pending.*,
                       replacement.task_execution_id AS replacement_execution_id
                FROM orchestration_v2.task_execution AS pending
                JOIN LATERAL (
                    SELECT newer.task_execution_id
                    FROM orchestration_v2.task_execution AS newer
                    WHERE newer.task_key=pending.task_key
                      AND (
                          newer.purpose=pending.purpose
                          OR newer.status='success'
                      )
                      AND newer.task_execution_id>pending.task_execution_id
                      AND newer.status IN (
                          'created','queued','running','waiting_dependency',
                          'retrying','validating','publishing','success'
                      )
                      AND newer.observation_start<=pending.observation_start
                      AND newer.observation_end>=pending.observation_end
                    ORDER BY newer.task_execution_id DESC
                    LIMIT 1
                ) AS replacement ON TRUE
                WHERE pending.status IN ('queued','retrying')
                  AND pending.observation_start IS NOT NULL
                  AND pending.observation_end IS NOT NULL
                ORDER BY pending.task_execution_id
                FOR UPDATE OF pending SKIP LOCKED
                LIMIT %s
                """,
                (limit,),
            )
            for candidate in cursor.fetchall():
                execution_id = int(candidate["task_execution_id"])
                replacement_id = int(candidate["replacement_execution_id"])
                cursor.execute(
                    """
                    UPDATE orchestration_v2.task_execution
                    SET status='superseded', finished_at=NOW(),
                        final_error_category='redundant_scope',
                        final_error_message=%s,
                        final_error_detail=final_error_detail ||
                            jsonb_build_object(
                                'replacement_execution_id', %s,
                                'corrective_action', 'deduplicate_pending_scope'
                            ),
                        lease_owner=NULL, lease_token=NULL,
                        lease_expires_at=NULL, updated_at=NOW()
                    WHERE task_execution_id=%s
                      AND status IN ('queued','retrying')
                    """,
                    (
                        f"superseded by covering execution {replacement_id}",
                        replacement_id,
                        execution_id,
                    ),
                )
                if cursor.rowcount != 1:
                    continue
                self._append_event(
                    cursor,
                    execution_id,
                    event_type="execution.superseded_redundant_scope",
                    node_key=candidate.get("current_node_key"),
                    attempt_number=max(1, int(candidate["attempt_count"])),
                    event_key=(
                        "execution.superseded_redundant_scope:"
                        f"{execution_id}:{replacement_id}"
                    ),
                    payload={"replacement_execution_id": replacement_id},
                    evidence_references=[{"task_execution_id": replacement_id}],
                )
                reconciled += 1
        return reconciled

    def revoke_obsolete_daily_certificates(self, *, limit=100, datasets=None):
        """Revoke only an obsolete exact-day certificate disproved by a current audit.

        Preserve the successful execution and original validation event as history.
        Never infer a ready state from this reconciliation.
        """
        from service.data_coverage.registry import COVERAGE_RULES
        versions = {r.dataset_name:r.revision for r in COVERAGE_RULES.list()
                    if r.date_partitioned and r.revision > 1 and
                    (datasets is None or r.dataset_name in datasets)}
        with self._connection() as conn, self._dict_cursor(conn) as cur:
            cur.execute("""SELECT s.dataset_state_id,s.dataset_name,s.source_execution_id,
                         s.observation_key,s.contract_version,s.validation_event_id,p.audit_id,
                         p.status, r.value AS revision,p.expected_entity_count,p.entity_count
                FROM orchestration_v2.dataset_state s JOIN jsonb_each_text(%s::jsonb) r ON r.key=s.dataset_name
                JOIN sys_data_coverage_partition p ON p.dataset_name=s.dataset_name
                    AND p.partition_date=s.observation_end AND p.expected
                JOIN sys_data_coverage_audit a ON a.audit_id=p.audit_id
                WHERE s.ready AND s.scope='{}'::jsonb AND s.observation_start=s.observation_end
                  AND s.observation_key=s.observation_end::text
                  AND substring(s.contract_version from '^coverage-rule:([0-9]+)$')::int < r.value::int
                  AND a.evidence->>'rule_revision'=r.value AND p.status IN ('missing','partial')
                ORDER BY p.partition_date DESC,s.dataset_state_id LIMIT %s
                FOR UPDATE OF s SKIP LOCKED FOR SHARE OF p""",(json.dumps(versions),limit))
            rows = cur.fetchall()
            for row in rows:
                status = 'gaps' if row['status']=='missing' else 'partial'
                proof = dict(row)
                event = self._append_event(cur,row['source_execution_id'],event_type='dataset.validation.revoked',
                    node_key='validate',attempt_number=None,event_key=None,payload=proof,
                    evidence_references=[{'audit_id':row['audit_id']}])
                cur.execute("""UPDATE orchestration_v2.dataset_state SET ready=false,data_status=%s,
                    published_at=NULL,contract_version=%s,expected_count=1,actual_count=0,
                    validation_summary=%s::jsonb,gap_summary=%s::jsonb,validation_event_id=%s,
                    revision=revision+1,updated_at=now() WHERE dataset_state_id=%s""",
                    (status,'coverage-rule:'+row['revision'],
                     json.dumps({'rule_revision':int(row['revision']),'supersedes':proof}),
                     json.dumps({row['status']:1}),event['event_id'],row['dataset_state_id']))
            return len(rows)

    def reconcile_stale_audit_contract_executions(self, *, limit: int = 1000) -> int:
        """Retire pending executions whose frozen audit contract is obsolete.

        V2 deliberately refuses to validate an execution under a rule other
        than the one frozen in its definition.  Once a new definition is
        active, retrying the stale instance can therefore never succeed.  Keep
        the evidence, retire only non-running instances, and let the repair
        planner create replacements against the active definition.
        """

        if not 1 <= limit <= 5000:
            raise ValueError("limit must be between 1 and 5000")
        reconciled = 0
        with self._connection() as connection, self._dict_cursor(connection) as cursor:
            cursor.execute(
                """
                SELECT execution.*, active.task_definition_id
                           AS replacement_definition_id,
                       active.version AS replacement_definition_version
                FROM orchestration_v2.task_execution AS execution
                JOIN orchestration_v2.task_definition AS frozen
                  ON frozen.task_definition_id=execution.task_definition_id
                JOIN orchestration_v2.task_definition AS active
                  ON active.task_key=execution.task_key
                 AND active.lifecycle_status='active'
                WHERE execution.status IN ('queued','retrying')
                  AND execution.task_definition_id<>active.task_definition_id
                  AND frozen.definition->'validation_contract'
                      IS DISTINCT FROM active.definition->'validation_contract'
                ORDER BY execution.task_execution_id
                FOR UPDATE OF execution SKIP LOCKED
                LIMIT %s
                """,
                (limit,),
            )
            for candidate in cursor.fetchall():
                execution_id = int(candidate["task_execution_id"])
                replacement_definition_id = int(
                    candidate["replacement_definition_id"]
                )
                replacement_version = int(
                    candidate["replacement_definition_version"]
                )
                cursor.execute(
                    """
                    UPDATE orchestration_v2.task_execution
                    SET status='superseded', finished_at=NOW(),
                        final_error_category='audit_contract_superseded',
                        final_error_message=%s,
                        final_error_detail=final_error_detail ||
                            jsonb_build_object(
                                'replacement_definition_id', %s,
                                'replacement_definition_version', %s,
                                'corrective_action',
                                'replan_with_active_audit_contract'
                            ),
                        lease_owner=NULL, lease_token=NULL,
                        lease_expires_at=NULL, updated_at=NOW()
                    WHERE task_execution_id=%s
                      AND status IN ('queued','retrying')
                    """,
                    (
                        "frozen audit contract was replaced by active "
                        f"definition v{replacement_version}",
                        replacement_definition_id,
                        replacement_version,
                        execution_id,
                    ),
                )
                if cursor.rowcount != 1:
                    continue
                self._append_event(
                    cursor,
                    execution_id,
                    event_type="execution.superseded_audit_contract",
                    node_key=candidate.get("current_node_key"),
                    attempt_number=max(1, int(candidate["attempt_count"])),
                    event_key=(
                        "execution.superseded_audit_contract:"
                        f"{execution_id}:{replacement_definition_id}"
                    ),
                    payload={
                        "replacement_definition_id": replacement_definition_id,
                        "replacement_definition_version": replacement_version,
                    },
                    evidence_references=[{
                        "task_definition_id": replacement_definition_id,
                    }],
                )
                reconciled += 1
        return reconciled

    def supersede_obsolete_definition_executions(
        self,
        task_keys: tuple[str, ...],
        *,
        reason: str,
        limit: int = 5000,
    ) -> int:
        """Retire non-running executions frozen to an obsolete definition.

        An implementation/formula change may leave the audit contract itself
        unchanged.  In that case the generic stale-audit reconciler cannot
        identify the work as obsolete, yet executing it would publish data
        under stale provenance.  This explicit, task-scoped operation keeps
        the old attempts as evidence and permits clean replanning against the
        active definition.  Running work is deliberately never interrupted.
        """

        if not task_keys:
            return 0
        if not reason.strip():
            raise ValueError("reason is required")
        if not 1 <= limit <= 10000:
            raise ValueError("limit must be between 1 and 10000")
        superseded = 0
        with self._connection() as connection, self._dict_cursor(connection) as cursor:
            cursor.execute(
                """
                SELECT execution.*, active.task_definition_id
                           AS replacement_definition_id,
                       active.version AS replacement_definition_version
                FROM orchestration_v2.task_execution AS execution
                JOIN orchestration_v2.task_definition AS active
                  ON active.task_key=execution.task_key
                 AND active.lifecycle_status='active'
                WHERE execution.task_key=ANY(%s)
                  AND execution.task_definition_id<>active.task_definition_id
                  AND execution.status IN (
                      'created','queued','waiting_dependency','retrying',
                      'attention'
                  )
                ORDER BY execution.task_execution_id
                FOR UPDATE OF execution SKIP LOCKED
                LIMIT %s
                """,
                (list(task_keys), limit),
            )
            for candidate in cursor.fetchall():
                execution_id = int(candidate["task_execution_id"])
                replacement_definition_id = int(
                    candidate["replacement_definition_id"]
                )
                replacement_version = int(
                    candidate["replacement_definition_version"]
                )
                cursor.execute(
                    """
                    UPDATE orchestration_v2.task_execution
                    SET status='superseded', finished_at=NOW(),
                        final_error_category='definition_superseded',
                        final_error_message=%s,
                        final_error_detail=final_error_detail ||
                            jsonb_build_object(
                                'replacement_definition_id', %s,
                                'replacement_definition_version', %s,
                                'corrective_action',
                                'replan_with_active_definition'
                            ),
                        lease_owner=NULL, lease_token=NULL,
                        lease_expires_at=NULL, updated_at=NOW()
                    WHERE task_execution_id=%s
                      AND status IN (
                          'created','queued','waiting_dependency','retrying',
                          'attention'
                      )
                    """,
                    (
                        reason,
                        replacement_definition_id,
                        replacement_version,
                        execution_id,
                    ),
                )
                if cursor.rowcount != 1:
                    continue
                self._append_event(
                    cursor,
                    execution_id,
                    event_type="execution.superseded_definition",
                    node_key=candidate.get("current_node_key"),
                    attempt_number=max(1, int(candidate["attempt_count"])),
                    event_key=(
                        "execution.superseded_definition:"
                        f"{execution_id}:{replacement_definition_id}"
                    ),
                    payload={
                        "reason": reason,
                        "replacement_definition_id": replacement_definition_id,
                        "replacement_definition_version": replacement_version,
                    },
                    evidence_references=[{
                        "task_definition_id": replacement_definition_id,
                    }],
                )
                superseded += 1
        return superseded

    def promote_quota_guarded_history_executions(self, *, limit: int = 100) -> int:
        """Give priority only to the newest covering guarded-history scope."""

        if not 1 <= limit <= 5000:
            raise ValueError("limit must be between 1 and 5000")
        normalized = 0
        with self._connection() as connection, self._dict_cursor(connection) as cursor:
            cursor.execute(
                """
                SELECT execution.*,
                       CASE WHEN EXISTS (
                           SELECT 1
                           FROM orchestration_v2.task_execution AS newer
                           WHERE newer.task_key=execution.task_key
                             AND newer.task_execution_id>
                                 execution.task_execution_id
                             AND newer.status IN (
                                 'created','queued','running',
                                 'waiting_dependency','retrying','validating',
                                 'publishing','success'
                             )
                             AND newer.observation_start<=
                                 execution.observation_start
                             AND newer.observation_end>=
                                 execution.observation_end
                       ) THEN 30 ELSE 95 END AS target_priority
                FROM orchestration_v2.task_execution AS execution
                WHERE execution.task_key=ANY(%s)
                  AND execution.frozen_scope->>'recovery_scope'=
                      'quota_guarded_history'
                  AND execution.status IN ('queued','retrying')
                  AND execution.priority <> CASE WHEN EXISTS (
                      SELECT 1
                      FROM orchestration_v2.task_execution AS newer
                      WHERE newer.task_key=execution.task_key
                        AND newer.task_execution_id>
                            execution.task_execution_id
                        AND newer.status IN (
                            'created','queued','running',
                            'waiting_dependency','retrying','validating',
                            'publishing','success'
                        )
                        AND newer.observation_start<=execution.observation_start
                        AND newer.observation_end>=execution.observation_end
                  ) THEN 30 ELSE 95 END
                ORDER BY execution.task_execution_id DESC
                FOR UPDATE OF execution SKIP LOCKED
                LIMIT %s
                """,
                (list(sorted(QUOTA_GUARDED_DATASETS)), limit),
            )
            for candidate in cursor.fetchall():
                execution_id = int(candidate["task_execution_id"])
                target_priority = int(candidate["target_priority"])
                cursor.execute(
                    """
                    UPDATE orchestration_v2.task_execution
                    SET priority=%s, updated_at=NOW()
                    WHERE task_execution_id=%s
                      AND status IN ('queued','retrying')
                      AND priority<>%s
                    """,
                    (target_priority, execution_id, target_priority),
                )
                if cursor.rowcount != 1:
                    continue
                self._append_event(
                    cursor,
                    execution_id,
                    event_type="execution.priority_normalized",
                    node_key=candidate.get("current_node_key"),
                    attempt_number=max(1, int(candidate["attempt_count"])),
                    event_key=(
                        f"execution.priority_normalized:{execution_id}:"
                        f"{target_priority}"
                    ),
                    payload={
                        "previous_priority": int(candidate["priority"]),
                        "priority": target_priority,
                        "reason": "quota_guarded_history_fairness",
                    },
                    evidence_references=[],
                )
                normalized += 1
        return normalized

    def retry_attention_executions(
        self,
        execution_ids: tuple[int, ...],
        *,
        reason: str,
        minimum_max_attempts: int | None = None,
    ) -> list[dict]:
        """Return explicitly selected attention executions to the durable queue."""

        if minimum_max_attempts is not None and not 1 <= minimum_max_attempts <= 100:
            raise ValueError("minimum_max_attempts must be between 1 and 100")
        if not execution_ids:
            return []
        retried: list[dict] = []
        with self._connection() as connection, self._dict_cursor(connection) as cursor:
            cursor.execute(
                """
                SELECT *
                FROM orchestration_v2.task_execution
                WHERE task_execution_id=ANY(%s)
                  AND status='attention'
                ORDER BY task_execution_id
                FOR UPDATE
                """,
                (list(execution_ids),),
            )
            for candidate in cursor.fetchall():
                execution_id = int(candidate["task_execution_id"])
                reset_data_nodes = candidate.get("final_error_category") in {
                    "data_incomplete", "completeness_guard",
                }
                node_status = dict(candidate.get("node_status") or {})
                current_node_key = candidate.get("current_node_key")
                frozen_scope = dict(candidate.get("frozen_scope") or {})
                if reset_data_nodes:
                    producer_node = (
                        "acquire"
                        if "acquire" in node_status
                        else "transform"
                        if "transform" in node_status
                        else current_node_key
                    )
                    node_order = (
                        "condition", "scope_plan", "acquire", "merge",
                        "transform", "validate", "publish",
                    )
                    producer_index = node_order.index(producer_node)
                    for node_key in tuple(node_status):
                        if (
                            node_key in node_order
                            and node_order.index(node_key) >= producer_index
                        ):
                            node_status[node_key] = "pending"
                    current_node_key = producer_node
                    if producer_node == "transform":
                        # An incomplete result must not be attached again as
                        # though this were merely publication reconciliation.
                        # Inputs may have been repaired since the failed run.
                        frozen_scope["reuse_existing_snapshot"] = False
                cursor.execute(
                    """
                    UPDATE orchestration_v2.task_execution
                    SET status='retrying', eligible_at=NOW(), finished_at=NULL,
                        max_attempts=GREATEST(
                            max_attempts,
                            attempt_count+1,
                            COALESCE(%s, max_attempts)
                        ),
                        final_error_category=NULL, final_error_message=NULL,
                        final_error_detail='{}'::jsonb,
                        current_node_key=%s,
                        node_status=%s::jsonb,
                        frozen_scope=%s::jsonb,
                        lease_owner=NULL, lease_token=NULL,
                        lease_expires_at=NULL, updated_at=NOW()
                    WHERE task_execution_id=%s AND status='attention'
                    RETURNING *
                    """,
                    (
                        minimum_max_attempts,
                        current_node_key,
                        psycopg2.extras.Json(node_status),
                        psycopg2.extras.Json(frozen_scope),
                        execution_id,
                    ),
                )
                row = cursor.fetchone()
                if not row:
                    continue
                self._append_event(
                    cursor,
                    execution_id,
                    event_type="execution.operator_retry",
                    node_key=candidate.get("current_node_key"),
                    attempt_number=max(1, int(candidate["attempt_count"])),
                    event_key=(
                        f"execution.operator_retry:{execution_id}:"
                        f"{candidate['attempt_count']}"
                    ),
                    payload={
                        "reason": reason,
                        "minimum_max_attempts": minimum_max_attempts,
                        "reset_data_nodes": reset_data_nodes,
                    },
                    evidence_references=[],
                )
                retried.append(dict(row))
        return retried

    def recover_transient_attention_executions(
        self,
        *,
        cooldown_seconds: int = 300,
        max_recovery_rounds: int = 6,
        limit: int = 100,
    ) -> list[dict]:
        """Requeue current transient failures after a bounded cool-down.

        Instance retry budgets protect an unhealthy provider from a tight
        loop, but a terminal network/rate-limit failure must not require a
        human to notice that connectivity later recovered.  Recovery rounds
        are counted from append-only execution events, capped, and skipped
        when a newer active or successful execution already covers the same
        logical scope.
        """

        if not 0 <= cooldown_seconds <= 604_800:
            raise ValueError("cooldown_seconds must be between 0 and 604800")
        if not 1 <= max_recovery_rounds <= 100:
            raise ValueError("max_recovery_rounds must be between 1 and 100")
        if not 1 <= limit <= 5000:
            raise ValueError("limit must be between 1 and 5000")
        recovered: list[dict] = []
        with self._connection() as connection, self._dict_cursor(connection) as cursor:
            cursor.execute(
                """
                SELECT failed.*,
                       COALESCE(recovery.rounds, 0) AS recovery_rounds
                FROM orchestration_v2.task_execution AS failed
                LEFT JOIN LATERAL (
                    SELECT count(*)::integer AS rounds
                    FROM orchestration_v2.task_execution_event AS event
                    WHERE event.task_execution_id=failed.task_execution_id
                      AND event.event_type='execution.auto_retry_transient'
                ) AS recovery ON true
                WHERE failed.status='attention'
                  AND failed.final_error_category IN (
                      'network', 'provider_transient', 'rate_limited',
                      'database_transient', 'lease_expired'
                  )
                  AND failed.finished_at <=
                      NOW()-(%s * INTERVAL '1 second')
                  AND COALESCE(recovery.rounds, 0) < %s
                  AND NOT EXISTS (
                      SELECT 1
                      FROM orchestration_v2.task_execution AS newer
                      WHERE newer.task_key=failed.task_key
                        AND newer.task_execution_id>failed.task_execution_id
                        AND (
                          newer.status IN (
                            'created','queued','running','waiting_dependency',
                            'retrying','validating','publishing','success'
                          )
                          OR (
                            newer.status='attention'
                            AND newer.final_error_category IN (
                              'network','provider_transient','rate_limited',
                              'database_transient','lease_expired'
                            )
                          )
                        )
                        AND (
                            newer.observation_key=failed.observation_key
                            OR (
                                newer.observation_start IS NOT NULL
                                AND newer.observation_end IS NOT NULL
                                AND failed.observation_start IS NOT NULL
                                AND failed.observation_end IS NOT NULL
                                AND newer.observation_start<=failed.observation_start
                                AND newer.observation_end>=failed.observation_end
                            )
                        )
                  )
                ORDER BY failed.finished_at, failed.task_execution_id
                LIMIT %s
                FOR UPDATE OF failed SKIP LOCKED
                """,
                (cooldown_seconds, max_recovery_rounds, limit),
            )
            for candidate in cursor.fetchall():
                execution_id = int(candidate["task_execution_id"])
                recovery_round = int(candidate["recovery_rounds"]) + 1
                previous_category = candidate.get("final_error_category")
                previous_message = candidate.get("final_error_message")
                cursor.execute(
                    """
                    UPDATE orchestration_v2.task_execution
                    SET status='retrying', eligible_at=NOW(), finished_at=NULL,
                        max_attempts=GREATEST(max_attempts,attempt_count+1),
                        final_error_category=NULL, final_error_message=NULL,
                        final_error_detail=final_error_detail ||
                            jsonb_build_object(
                                'auto_recovery_round', %s,
                                'last_transient_error_category', %s,
                                'last_transient_error_message', %s
                            ),
                        lease_owner=NULL, lease_token=NULL,
                        lease_expires_at=NULL, updated_at=NOW()
                    WHERE task_execution_id=%s AND status='attention'
                    RETURNING *
                    """,
                    (
                        recovery_round,
                        previous_category,
                        (previous_message or "")[:4000],
                        execution_id,
                    ),
                )
                row = cursor.fetchone()
                if not row:
                    continue
                self._append_event(
                    cursor,
                    execution_id,
                    event_type="execution.auto_retry_transient",
                    node_key=candidate.get("current_node_key"),
                    attempt_number=max(1, int(candidate["attempt_count"])),
                    event_key=(
                        f"execution.auto_retry_transient:{execution_id}:"
                        f"{recovery_round}"
                    ),
                    payload={
                        "recovery_round": recovery_round,
                        "max_recovery_rounds": max_recovery_rounds,
                        "cooldown_seconds": cooldown_seconds,
                        "previous_error_category": previous_category,
                    },
                    evidence_references=[],
                )
                recovered.append(dict(row))
        return recovered

    def checkpoint_execution(
        self,
        execution_id: int,
        *,
        worker_id: str,
        lease_token: str,
        current_node_key: str,
        node_status: dict[str, str],
        frozen_scope: dict[str, Any] | None = None,
        collected: bool = False,
    ) -> dict:
        """Persist node progress without manufacturing child executions.

        The compare-and-set lease guard makes the checkpoint safe when a stale
        worker resumes after another worker has reclaimed the execution.
        """
        scope_digest = (
            canonical_digest(frozen_scope) if frozen_scope is not None else None
        )
        with self._connection() as connection, self._dict_cursor(connection) as cursor:
            cursor.execute(
                """
                UPDATE orchestration_v2.task_execution
                SET current_node_key=%s,
                    node_status=%s::jsonb,
                    frozen_scope=COALESCE(%s::jsonb,frozen_scope),
                    scope_digest=COALESCE(%s,scope_digest),
                    collected_at=CASE WHEN %s THEN NOW() ELSE collected_at END,
                    updated_at=NOW()
                WHERE task_execution_id=%s
                  AND lease_owner=%s AND lease_token=%s
                  AND status IN ('running','validating','publishing')
                  AND lease_expires_at > NOW()
                RETURNING *
                """,
                (
                    current_node_key,
                    json.dumps(node_status, ensure_ascii=False),
                    (
                        json.dumps(frozen_scope, ensure_ascii=False)
                        if frozen_scope is not None else None
                    ),
                    scope_digest,
                    collected,
                    execution_id,
                    worker_id,
                    lease_token,
                ),
            )
            row = cursor.fetchone()
            if not row:
                raise RuntimeError("execution checkpoint lost its lease")
            return dict(row)

    def claim_next(
        self,
        *,
        worker_id: str,
        resource_classes: Iterable[str],
        lease_seconds: int = 120,
        execution_ids: tuple[int, ...] | None = None,
        short_only: bool = False,
    ) -> dict | None:
        classes = tuple(resource_classes)
        if not classes:
            return None
        if lease_seconds <= 0:
            raise ValueError("lease_seconds must be positive")
        lease_token = secrets.token_hex(24)
        with self._connection() as connection, self._dict_cursor(connection) as cursor:
            # Serialize only the short claim transaction, not execution.
            # Row SKIP LOCKED alone cannot protect a provider-wide NOT EXISTS
            # predicate when two workers claim different rows concurrently.
            cursor.execute("SELECT pg_advisory_xact_lock(73124, 1)")
            cursor.execute(
                """
                WITH task_recency AS (
                    SELECT task_key, MAX(started_at) AS last_started_at
                    FROM orchestration_v2.task_execution
                    WHERE resource_class = ANY(%s)
                    GROUP BY task_key
                ), candidate AS (
                    SELECT queued.task_execution_id
                    FROM orchestration_v2.task_execution AS queued
                    LEFT JOIN task_recency AS recency
                      ON recency.task_key=queued.task_key
                    WHERE queued.status IN ('queued','retrying')
                      AND queued.eligible_at <= NOW()
                      AND queued.attempt_count < queued.max_attempts
                      AND queued.resource_class = ANY(%s)
                      AND (%s::bigint[] IS NULL OR queued.task_execution_id=ANY(%s::bigint[]))
                      AND (NOT %s OR (queued.task_key <> 'share_float' AND EXISTS (
                          SELECT 1 FROM orchestration_v2.task_definition short_definition
                          WHERE short_definition.task_definition_id=queued.task_definition_id
                            AND short_definition.definition->'scope_contract'->>'cadence'='daily'
                      )))
                      -- The mutex is symmetric across routine and historical
                      -- pools. A daily arrival must not overlap an already
                      -- running full-market factor transform either.
                      AND NOT (
                        queued.task_key='local_factor_snapshot'
                        AND EXISTS (
                          SELECT 1 FROM orchestration_v2.task_execution busy
                          WHERE busy.task_key=queued.task_key
                            AND busy.status IN ('running','validating','publishing')
                        )
                      )
                      -- Historical factors run only overnight, with one full
                      -- hour of headroom before the daytime collection window.
                      AND (queued.resource_class <> 'factor-backfill' OR (
                        ((NOW() AT TIME ZONE 'Asia/Shanghai')::time >= TIME '21:00'
                         OR (NOW() AT TIME ZONE 'Asia/Shanghai')::time < TIME '06:00')
                        AND NOT EXISTS (
                          SELECT 1 FROM orchestration_v2.task_execution routine
                          WHERE routine.resource_class='derived'
                            AND routine.status IN ('queued','retrying','running','validating','publishing')
                            AND routine.eligible_at <= NOW()
                        )
                        AND NOT EXISTS (
                          SELECT 1 FROM orchestration_v2.task_execution active_factor
                          WHERE active_factor.task_key='local_factor_snapshot'
                            AND active_factor.status IN ('running','validating','publishing')
                        )
                      ))
                      -- factor_value needs about 202 calls for one complete
                      -- market date and has a 1,000-call daily allowance.
                      -- Let the 19:15 routine partition reserve its calls
                      -- before historical dates consume the remaining quota.
                      AND NOT (
                        queued.task_key='factor_value'
                        AND queued.purpose IN (
                          'initialization','backfill','repair'
                        )
                        AND (NOW() AT TIME ZONE 'Asia/Shanghai')::time
                            < TIME '20:00:00'
                      )
                      -- us_daily has a provider-enforced one-call-per-hour
                      -- window.  Do not lease another execution merely to
                      -- discover the shared slot is still closed; the runtime
                      -- can wait inline when the boundary is within 15s.
                      AND NOT (
                        queued.task_key='us_daily'
                        AND EXISTS (
                          SELECT 1 FROM sys_tushare_rate_limit AS rate_slot
                          WHERE rate_slot.api_name='us_daily'
                            AND rate_slot.next_allowed_at >
                                NOW() + INTERVAL '15 seconds'
                        )
                      )
                      AND NOT (
                        queued.task_key = ANY(%s)
                        AND EXISTS (
                          SELECT 1
                          FROM orchestration_v2.task_execution AS active
                          WHERE active.task_key=queued.task_key
                            AND active.task_execution_id<>queued.task_execution_id
                            AND active.status IN (
                              'running','validating','publishing'
                            )
                        )
                      )
                      -- Financial Data scheduled pulls share one provider
                      -- quota and some full-market routes perform dozens of
                      -- protocol requests inside a single acquire node.  A
                      -- task-level serial gate prevents distinct ant_* tasks
                      -- from stampeding the same credential.  The task still
                      -- owns its entire market sweep and validation lifecycle;
                      -- this does not create child executions.
                      AND NOT (
                        queued.task_key LIKE 'ant\\_%%' ESCAPE '\\'
                        AND EXISTS (
                          SELECT 1
                          FROM orchestration_v2.task_execution AS active
                          WHERE active.task_execution_id<>
                                queued.task_execution_id
                            AND active.task_key LIKE 'ant\\_%%' ESCAPE '\\'
                            AND active.status IN (
                              'running','validating','publishing'
                            )
                        )
                      )
                      AND NOT (
                        queued.task_key = ANY(%s)
                        AND EXISTS (
                          SELECT 1
                          FROM orchestration_v2.task_execution AS covering
                          WHERE covering.task_key=queued.task_key
                            AND covering.task_execution_id>
                                queued.task_execution_id
                            AND covering.status IN (
                              'created','queued','running',
                              'waiting_dependency','retrying','validating',
                              'publishing','success'
                            )
                            AND covering.observation_start<=
                                queued.observation_start
                            AND covering.observation_end>=
                                queued.observation_end
                        )
                      )
                    ORDER BY queued.priority DESC,
                             CASE WHEN queued.status='retrying' THEN 0 ELSE 1 END,
                             recency.last_started_at NULLS FIRST,
                             queued.eligible_at,
                             queued.task_execution_id
                    FOR UPDATE OF queued SKIP LOCKED
                    LIMIT 1
                )
                UPDATE orchestration_v2.task_execution AS execution
                SET status='running', lease_owner=%s, lease_token=%s,
                    lease_expires_at=NOW()+(%s * INTERVAL '1 second'),
                    attempt_count=attempt_count+1,
                    started_at=COALESCE(started_at,NOW()), updated_at=NOW()
                FROM candidate
                WHERE execution.task_execution_id=candidate.task_execution_id
                RETURNING execution.*
                """,
                (
                    list(classes),
                    list(classes),
                    list(execution_ids) if execution_ids is not None else None,
                    list(execution_ids) if execution_ids is not None else None,
                    short_only,
                    list(sorted(SERIALIZED_ACQUISITION_TASKS)),
                    list(sorted(QUOTA_GUARDED_DATASETS)),
                    worker_id,
                    lease_token,
                    lease_seconds,
                ),
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def reclaim_expired_leases(self, *, limit: int = 100) -> list[dict]:
        """Recover abandoned executions without creating duplicate work.

        Each execution is locked before its lease is evaluated.  A run with
        retry budget remaining returns to ``retrying``; an exhausted run moves
        to ``attention``.  The recovery fact is appended in the same
        transaction so operators never see a silent state rewrite.
        """
        if limit < 1 or limit > 10_000:
            raise ValueError("limit must be between 1 and 10000")

        recovered: list[dict] = []
        with self._connection() as connection, self._dict_cursor(connection) as cursor:
            cursor.execute(
                """
                SELECT *
                FROM orchestration_v2.task_execution
                WHERE status IN ('running','validating','publishing')
                  AND lease_expires_at <= NOW()
                ORDER BY lease_expires_at, task_execution_id
                FOR UPDATE SKIP LOCKED
                LIMIT %s
                """,
                (limit,),
            )
            expired = [dict(row) for row in cursor.fetchall()]
            for execution in expired:
                exhausted = execution["attempt_count"] >= execution["max_attempts"]
                target_status = "attention" if exhausted else "retrying"
                cursor.execute(
                    """
                    UPDATE orchestration_v2.task_execution
                    SET status=%s,
                        eligible_at=CASE WHEN %s THEN eligible_at ELSE NOW() END,
                        lease_owner=NULL, lease_token=NULL, lease_expires_at=NULL,
                        final_error_category='lease_expired',
                        final_error_message='worker lease expired before completion',
                        final_error_detail=jsonb_build_object(
                            'expired_owner', %s,
                            'expired_at', %s,
                            'attempt', %s,
                            'max_attempts', %s
                        ),
                        finished_at=CASE WHEN %s THEN NOW() ELSE NULL END,
                        updated_at=NOW()
                    WHERE task_execution_id=%s
                    RETURNING *
                    """,
                    (
                        target_status,
                        exhausted,
                        execution["lease_owner"],
                        execution["lease_expires_at"],
                        execution["attempt_count"],
                        execution["max_attempts"],
                        exhausted,
                        execution["task_execution_id"],
                    ),
                )
                updated = dict(cursor.fetchone())
                self._append_event(
                    cursor,
                    execution["task_execution_id"],
                    event_type="execution.lease_expired",
                    node_key=execution["current_node_key"],
                    attempt_number=execution["attempt_count"],
                    event_key=(
                        f"execution.lease_expired:{execution['task_execution_id']}:"
                        f"{execution['attempt_count']}"
                    ),
                    payload={
                        "previous_status": execution["status"],
                        "recovered_status": target_status,
                        "expired_owner": execution["lease_owner"],
                        "expired_at": execution["lease_expires_at"].isoformat(),
                        "retry_budget_exhausted": exhausted,
                    },
                    evidence_references=[],
                )
                recovered.append(updated)
        return recovered

    def get_execution(self, execution_id: int) -> dict | None:
        with self._connection() as connection, self._dict_cursor(connection) as cursor:
            cursor.execute(
                """
                SELECT execution.*,
                       NOT EXISTS (
                           SELECT 1
                           FROM orchestration_v2.task_execution AS newer
                           WHERE newer.task_key=execution.task_key
                             AND newer.observation_key=execution.observation_key
                             AND newer.task_execution_id>
                                 execution.task_execution_id
                       ) AS is_current_scope_execution,
                       (
                           SELECT max(newer.task_execution_id)
                           FROM orchestration_v2.task_execution AS newer
                           WHERE newer.task_key=execution.task_key
                             AND newer.observation_key=execution.observation_key
                       ) AS latest_scope_execution_id
                FROM orchestration_v2.task_execution AS execution
                WHERE execution.task_execution_id=%s
                """,
                (execution_id,),
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def transition_execution(
        self,
        execution_id: int,
        *,
        expected_status: ExecutionStatus,
        target_status: ExecutionStatus,
        worker_id: str | None = None,
        lease_token: str | None = None,
        current_node_key: str | None = None,
        node_status: dict[str, str] | None = None,
        eligible_at: datetime | None = None,
        error_category: str | None = None,
        error_message: str | None = None,
        error_detail: dict[str, Any] | None = None,
    ) -> dict:
        terminal = target_status in {
            ExecutionStatus.SUCCESS,
            ExecutionStatus.ATTENTION,
            ExecutionStatus.SUPERSEDED,
            ExecutionStatus.CANCELLED,
        }
        release_lease = terminal or target_status in {
            ExecutionStatus.QUEUED,
            ExecutionStatus.RETRYING,
            ExecutionStatus.WAITING_DEPENDENCY,
        }
        lease_filter = ""
        params: list[Any] = [
            target_status,
            current_node_key,
            json.dumps(node_status, ensure_ascii=False) if node_status is not None else None,
            eligible_at,
            error_category,
            error_message,
            json.dumps(error_detail or {}, ensure_ascii=False),
            terminal,
            release_lease,
            release_lease,
            release_lease,
            execution_id,
            expected_status,
        ]
        if worker_id is not None or lease_token is not None:
            if not worker_id or not lease_token:
                raise ValueError("worker_id and lease_token must be supplied together")
            lease_filter = " AND lease_owner=%s AND lease_token=%s"
            params.extend([worker_id, lease_token])
        with self._connection() as connection, self._dict_cursor(connection) as cursor:
            cursor.execute(
                """
                UPDATE orchestration_v2.task_execution
                SET status=%s,
                    current_node_key=COALESCE(%s,current_node_key),
                    node_status=COALESCE(%s::jsonb,node_status),
                    eligible_at=COALESCE(%s,eligible_at),
                    final_error_category=%s, final_error_message=%s,
                    final_error_detail=%s::jsonb,
                    finished_at=CASE WHEN %s THEN NOW() ELSE NULL END,
                    lease_owner=CASE WHEN %s THEN NULL ELSE lease_owner END,
                    lease_token=CASE WHEN %s THEN NULL ELSE lease_token END,
                    lease_expires_at=CASE WHEN %s THEN NULL ELSE lease_expires_at END,
                    updated_at=NOW()
                WHERE task_execution_id=%s AND status=%s
                """ + lease_filter + " RETURNING *",
                tuple(params),
            )
            row = cursor.fetchone()
            if not row:
                raise RuntimeError("execution transition lost its status or lease compare-and-set")
            if target_status == ExecutionStatus.SUCCESS:
                # A fresh repair execution owns the final truth for this
                # logical scope.  Keeping older attention rows active after
                # the same task/date is strictly ready makes the exception
                # center contradict the data calendar.  Preserve history but
                # close those obsolete alerts as superseded, with an event
                # pointing at the successful replacement.
                cursor.execute(
                    """
                    UPDATE orchestration_v2.task_execution
                    SET status='superseded', finished_at=NOW(),
                        final_error_category='recovered_by_later_execution',
                        final_error_message=%s,
                        final_error_detail=final_error_detail ||
                            jsonb_build_object(
                                'recovered_by_execution_id', %s,
                                'corrective_action', 'superseded_after_verified_repair'
                            ),
                        lease_owner=NULL, lease_token=NULL,
                        lease_expires_at=NULL, updated_at=NOW()
                    WHERE task_key=%s
                      AND task_execution_id<>%s AND status='attention'
                      AND (
                        observation_key=%s
                        OR (
                          %s::date IS NOT NULL AND %s::date IS NOT NULL
                          AND observation_start IS NOT NULL
                          AND observation_end IS NOT NULL
                          AND observation_start >= %s::date
                          AND observation_end <= %s::date
                        )
                      )
                    RETURNING task_execution_id, current_node_key, attempt_count
                    """,
                    (
                        f"recovered by successful execution {execution_id}",
                        execution_id,
                        row["task_key"],
                        execution_id,
                        row["observation_key"],
                        row.get("observation_start"),
                        row.get("observation_end"),
                        row.get("observation_start"),
                        row.get("observation_end"),
                    ),
                )
                for resolved in cursor.fetchall():
                    resolved_id = int(resolved["task_execution_id"])
                    self._append_event(
                        cursor,
                        resolved_id,
                        event_type="execution.superseded_after_verified_repair",
                        node_key=resolved.get("current_node_key"),
                        attempt_number=max(1, int(resolved["attempt_count"])),
                        event_key=(
                            "execution.superseded_after_verified_repair:"
                            f"{resolved_id}:{execution_id}"
                        ),
                        payload={"recovered_by_execution_id": execution_id},
                        evidence_references=[{
                            "task_execution_id": execution_id,
                            "event": "execution.success",
                        }],
                    )
            return dict(row)

    @staticmethod
    def _append_event(
        cursor,
        execution_id: int,
        *,
        event_type: str,
        node_key: str | None,
        attempt_number: int | None,
        event_key: str | None,
        payload: dict[str, Any],
        evidence_references: list[dict[str, Any]],
    ) -> dict:
        # Locking the execution serializes sequence allocation without a sixth
        # counter table and without rewriting an events JSONB hot row.
        cursor.execute(
            """
            SELECT task_execution_id FROM orchestration_v2.task_execution
            WHERE task_execution_id=%s FOR UPDATE
            """,
            (execution_id,),
        )
        if not cursor.fetchone():
            raise LookupError(f"task execution not found: {execution_id}")
        cursor.execute(
            """
            SELECT COALESCE(MAX(sequence_number),0)+1 AS next_sequence
            FROM orchestration_v2.task_execution_event
            WHERE task_execution_id=%s
            """,
            (execution_id,),
        )
        sequence_number = cursor.fetchone()["next_sequence"]
        cursor.execute(
            """
            INSERT INTO orchestration_v2.task_execution_event(
                task_execution_id, sequence_number, event_type, node_key,
                attempt_number, event_key, payload, evidence_references
            ) VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb)
            RETURNING *
            """,
            (
                execution_id,
                sequence_number,
                event_type,
                node_key,
                attempt_number,
                event_key,
                json.dumps(payload, ensure_ascii=False),
                json.dumps(evidence_references, ensure_ascii=False),
            ),
        )
        return dict(cursor.fetchone())

    def append_event(
        self,
        execution_id: int,
        *,
        event_type: str,
        node_key: str | None = None,
        attempt_number: int | None = None,
        event_key: str | None = None,
        payload: dict[str, Any] | None = None,
        evidence_references: list[dict[str, Any]] | None = None,
    ) -> dict:
        with self._connection() as connection, self._dict_cursor(connection) as cursor:
            return self._append_event(
                cursor,
                execution_id,
                event_type=event_type,
                node_key=node_key,
                attempt_number=attempt_number,
                event_key=event_key,
                payload=payload or {},
                evidence_references=evidence_references or [],
            )

    def _publish_dataset_state_locked(
        self,
        cursor,
        execution: dict,
        execution_id: int,
        update: DatasetStateUpdate,
        *,
        validation_payload: dict[str, Any],
        evidence_references: list[dict[str, Any]] | None = None,
    ) -> dict:
        """Append validation/state events and upsert one dataset_state row.

        The caller owns the transaction and has already locked the execution
        row; this helper only performs the append-only writes.
        """
        scope_digest = canonical_digest(update.scope)
        published_at = datetime.now().astimezone() if update.ready else None
        validation = self._append_event(
            cursor,
            execution_id,
            event_type="dataset.validation.completed",
            node_key="validate",
            attempt_number=None,
            event_key=None,
            payload=validation_payload,
            evidence_references=evidence_references or [],
        )
        event_type = "dataset.ready" if update.ready else "dataset.state.updated"
        state_event = self._append_event(
            cursor,
            execution_id,
            event_type=event_type,
            node_key="publish",
            attempt_number=None,
            event_key=(
                f"{event_type}:{execution_id}:{update.dataset_name}:"
                f"{update.observation_key}:{scope_digest}:{update.contract_version}:"
                f"attempt-{execution['attempt_count']}"
            ),
            payload={
                "dataset_name": update.dataset_name,
                "observation_key": update.observation_key,
                "scope_digest": scope_digest,
                "contract_version": update.contract_version,
                "data_status": update.data_status.value,
                "validation_event_id": validation["event_id"],
            },
            evidence_references=[],
        )
        cursor.execute(
            """
            INSERT INTO orchestration_v2.dataset_state(
                dataset_name, observation_key, observation_start,
                observation_end, observation_period, publication_date,
                available_at, collected_at, scope, scope_digest,
                contract_version, expectation_status, data_status, ready,
                expected_count, actual_count, gap_summary,
                validation_summary, source_execution_id,
                validation_event_id, published_at
            ) VALUES (
                %s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s,%s,%s,%s,%s,
                %s::jsonb,%s::jsonb,%s,%s,%s
            )
            ON CONFLICT (
                dataset_name, observation_key, scope_digest
            ) DO UPDATE SET
                observation_start=EXCLUDED.observation_start,
                observation_end=EXCLUDED.observation_end,
                observation_period=EXCLUDED.observation_period,
                publication_date=EXCLUDED.publication_date,
                available_at=EXCLUDED.available_at,
                collected_at=EXCLUDED.collected_at,
                scope=EXCLUDED.scope,
                contract_version=EXCLUDED.contract_version,
                expectation_status=EXCLUDED.expectation_status,
                data_status=EXCLUDED.data_status,
                ready=EXCLUDED.ready,
                expected_count=EXCLUDED.expected_count,
                actual_count=EXCLUDED.actual_count,
                gap_summary=EXCLUDED.gap_summary,
                validation_summary=EXCLUDED.validation_summary,
                source_execution_id=EXCLUDED.source_execution_id,
                validation_event_id=EXCLUDED.validation_event_id,
                published_at=EXCLUDED.published_at,
                revision=orchestration_v2.dataset_state.revision+1,
                updated_at=NOW()
            RETURNING *
            """,
            (
                update.dataset_name,
                update.observation_key,
                update.observation_start,
                update.observation_end,
                update.observation_period,
                update.publication_date,
                update.available_at,
                update.collected_at,
                json.dumps(update.scope, ensure_ascii=False),
                scope_digest,
                update.contract_version,
                update.expectation_status,
                update.data_status,
                update.ready,
                update.expected_count,
                update.actual_count,
                json.dumps(update.gap_summary, ensure_ascii=False),
                json.dumps(update.validation_summary, ensure_ascii=False),
                execution_id,
                validation["event_id"],
                published_at,
            ),
        )
        state = dict(cursor.fetchone())
        state["publication_event_id"] = state_event["event_id"]
        return state

    @staticmethod
    def _locked_publishable_execution(cursor, execution_id: int) -> dict:
        cursor.execute(
            """
            SELECT status, attempt_count FROM orchestration_v2.task_execution
            WHERE task_execution_id=%s FOR UPDATE
            """,
            (execution_id,),
        )
        execution = cursor.fetchone()
        if not execution:
            raise LookupError(f"task execution not found: {execution_id}")
        if execution["status"] not in {"validating", "publishing"}:
            raise ValueError("dataset state may only be published after validation")
        return dict(execution)

    def publish_dataset_state(
        self,
        execution_id: int,
        update: DatasetStateUpdate,
        *,
        validation_payload: dict[str, Any],
        evidence_references: list[dict[str, Any]] | None = None,
    ) -> dict:
        with self._connection() as connection, self._dict_cursor(connection) as cursor:
            execution = self._locked_publishable_execution(cursor, execution_id)
            return self._publish_dataset_state_locked(
                cursor,
                execution,
                execution_id,
                update,
                validation_payload=validation_payload,
                evidence_references=evidence_references,
            )

    def publish_dataset_states(
        self,
        execution_id: int,
        publications: list[
            tuple[
                DatasetStateUpdate,
                dict[str, Any],
                list[dict[str, Any]] | None,
            ]
        ],
    ) -> list[dict]:
        """Publish every dataset state of one execution in a single transaction.

        Multi-output tasks (for example weekly+monthly bars) must not end up
        with some datasets ready while others failed mid-publication; either
        the whole batch commits or none of it does.
        """
        states: list[dict] = []
        with self._connection() as connection, self._dict_cursor(connection) as cursor:
            execution = self._locked_publishable_execution(cursor, execution_id)
            for update, validation_payload, evidence_references in publications:
                states.append(
                    self._publish_dataset_state_locked(
                        cursor,
                        execution,
                        execution_id,
                        update,
                        validation_payload=validation_payload,
                        evidence_references=evidence_references,
                    )
                )
        return states

    def renew_lease(
        self,
        execution_id: int,
        *,
        worker_id: str,
        lease_token: str,
        lease_seconds: int = 120,
    ) -> datetime:
        if lease_seconds <= 0:
            raise ValueError("lease_seconds must be positive")
        with self._connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE orchestration_v2.task_execution
                SET lease_expires_at=NOW()+(%s * INTERVAL '1 second'),
                    updated_at=NOW()
                WHERE task_execution_id=%s AND lease_owner=%s AND lease_token=%s
                  AND status IN ('running','validating','publishing')
                  AND lease_expires_at > NOW()
                RETURNING lease_expires_at
                """,
                (lease_seconds, execution_id, worker_id, lease_token),
            )
            row = cursor.fetchone()
            if not row:
                raise RuntimeError("execution lease was lost")
            return row[0]

    def defer_execution(
        self,
        execution_id: int,
        *,
        delay: timedelta,
        worker_id: str,
        lease_token: str,
        node_status: dict[str, str] | None = None,
        reason: str = "resource slot deferred",
    ) -> dict:
        if delay.total_seconds() < 0:
            raise ValueError("delay must not be negative")
        eligible_at = datetime.now().astimezone() + delay
        with self._connection() as connection, self._dict_cursor(connection) as cursor:
            cursor.execute(
                """
                UPDATE orchestration_v2.task_execution
                SET status='retrying', eligible_at=%s,
                    attempt_count=GREATEST(attempt_count-1,0),
                    node_status=COALESCE(%s::jsonb,node_status),
                    lease_owner=NULL, lease_token=NULL, lease_expires_at=NULL,
                    final_error_category=NULL, final_error_message=NULL,
                    final_error_detail='{}'::jsonb, updated_at=NOW()
                WHERE task_execution_id=%s AND status='running'
                  AND lease_owner=%s AND lease_token=%s
                RETURNING *
                """,
                (
                    eligible_at,
                    json.dumps(node_status, ensure_ascii=False)
                    if node_status is not None else None,
                    execution_id,
                    worker_id,
                    lease_token,
                ),
            )
            row = cursor.fetchone()
            if not row:
                raise RuntimeError("execution deferral lost its running lease")
            updated = dict(row)
            # Claiming an execution increments ``attempt_count``.  A pure
            # resource/quota deferral deliberately gives that retry budget
            # back before this event is appended, so the persisted counter
            # may be zero here.  Event attempts are historical facts about
            # the claim that just ran and the database contract requires a
            # positive number; reconstruct the claimed attempt instead of
            # copying the post-refund counter.
            deferred_attempt_number = max(
                1,
                int(updated["attempt_count"]) + 1,
            )
            self._append_event(
                cursor,
                execution_id,
                event_type="execution.deferred",
                node_key=updated.get("current_node_key"),
                attempt_number=deferred_attempt_number,
                event_key=None,
                payload={
                    "reason": reason[:4000],
                    "retry_after_seconds": int(delay.total_seconds()),
                    "eligible_at": eligible_at.isoformat(),
                    "attempt_consumed": False,
                },
                evidence_references=[],
            )
            return updated
