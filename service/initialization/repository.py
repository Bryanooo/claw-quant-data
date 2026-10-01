"""V2 initialization projections without a second orchestration schema."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any

import psycopg2
import psycopg2.extras

from service.config import DB_CONFIG


class InitializationRepository:
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

    def set_execution_status(self, initialization_id: int, status: str) -> int:
        if status == "paused":
            source = ("created", "queued", "retrying", "waiting_dependency")
            target = "cancelled"
        elif status == "resumed":
            source = ("cancelled",)
            target = "queued"
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


def routine_collection_enabled(*_args: Any, **_kwargs: Any) -> bool:
    """V2 cutover has no mutable V1 runtime-mode gate."""
    return True
