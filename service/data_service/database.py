"""Thread-safe PostgreSQL connection pool used by the HTTP service."""

from collections.abc import Iterator
from contextlib import contextmanager
import logging
import time
from typing import Any

import psycopg2.extras
from psycopg2.pool import ThreadedConnectionPool

from service.config import (
    API_DB_CONNECT_RETRIES,
    API_DB_CONNECT_RETRY_SECONDS,
    API_DB_POOL_MAX,
    API_DB_POOL_MIN,
    DB_CONFIG,
)

logger = logging.getLogger(__name__)


class Database:
    def __init__(
        self,
        config: dict[str, Any] | None = None,
        *,
        min_connections: int = API_DB_POOL_MIN,
        max_connections: int = API_DB_POOL_MAX,
        connect_retries: int = API_DB_CONNECT_RETRIES,
        connect_retry_seconds: int = API_DB_CONNECT_RETRY_SECONDS,
    ):
        if connect_retries < 1:
            raise ValueError("connect_retries must be at least 1")

        last_error: Exception | None = None
        for attempt in range(1, connect_retries + 1):
            try:
                self._pool = ThreadedConnectionPool(
                    min_connections,
                    max_connections,
                    **(config or DB_CONFIG),
                )
                break
            except Exception as exc:
                last_error = exc
                if attempt == connect_retries:
                    raise
                logger.warning(
                    "database pool unavailable (attempt %s/%s); retrying in %ss",
                    attempt,
                    connect_retries,
                    connect_retry_seconds,
                )
                time.sleep(connect_retry_seconds)
        else:  # pragma: no cover - defensive guard for type checkers
            raise RuntimeError("database pool initialization failed") from last_error

    @contextmanager
    def connection(self) -> Iterator[Any]:
        connection = self._pool.getconn()
        discard = False
        try:
            connection.rollback()
            connection.set_session(readonly=True, autocommit=False)
            yield connection
        except BaseException:
            discard = bool(connection.closed)
            try:
                connection.rollback()
            except Exception:
                discard = True
            raise
        finally:
            if discard or connection.closed:
                self._pool.putconn(connection, close=True)
            else:
                try:
                    connection.rollback()
                finally:
                    self._pool.putconn(connection)

    def fetch_all(self, statement: Any, params: tuple[Any, ...] = ()) -> list[dict]:
        with (
            self.connection() as connection,
            connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor,
        ):
            cursor.execute(statement, params)
            return [dict(row) for row in cursor.fetchall()]

    def fetch_one(self, statement: Any, params: tuple[Any, ...] = ()) -> dict | None:
        with (
            self.connection() as connection,
            connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor,
        ):
            cursor.execute(statement, params)
            row = cursor.fetchone()
            return dict(row) if row else None

    def close(self) -> None:
        self._pool.closeall()
