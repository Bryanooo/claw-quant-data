"""V2 initialization projections without a second orchestration schema."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any

import psycopg2
import psycopg2.extras

from service.config import DB_CONFIG


class InitializationRepository:
    _CONTROL_KEY_PREFIX = "orchestration_v2.initialization."

    def __init__(self, connection_factory=psycopg2.connect):
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

    def audit_jobs(self, initialization_id: int) -> list[dict]:
        prefix = f"v2-init:{initialization_id}:%"
        with self._connection() as connection, connection.cursor(
            cursor_factory=psycopg2.extras.RealDictCursor
        ) as cursor:
            cursor.execute(
                """
                SELECT job_id, dataset_name, start_date, end_date, status,
                       idempotency_key,
                       attempt, max_attempts, error_message, created_at,
                       started_at, finished_at
                FROM sys_data_coverage_job
                WHERE idempotency_key LIKE %s
                ORDER BY job_id
                """,
                (prefix,),
            )
            return [dict(row) for row in cursor.fetchall()]

    def executions(self, initialization_id: int, *, limit: int = 5000) -> list[dict]:
        with self._connection() as connection, connection.cursor(
            cursor_factory=psycopg2.extras.RealDictCursor
        ) as cursor:
            cursor.execute(
                """
                SELECT task_execution_id, task_key, definition_version, purpose,
                       observation_key, observation_start, observation_end,
                       status, current_node_key, node_status,
                       attempt_count AS attempt, max_attempts,
                       final_error_category AS failure_category,
                       final_error_message AS error_message,
                       NULL::BIGINT AS rows_fetched,
                       NULL::BIGINT AS rows_written,
                       created_at, started_at,
                       finished_at, updated_at
                FROM orchestration_v2.task_execution
                WHERE frozen_scope->>'initialization_id'=%s
                ORDER BY task_execution_id
                LIMIT %s
                """,
                (str(initialization_id), limit),
            )
            return [dict(row) for row in cursor.fetchall()]

    def execution_summary(self, initialization_id: int) -> dict:
        """Summarize the current logical execution set without row limits.

        Execution history can exceed the dashboard page size.  Initialization
        readiness must be computed from every logical observation, while only
        the newest retry for a task/observation may represent its current
        state.
        """
        with self._connection() as connection, connection.cursor(
            cursor_factory=psycopg2.extras.RealDictCursor
        ) as cursor:
            cursor.execute(
                """
                WITH current_execution AS (
                    SELECT DISTINCT ON (task_key, observation_key)
                           task_execution_id, task_key, observation_key, status
                    FROM orchestration_v2.task_execution
                    WHERE frozen_scope->>'initialization_id'=%s
                    ORDER BY task_key, observation_key,
                             task_execution_id DESC
                )
                SELECT COALESCE(sum(status_count), 0)::bigint AS total,
                       COALESCE(
                         jsonb_object_agg(status, status_count), '{}'::jsonb
                       ) AS counts,
                       max(task_execution_id) AS latest_execution_id,
                       max(task_execution_id) FILTER (WHERE status='success')
                           AS latest_success_execution_id
                FROM (
                    SELECT status, count(*)::bigint AS status_count,
                           max(task_execution_id) AS task_execution_id
                    FROM current_execution
                    GROUP BY status
                ) AS grouped
                """,
                (str(initialization_id),),
            )
            row = dict(cursor.fetchone())
        return {
            "total": int(row.get("total") or 0),
            "counts": {
                str(key): int(value)
                for key, value in dict(row.get("counts") or {}).items()
            },
            "latest_execution_id": int(row.get("latest_execution_id") or 0),
            "latest_success_execution_id": int(
                row.get("latest_success_execution_id") or 0
            ),
        }

    def find_latest_id(self) -> int | None:
        with self._connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT split_part(idempotency_key, ':', 2)::bigint
                FROM sys_data_coverage_job
                WHERE idempotency_key LIKE 'v2-init:%'
                ORDER BY job_id DESC LIMIT 1
                """
            )
            row = cursor.fetchone()
            return int(row[0]) if row else None

    def control_status(self, initialization_id: int) -> str:
        key = f"{self._CONTROL_KEY_PREFIX}{initialization_id}.status"
        with self._connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT cfg_value
                FROM sys_config
                WHERE cfg_key=%s AND is_active=TRUE
                """,
                (key,),
            )
            row = cursor.fetchone()
            return str(row[0]) if row else "active"

    def set_control_status(self, initialization_id: int, status: str) -> None:
        if status not in {"active", "paused"}:
            raise ValueError(f"unsupported initialization control status: {status}")
        key = f"{self._CONTROL_KEY_PREFIX}{initialization_id}.status"
        with self._connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO sys_config (
                    cfg_key, cfg_value, cfg_type, description, is_active,
                    updated_at, updated_by
                ) VALUES (%s, %s, 'string', %s, TRUE, NOW(), 'initialization_v2')
                ON CONFLICT (cfg_key) DO UPDATE
                SET cfg_value=EXCLUDED.cfg_value,
                    description=EXCLUDED.description,
                    is_active=TRUE,
                    updated_at=NOW(),
                    updated_by='initialization_v2'
                """,
                (
                    key,
                    status,
                    "Durable operator control for a V2 initialization campaign",
                ),
            )

    def set_execution_status(self, initialization_id: int, status: str) -> int:
        if status == "paused":
            source = ("created", "queued", "retrying", "waiting_dependency")
            target = "cancelled"
        else:
            raise ValueError(f"unsupported initialization transition: {status}")
        with self._connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE orchestration_v2.task_execution
                SET status=%s, updated_at=NOW(),
                    finished_at=CASE WHEN %s='cancelled' THEN NOW() ELSE NULL END,
                    final_error_category=CASE WHEN %s='cancelled'
                        THEN 'operator_paused' ELSE NULL END,
                    final_error_message=CASE WHEN %s='cancelled'
                        THEN 'paused by initialization operator' ELSE NULL END,
                    final_error_detail=CASE WHEN %s='cancelled'
                        THEN jsonb_build_object('operator_action','pause')
                        ELSE '{}'::jsonb END,
                    lease_owner=NULL, lease_token=NULL, lease_expires_at=NULL
                WHERE frozen_scope->>'initialization_id'=%s
                  AND status=ANY(%s)
                """,
                (
                    target,
                    target,
                    target,
                    target,
                    target,
                    str(initialization_id),
                    list(source),
                ),
            )
            return cursor.rowcount

    def supersede_legacy_quota_guarded_executions(
        self,
        initialization_id: int,
        *,
        task_keys: tuple[str, ...],
    ) -> int:
        """Retire failed per-period fan-out superseded by bounded history plans.

        The original rows remain as immutable operational evidence.  Only
        terminal attention instances created before the bounded-history
        planner are transitioned, so unrelated failures still block resume.
        """
        if not task_keys:
            return 0
        with self._connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE orchestration_v2.task_execution
                SET status='superseded',
                    updated_at=NOW(),
                    finished_at=COALESCE(finished_at, NOW()),
                    final_error_category='superseded_by_bounded_history',
                    final_error_message=(
                        'legacy per-period execution replaced by quota-aware '
                        'bounded history recovery'
                    ),
                    final_error_detail=COALESCE(final_error_detail, '{}'::jsonb)
                        || jsonb_build_object(
                            'superseded_reason', 'quota_aware_planner_migration'
                        ),
                    lease_owner=NULL,
                    lease_token=NULL,
                    lease_expires_at=NULL
                WHERE frozen_scope->>'initialization_id'=%s
                  AND task_key=ANY(%s)
                  AND status='attention'
                  AND COALESCE(observation_key, '') NOT LIKE 'history:%%'
                """,
                (str(initialization_id), list(task_keys)),
            )
            return cursor.rowcount


def routine_collection_enabled(*_args: Any, **_kwargs: Any) -> bool:
    """V2 cutover has no mutable V1 runtime-mode gate."""
    return True
