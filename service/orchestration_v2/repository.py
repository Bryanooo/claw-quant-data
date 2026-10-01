"""PostgreSQL persistence for the isolated V2 orchestration control plane."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from contextlib import contextmanager
from datetime import datetime, timedelta
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
    TaskDefinitionDocument,
    canonical_digest,
)


class OrchestrationV2Repository:
    """Small transactional repository; it does not activate the V2 engine."""

    _CONTROL_TABLES = frozenset({
        "acquisition_endpoint",
        "task_definition",
        "task_execution",
        "task_execution_event",
        "dataset_state",
    })

    def __init__(self, connection_factory: Callable[..., Any] = psycopg2.connect):
        self._connection_factory = connection_factory

    @contextmanager
    def _connection(self):
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
        where = " WHERE " + " AND ".join(conditions) if conditions else ""
        params.append(limit)
        with self._connection() as connection, self._dict_cursor(connection) as cursor:
            cursor.execute(
                """
                SELECT task_definition_id, task_key, version, lifecycle_status,
                       workflow_kind, definition_digest, app_revision, image_digest,
                       definition->'input_datasets' AS input_datasets,
                       definition->'output_datasets' AS output_datasets,
                       jsonb_array_length(definition->'nodes') AS node_count,
                       created_by, activated_by, created_at, activated_at, retired_at
                FROM orchestration_v2.task_definition
                """ + where + " ORDER BY task_definition_id DESC LIMIT %s",
                tuple(params),
            )
            return [dict(row) for row in cursor.fetchall()]

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
                SELECT task_execution_id, task_definition_id, task_key,
                       definition_version, purpose, trigger_source, status,
                       observation_key, observation_start, observation_end,
                       publication_date, data_available_at, collected_at,
                       current_node_key, node_status, priority, resource_class,
                       attempt_count, max_attempts, eligible_at, lease_owner,
                       lease_expires_at, final_error_category, final_error_message,
                       created_at, started_at, finished_at, updated_at
                FROM orchestration_v2.task_execution
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
                  AND payload->>'completion_status' IN ('complete','empty')
                  AND COALESCE(
                          (payload->'completion_evidence'->>'verified')::BOOLEAN,
                          false
                      )
                ORDER BY COALESCE(payload->>'request_key', event_id::TEXT),
                         sequence_number DESC
                """,
                (execution_id,),
            )
            return [dict(row["payload"] or {}) for row in cursor.fetchall()]

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
        for item in items:
            now = business_now()
            next_morning_release = datetime.combine(
                observation_date + timedelta(days=1),
                NEXT_MORNING_TASK_RELEASE_TIME,
                tzinfo=now.tzinfo,
            )
            if (
                item["status"] == "not_dispatched"
                and item["task_key"] in NEXT_MORNING_TASKS
                and now < next_morning_release
            ):
                item["status"] = "not_due"
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
        return {
            "engine": "orchestration_v2",
            "data_date": observation_date,
            "summary": {
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
                """,
                (request.task_key,),
            )
            definition = cursor.fetchone()
            if not definition:
                raise LookupError(f"active task definition not found: {request.task_key}")
            cursor.execute(
                """
                SELECT * FROM orchestration_v2.task_execution
                WHERE task_key=%s AND observation_key=%s
                  AND status IN (
                    'created','queued','running','waiting_dependency','retrying',
                    'validating','publishing'
                  )
                ORDER BY task_execution_id DESC
                LIMIT 1
                FOR UPDATE
                """,
                (request.task_key, request.observation_key),
            )
            active_scope = cursor.fetchone()
            if active_scope:
                return dict(active_scope), False
            historical = request.purpose.value in {
                "initialization", "backfill", "repair"
            }
            resource_class = (
                "v2-backfill"
                if historical
                else definition["definition"]["resource"]["resource_class"]
            )
            priority = (
                95
                if request.purpose.value == "repair"
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
            cursor.execute(
                """
                SELECT * FROM orchestration_v2.task_execution
                WHERE idempotency_key=%s
                   OR (
                        task_key=%s AND observation_key=%s
                    AND status IN (
                        'created','queued','running','waiting_dependency',
                        'retrying','validating','publishing'
                    )
                   )
                ORDER BY (idempotency_key=%s) DESC, task_execution_id DESC
                LIMIT 1
                """,
                (
                    request.idempotency_key,
                    request.task_key,
                    request.observation_key,
                    request.idempotency_key,
                ),
            )
            existing = cursor.fetchone()
            if not existing:
                raise RuntimeError("execution insert conflicted but owner was not found")
            return dict(existing), False

    def reopen_daily_without_transport(self, observation_date) -> list[dict]:
        """Correct a false terminal daily run that skipped acquisition.

        This is intentionally narrower than a generic terminal-state retry:
        only successful daily executions with no completed acquire request are
        eligible. The correction and invalidation of their published dataset
        state are recorded atomically and visibly in the event stream.
        """

        reopened: list[dict] = []
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
                  AND execution.status='success'
                  AND NOT EXISTS (
                      SELECT 1
                      FROM orchestration_v2.task_execution_event AS event
                      WHERE event.task_execution_id=execution.task_execution_id
                        AND event.event_type='node.acquire.request_completed'
                  )
                ORDER BY execution.task_execution_id
                FOR UPDATE OF execution
                """,
                (observation_date, observation_date),
            )
            candidates = list(cursor.fetchall())
            for candidate in candidates:
                nodes = candidate["definition"].get("nodes", [])
                node_status = {node["key"]: "pending" for node in nodes}
                if nodes:
                    node_status[nodes[0]["key"]] = "ready"
                cursor.execute(
                    """
                    UPDATE orchestration_v2.task_execution
                    SET status='queued', current_node_key=%s,
                        node_status=%s::jsonb, eligible_at=NOW(),
                        finished_at=NULL, final_error_category=NULL,
                        final_error_message=NULL, final_error_detail='{}'::jsonb,
                        lease_owner=NULL, lease_token=NULL, lease_expires_at=NULL,
                        updated_at=NOW()
                    WHERE task_execution_id=%s AND status='success'
                    RETURNING *
                    """,
                    (
                        nodes[0]["key"] if nodes else None,
                        json.dumps(node_status, ensure_ascii=False),
                        candidate["task_execution_id"],
                    ),
                )
                row = cursor.fetchone()
                if not row:
                    continue
                cursor.execute(
                    """
                    UPDATE orchestration_v2.dataset_state
                    SET data_status='pending', ready=false,
                        validation_summary=validation_summary || jsonb_build_object(
                            'invalidated', true,
                            'invalidation_reason', 'daily_acquire_was_skipped'
                        ),
                        updated_at=NOW()
                    WHERE source_execution_id=%s
                    """,
                    (candidate["task_execution_id"],),
                )
                self._append_event(
                    cursor,
                    candidate["task_execution_id"],
                    event_type="execution.reopened_invalid_preflight",
                    node_key=nodes[0]["key"] if nodes else None,
                    attempt_number=max(1, int(candidate["attempt_count"])),
                    event_key=(
                        "execution.reopened_invalid_preflight:"
                        f"{candidate['task_execution_id']}"
                    ),
                    payload={
                        "reason": "daily_acquire_was_skipped",
                        "observation_date": observation_date.isoformat(),
                    },
                    evidence_references=[],
                )
                reopened.append(dict(row))
        return reopened

    def reopen_daily_for_revalidation(self, observation_date) -> list[dict]:
        """Re-run validation for terminal daily scopes using stored transport.

        This maintenance operation is intentionally date-bounded and preserves
        each execution identity. The runtime reuses verified acquire events,
        so no provider call is repeated merely to correct validation logic.
        """

        reopened: list[dict] = []
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
                  AND execution.status IN ('success', 'attention')
                ORDER BY execution.task_execution_id
                FOR UPDATE OF execution
                """,
                (observation_date, observation_date),
            )
            candidates = list(cursor.fetchall())
            for candidate in candidates:
                nodes = candidate["definition"].get("nodes", [])
                node_status = {node["key"]: "pending" for node in nodes}
                if nodes:
                    node_status[nodes[0]["key"]] = "ready"
                cursor.execute(
                    """
                    UPDATE orchestration_v2.task_execution
                    SET status='queued', current_node_key=%s,
                        node_status=%s::jsonb, eligible_at=NOW(),
                        max_attempts=GREATEST(max_attempts,attempt_count+1),
                        finished_at=NULL, final_error_category=NULL,
                        final_error_message=NULL, final_error_detail='{}'::jsonb,
                        lease_owner=NULL, lease_token=NULL, lease_expires_at=NULL,
                        updated_at=NOW()
                    WHERE task_execution_id=%s
                      AND status IN ('success', 'attention')
                    RETURNING *
                    """,
                    (
                        nodes[0]["key"] if nodes else None,
                        json.dumps(node_status, ensure_ascii=False),
                        candidate["task_execution_id"],
                    ),
                )
                row = cursor.fetchone()
                if not row:
                    continue
                cursor.execute(
                    """
                    UPDATE orchestration_v2.dataset_state
                    SET data_status='auditing', ready=false,
                        validation_summary=validation_summary || jsonb_build_object(
                            'revalidating', true,
                            'revalidation_reason', 'task_scope_must_ignore_discovery_grace'
                        ),
                        updated_at=NOW()
                    WHERE source_execution_id=%s
                    """,
                    (candidate["task_execution_id"],),
                )
                self._append_event(
                    cursor,
                    candidate["task_execution_id"],
                    event_type="execution.reopened_revalidation",
                    node_key=nodes[0]["key"] if nodes else None,
                    attempt_number=max(1, int(candidate["attempt_count"])),
                    event_key=(
                        "execution.reopened_revalidation:"
                        f"{candidate['task_execution_id']}:"
                        f"{candidate['attempt_count']}"
                    ),
                    payload={
                        "reason": "task_scope_must_ignore_discovery_grace",
                        "observation_date": observation_date.isoformat(),
                        "provider_recollection": False,
                    },
                    evidence_references=[],
                )
                reopened.append(dict(row))
        return reopened

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

    def supersede_attention_executions(
        self,
        execution_ids: tuple[int, ...],
        *,
        reason: str,
    ) -> list[dict]:
        """Supersede explicitly selected invalid scopes without deleting history.

        This is the operator-safe escape hatch for executions created from a
        definition that was later corrected (for example, a quarterly endpoint
        accidentally dispatched with a weekly scope).  Only terminal
        ``attention`` executions may be changed, so active work cannot be
        interrupted and a broad selector cannot retire healthy history.
        """

        if not execution_ids:
            return []
        superseded: list[dict] = []
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
                cursor.execute(
                    """
                    UPDATE orchestration_v2.task_execution
                    SET status='superseded', finished_at=NOW(),
                        final_error_category='invalid_scope',
                        final_error_message=%s,
                        final_error_detail=jsonb_build_object(
                            'corrective_action', 'supersede_invalid_definition_scope'
                        ),
                        lease_owner=NULL, lease_token=NULL,
                        lease_expires_at=NULL, updated_at=NOW()
                    WHERE task_execution_id=%s AND status='attention'
                    RETURNING *
                    """,
                    (reason, execution_id),
                )
                row = cursor.fetchone()
                if not row:
                    continue
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
                    event_type="execution.operator_superseded_invalid_scope",
                    node_key=candidate.get("current_node_key"),
                    attempt_number=max(1, int(candidate["attempt_count"])),
                    event_key=f"execution.operator_superseded_invalid_scope:{execution_id}",
                    payload={"reason": reason},
                    evidence_references=[],
                )
                superseded.append(dict(row))
        return superseded

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
                      AND candidate.observation_key=failed.observation_key
                      AND candidate.status='success'
                      AND candidate.task_execution_id>failed.task_execution_id
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

    def supersede_invalid_scope_executions(
        self,
        execution_ids: tuple[int, ...],
        *,
        reason: str,
    ) -> list[dict]:
        """Stop explicitly selected non-terminal work whose scope is invalid.

        This is deliberately ID-based: a rule correction may invalidate a
        large queued history plan, but operators must first resolve the exact
        executions instead of retiring work through a broad task/status
        predicate.  History and events are retained; no business rows are
        deleted.
        """

        if not execution_ids:
            return []
        superseded: list[dict] = []
        active_statuses = ("queued", "retrying", "running", "validating", "attention")
        with self._connection() as connection, self._dict_cursor(connection) as cursor:
            cursor.execute(
                """
                SELECT *
                FROM orchestration_v2.task_execution
                WHERE task_execution_id=ANY(%s)
                  AND status=ANY(%s)
                ORDER BY task_execution_id
                FOR UPDATE
                """,
                (list(execution_ids), list(active_statuses)),
            )
            for candidate in cursor.fetchall():
                execution_id = int(candidate["task_execution_id"])
                cursor.execute(
                    """
                    UPDATE orchestration_v2.task_execution
                    SET status='superseded', finished_at=NOW(),
                        final_error_category='invalid_scope',
                        final_error_message=%s,
                        final_error_detail=jsonb_build_object(
                            'corrective_action', 'supersede_invalid_coverage_scope'
                        ),
                        lease_owner=NULL, lease_token=NULL,
                        lease_expires_at=NULL, updated_at=NOW()
                    WHERE task_execution_id=%s
                      AND status=ANY(%s)
                    RETURNING *
                    """,
                    (reason, execution_id, list(active_statuses)),
                )
                row = cursor.fetchone()
                if not row:
                    continue
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
                    event_type="execution.operator_superseded_invalid_scope",
                    node_key=candidate.get("current_node_key"),
                    attempt_number=max(1, int(candidate["attempt_count"])),
                    event_key=f"execution.operator_superseded_invalid_scope:{execution_id}",
                    payload={"reason": reason},
                    evidence_references=[],
                )
                superseded.append(dict(row))
        return superseded

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
                        lease_owner=NULL, lease_token=NULL,
                        lease_expires_at=NULL, updated_at=NOW()
                    WHERE task_execution_id=%s AND status='attention'
                    RETURNING *
                    """,
                    (minimum_max_attempts, execution_id),
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
                    },
                    evidence_references=[],
                )
                retried.append(dict(row))
        return retried

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
    ) -> dict | None:
        classes = tuple(resource_classes)
        if not classes:
            return None
        if lease_seconds <= 0:
            raise ValueError("lease_seconds must be positive")
        lease_token = secrets.token_hex(24)
        with self._connection() as connection, self._dict_cursor(connection) as cursor:
            cursor.execute(
                """
                WITH candidate AS (
                    SELECT task_execution_id
                    FROM orchestration_v2.task_execution
                    WHERE status IN ('queued','retrying')
                      AND eligible_at <= NOW()
                      AND attempt_count < max_attempts
                      AND resource_class = ANY(%s)
                    ORDER BY priority DESC, eligible_at, task_execution_id
                    FOR UPDATE SKIP LOCKED
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
                (list(classes), worker_id, lease_token, lease_seconds),
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
                "SELECT * FROM orchestration_v2.task_execution "
                "WHERE task_execution_id=%s",
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
                    WHERE task_key=%s AND observation_key=%s
                      AND task_execution_id<>%s AND status='attention'
                    RETURNING task_execution_id, current_node_key, attempt_count
                    """,
                    (
                        f"recovered by successful execution {execution_id}",
                        execution_id,
                        row["task_key"],
                        row["observation_key"],
                        execution_id,
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

    def publish_dataset_state(
        self,
        execution_id: int,
        update: DatasetStateUpdate,
        *,
        validation_payload: dict[str, Any],
        evidence_references: list[dict[str, Any]] | None = None,
    ) -> dict:
        scope_digest = canonical_digest(update.scope)
        published_at = datetime.now().astimezone() if update.ready else None
        with self._connection() as connection, self._dict_cursor(connection) as cursor:
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
            self._append_event(
                cursor,
                execution_id,
                event_type="execution.deferred",
                node_key=updated.get("current_node_key"),
                attempt_number=int(updated["attempt_count"]),
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
