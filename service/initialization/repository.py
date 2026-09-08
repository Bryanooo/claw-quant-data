"""Persistence for initialization campaigns and the runtime mode gate."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import contextmanager
from datetime import date
import json
from typing import Any

import psycopg2
import psycopg2.extras

from service.config import DB_CONFIG


class InitializationRepository:
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

    def runtime_state(self) -> dict:
        with (
            self._connection() as connection,
            connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor,
        ):
            cursor.execute("SELECT * FROM sys_collection_runtime_state WHERE singleton")
            return dict(cursor.fetchone())

    def trade_dates(self, start_date: date, end_date: date) -> list[date]:
        with self._connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT cal_date FROM trade_cal
                WHERE exchange='SSE' AND is_open=1
                  AND cal_date BETWEEN %s AND %s
                ORDER BY cal_date
                """,
                (start_date, end_date),
            )
            return [row[0] for row in cursor.fetchall()]

    def create(
        self,
        *,
        profile: str,
        history_start: date,
        history_end: date,
        auto_activate: bool,
        idempotency_key: str,
        options: dict,
    ) -> tuple[dict, bool]:
        with (
            self._connection() as connection,
            connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor,
        ):
            cursor.execute("SELECT pg_advisory_xact_lock(%s)", (1_924_202_619,))
            cursor.execute(
                """
                SELECT mode FROM sys_collection_runtime_state
                WHERE singleton
                FOR UPDATE
                """
            )
            runtime = cursor.fetchone()
            if not runtime:
                raise RuntimeError("collection runtime state is missing")
            background = runtime["mode"] == "daily"
            cursor.execute(
                """
                SELECT * FROM sys_collection_initialization
                WHERE idempotency_key=%s
                """,
                (idempotency_key,),
            )
            existing = cursor.fetchone()
            if existing:
                return dict(existing), False
            stored_options = dict(options)
            stored_options["background"] = background
            cursor.execute(
                """
                SELECT initialization_id FROM sys_collection_initialization
                WHERE status IN ('running','paused','attention','ready')
                LIMIT 1
                """
            )
            if cursor.fetchone():
                raise ValueError("another initialization campaign is already active")
            cursor.execute(
                """
                INSERT INTO sys_collection_initialization(
                    profile, history_start, history_end, auto_activate,
                    idempotency_key, options
                ) VALUES (%s,%s,%s,%s,%s,%s::jsonb)
                RETURNING *
                """,
                (
                    profile, history_start, history_end, auto_activate,
                    idempotency_key, json.dumps(stored_options, ensure_ascii=False),
                ),
            )
            row = dict(cursor.fetchone())
            cursor.execute(
                """
                UPDATE sys_collection_runtime_state
                SET mode=CASE WHEN mode='daily' THEN 'daily' ELSE 'initializing' END,
                    active_initialization_id=%s,
                    updated_at=NOW()
                WHERE singleton
                """,
                (row["initialization_id"],),
            )
            return row, True

    def get(self, initialization_id: int) -> dict | None:
        with (
            self._connection() as connection,
            connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor,
        ):
            cursor.execute(
                "SELECT * FROM sys_collection_initialization WHERE initialization_id=%s",
                (initialization_id,),
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def active(self) -> dict | None:
        with (
            self._connection() as connection,
            connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor,
        ):
            cursor.execute(
                """
                SELECT * FROM sys_collection_initialization
                WHERE status IN ('running','paused','attention','ready')
                ORDER BY initialization_id DESC LIMIT 1
                """
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def latest(self) -> dict | None:
        """Return the latest campaign, including a completed audit trail."""
        with (
            self._connection() as connection,
            connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor,
        ):
            cursor.execute(
                """
                SELECT * FROM sys_collection_initialization
                ORDER BY initialization_id DESC LIMIT 1
                """
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def add_collection_step(
        self,
        initialization_id: int,
        phase: int,
        step_key: str,
        job_id: int,
        *,
        allow_empty: bool,
        require_verified: bool,
    ) -> None:
        with self._connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO sys_collection_initialization_step(
                    initialization_id, phase, step_key, resource_type,
                    collection_job_id, allow_empty, require_verified
                ) VALUES (%s,%s,%s,'collection',%s,%s,%s)
                ON CONFLICT (initialization_id, step_key) DO UPDATE
                SET collection_job_id=EXCLUDED.collection_job_id, updated_at=NOW()
                """,
                (
                    initialization_id, phase, step_key, job_id,
                    allow_empty, require_verified,
                ),
            )

    def has_step(self, initialization_id: int, step_key: str) -> bool:
        with self._connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT 1 FROM sys_collection_initialization_step
                WHERE initialization_id=%s AND step_key=%s
                """,
                (initialization_id, step_key),
            )
            return cursor.fetchone() is not None

    def step_keys(self, initialization_id: int, phase: int) -> set[str]:
        """Load phase keys once so large history plans do not query per step."""
        with self._connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT step_key FROM sys_collection_initialization_step
                WHERE initialization_id=%s AND phase=%s
                """,
                (initialization_id, phase),
            )
            return {row[0] for row in cursor.fetchall()}

    def delete_step(self, step_id: int) -> None:
        with self._connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM sys_collection_initialization_step WHERE step_id=%s",
                (step_id,),
            )

    def increment_round(self, initialization_id: int) -> int:
        with self._connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE sys_collection_initialization
                SET verification_round=verification_round+1, updated_at=NOW()
                WHERE initialization_id=%s
                RETURNING verification_round
                """,
                (initialization_id,),
            )
            return int(cursor.fetchone()[0])

    def claim_transient_auto_recovery(
        self, initialization_id: int, *, max_recoveries: int
    ) -> int | None:
        """Atomically reserve one bounded transient-recovery attempt."""
        with self._connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE sys_collection_initialization
                SET options = jsonb_set(
                        COALESCE(options, '{}'::jsonb),
                        '{transient_auto_recovery_count}',
                        to_jsonb(
                            COALESCE(
                                (options->>'transient_auto_recovery_count')::integer,
                                0
                            ) + 1
                        ),
                        TRUE
                    ),
                    updated_at = NOW()
                WHERE initialization_id=%s AND status='attention'
                  AND COALESCE(
                        (options->>'transient_auto_recovery_count')::integer,
                        0
                      ) < %s
                RETURNING (options->>'transient_auto_recovery_count')::integer
                """,
                (initialization_id, max_recoveries),
            )
            row = cursor.fetchone()
            return int(row[0]) if row else None

    def add_coverage_step(
        self,
        initialization_id: int,
        phase: int,
        step_key: str,
        coverage_job_id: int,
    ) -> None:
        with self._connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO sys_collection_initialization_step(
                    initialization_id, phase, step_key, resource_type,
                    coverage_job_id, allow_empty, require_verified
                ) VALUES (%s,%s,%s,'coverage',%s,FALSE,TRUE)
                ON CONFLICT (initialization_id, step_key) DO UPDATE
                SET coverage_job_id=EXCLUDED.coverage_job_id, updated_at=NOW()
                """,
                (initialization_id, phase, step_key, coverage_job_id),
            )

    def add_fanout_step(
        self,
        initialization_id: int,
        phase: int,
        step_key: str,
        fanout_campaign_id: int,
        *,
        allow_empty: bool,
    ) -> None:
        with self._connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO sys_collection_initialization_step(
                    initialization_id, phase, step_key, resource_type,
                    fanout_campaign_id, allow_empty, require_verified
                ) VALUES (%s,%s,%s,'fanout',%s,%s,TRUE)
                ON CONFLICT (initialization_id, step_key) DO UPDATE
                SET fanout_campaign_id=EXCLUDED.fanout_campaign_id,
                    updated_at=NOW()
                """,
                (
                    initialization_id,
                    phase,
                    step_key,
                    fanout_campaign_id,
                    allow_empty,
                ),
            )

    def phase_steps(self, initialization_id: int, phase: int) -> list[dict]:
        with (
            self._connection() as connection,
            connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor,
        ):
            cursor.execute(
                """
                SELECT step.*,
                       collection.status AS collection_status,
                       collection.completion_status,
                       collection.completion_evidence,
                       collection.rows_fetched, collection.rows_inserted,
                       collection.error_message AS collection_error,
                       collection.finished_at AS collection_finished_at,
                       coverage.status AS coverage_status,
                       audit.status AS audit_status,
                       audit.missing_partitions, audit.partial_partitions,
                       fanout.status AS fanout_status,
                       fanout.completion_status AS fanout_completion_status,
                       fanout.universe_total AS fanout_universe_total,
                       fanout.next_offset AS fanout_next_offset,
                       fanout.completed_offset AS fanout_completed_offset,
                       fanout.pages_created AS fanout_pages_created,
                       fanout.pages_completed AS fanout_pages_completed,
                       fanout.rows_fetched AS fanout_rows_fetched,
                       fanout.rows_inserted AS fanout_rows_inserted,
                       fanout.error_message AS fanout_error
                FROM sys_collection_initialization_step AS step
                LEFT JOIN sys_collection_job AS collection
                  ON collection.job_id=step.collection_job_id
                LEFT JOIN sys_data_coverage_job AS coverage
                  ON coverage.job_id=step.coverage_job_id
                LEFT JOIN LATERAL (
                    SELECT status, missing_partitions, partial_partitions
                    FROM sys_data_coverage_audit
                    WHERE job_id=coverage.job_id
                    ORDER BY audit_id DESC LIMIT 1
                ) AS audit ON TRUE
                LEFT JOIN sys_collection_fanout_campaign AS fanout
                  ON fanout.campaign_id=step.fanout_campaign_id
                WHERE step.initialization_id=%s AND step.phase=%s
                ORDER BY step.step_id
                """,
                (initialization_id, phase),
            )
            return [dict(row) for row in cursor.fetchall()]

    def list_steps(self, initialization_id: int, *, limit: int = 500) -> list[dict]:
        with self._connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT DISTINCT phase
                FROM sys_collection_initialization_step
                WHERE initialization_id=%s
                ORDER BY phase
                """,
                (initialization_id,),
            )
            phases = [int(row[0]) for row in cursor.fetchall()]
        rows: list[dict] = []
        for phase in phases:
            rows.extend(self.phase_steps(initialization_id, phase))
            if len(rows) >= limit:
                break
        return rows[:limit]

    def update_progress(
        self,
        initialization_id: int,
        *,
        planned: int,
        completed: int,
        failed: int,
        error_message: str | None = None,
    ) -> None:
        with self._connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE sys_collection_initialization
                SET planned_steps=%s, completed_steps=%s, failed_steps=%s,
                    error_message=%s, updated_at=NOW()
                WHERE initialization_id=%s
                """,
                (planned, completed, failed, error_message, initialization_id),
            )

    def advance(self, initialization_id: int, phase: int, phase_name: str) -> None:
        with self._connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE sys_collection_initialization
                SET current_phase=%s, phase_name=%s, status='running',
                    planned_steps=0, completed_steps=0, failed_steps=0,
                    error_message=NULL, updated_at=NOW()
                WHERE initialization_id=%s
                """,
                (phase, phase_name, initialization_id),
            )

    def set_status(
        self,
        initialization_id: int,
        status: str,
        *,
        error_message: str | None = None,
    ) -> None:
        with self._connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE sys_collection_initialization
                SET status=%s, error_message=%s, updated_at=NOW(),
                    finished_at=CASE WHEN %s='completed' THEN NOW() ELSE finished_at END
                WHERE initialization_id=%s
                """,
                (status, error_message, status, initialization_id),
            )

    def activate(self, initialization_id: int) -> None:
        with self._connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE sys_collection_initialization
                SET status='completed', finished_at=NOW(), updated_at=NOW()
                WHERE initialization_id=%s AND status='ready'
                """,
                (initialization_id,),
            )
            if cursor.rowcount != 1:
                raise ValueError("initialization is not ready for daily activation")
            cursor.execute(
                """
                UPDATE sys_collection_runtime_state
                SET mode='daily', active_initialization_id=NULL, updated_at=NOW()
                WHERE singleton AND active_initialization_id=%s
                """,
                (initialization_id,),
            )


def routine_collection_enabled(
    repository: InitializationRepository | None = None,
) -> bool:
    """Fail closed: routine schedules run only after initialization activation."""
    return (repository or InitializationRepository()).runtime_state()["mode"] == "daily"
