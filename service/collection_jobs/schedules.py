"""Persistent cursor for reconciling APScheduler collection triggers."""

from collections.abc import Callable
from contextlib import contextmanager
from datetime import datetime
from typing import Any

import psycopg2
import psycopg2.extras

from service.config import DB_CONFIG


class ScheduleCursorRepository:
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

    def get(self, schedule_id: str) -> dict | None:
        with (
            self._connection() as connection,
            connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor,
        ):
            cursor.execute(
                "SELECT * FROM sys_collection_schedule_cursor WHERE schedule_id = %s",
                (schedule_id,),
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def advance(
        self,
        schedule_id: str,
        scheduled_for: datetime,
        *,
        job_id: int,
        handler_key: str,
        handler_version: str,
    ) -> None:
        """Monotonically advance a cursor after durable task creation."""
        with self._connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO sys_collection_schedule_cursor
                    (schedule_id, last_dispatched_for, last_job_id,
                     handler_key, handler_version)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (schedule_id) DO UPDATE
                SET last_dispatched_for = GREATEST(
                        sys_collection_schedule_cursor.last_dispatched_for,
                        EXCLUDED.last_dispatched_for
                    ),
                    last_job_id = CASE
                        WHEN EXCLUDED.last_dispatched_for >=
                             sys_collection_schedule_cursor.last_dispatched_for
                        THEN EXCLUDED.last_job_id
                        ELSE sys_collection_schedule_cursor.last_job_id
                    END,
                    handler_key = EXCLUDED.handler_key,
                    handler_version = EXCLUDED.handler_version,
                    updated_at = NOW()
                """,
                (
                    schedule_id,
                    scheduled_for,
                    job_id,
                    handler_key,
                    handler_version,
                ),
            )

    def bootstrap(
        self,
        schedule_id: str,
        scheduled_for: datetime,
        *,
        handler_key: str,
        handler_version: str,
    ) -> bool:
        """Seed a new cursor without replaying work from before this feature."""
        with self._connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO sys_collection_schedule_cursor
                    (schedule_id, last_dispatched_for, last_job_id,
                     handler_key, handler_version)
                VALUES (%s, %s, NULL, %s, %s)
                ON CONFLICT (schedule_id) DO NOTHING
                """,
                (schedule_id, scheduled_for, handler_key, handler_version),
            )
            return cursor.rowcount == 1
