"""PostgreSQL repository for the persistent collection-job queue."""

import json
from collections.abc import Callable
from contextlib import contextmanager
from datetime import date
from typing import Any

import psycopg2
import psycopg2.extras

from service.config import DB_CONFIG
from service.collection_jobs.models import BatchChildSpec, HandlerMetadata, JobLeaseLostError


class JobRepository:
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

    def create(
        self,
        task_name: str,
        parameters: dict,
        *,
        max_attempts: int,
        idempotency_key: str | None,
        parent_job_id: int | None = None,
        api_name: str | None = None,
        cadence: str | None = None,
        period_key: str | None = None,
        expected_for: Any | None = None,
        handler_type: str | None = None,
        handler_key: str | None = None,
        handler_version: str | None = None,
        code_revision: str | None = None,
        priority: int = 50,
        resource_class: str = "default",
    ) -> tuple[dict, bool]:
        with (
            self._connection() as connection,
            connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor,
        ):
            cursor.execute(
                """
                    INSERT INTO sys_collection_job
                        (task_name, parameters, max_attempts, idempotency_key,
                         parent_job_id, api_name, cadence, period_key, expected_for,
                         handler_type, handler_key, handler_version, code_revision,
                         priority, resource_class)
                    VALUES (%s, %s::jsonb, %s, %s, %s, %s, %s, %s, %s,
                            %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (idempotency_key) DO NOTHING
                    RETURNING *
                    """,
                (
                    task_name,
                    json.dumps(parameters, ensure_ascii=False),
                    max_attempts,
                    idempotency_key,
                    parent_job_id,
                    api_name,
                    cadence,
                    period_key,
                    expected_for,
                    handler_type,
                    handler_key,
                    handler_version,
                    code_revision,
                    priority,
                    resource_class,
                ),
            )
            row = cursor.fetchone()
            if row:
                return dict(row), True
            cursor.execute(
                """
                UPDATE sys_collection_job
                SET api_name = COALESCE(api_name, %s),
                    cadence = COALESCE(cadence, %s),
                    period_key = COALESCE(period_key, %s),
                    expected_for = COALESCE(expected_for, %s),
                    handler_type = COALESCE(handler_type, %s),
                    handler_key = COALESCE(handler_key, %s),
                    handler_version = COALESCE(handler_version, %s),
                    code_revision = COALESCE(code_revision, %s)
                WHERE idempotency_key = %s
                """,
                (
                    api_name, cadence, period_key, expected_for,
                    handler_type, handler_key, handler_version, code_revision,
                    idempotency_key,
                ),
            )
            cursor.execute(
                "SELECT * FROM sys_collection_job WHERE idempotency_key = %s",
                (idempotency_key,),
            )
            return dict(cursor.fetchone()), False

    def get(self, job_id: int) -> dict | None:
        with (
            self._connection() as connection,
            connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor,
        ):
            cursor.execute(
                "SELECT * FROM sys_collection_job WHERE job_id = %s",
                (job_id,),
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def create_empty_recheck(
        self,
        root_job_id: int,
        *,
        min_interval_seconds: int,
        max_generations: int,
        window_days: int,
        handler: HandlerMetadata,
    ) -> dict | None:
        """Create one delayed, separately auditable retry of an empty result.

        The chain is locked and linked in PostgreSQL so concurrent scheduler
        instances cannot create duplicate rechecks. Normal transient failures
        still use ``attempt/max_attempts`` inside each individual job.
        """
        if min_interval_seconds < 1 or window_days < 1:
            raise ValueError("empty recheck interval and window must be positive")
        if not 1 <= max_generations <= 20:
            raise ValueError("empty recheck generations must be between 1 and 20")
        with (
            self._connection() as connection,
            connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor,
        ):
            cursor.execute(
                """
                SELECT *
                FROM sys_collection_job
                WHERE job_id = %s OR recheck_root_job_id = %s
                ORDER BY recheck_generation DESC, job_id DESC
                LIMIT 1
                FOR UPDATE
                """,
                (root_job_id, root_job_id),
            )
            latest = cursor.fetchone()
            if not latest:
                return None
            generation = int(latest["recheck_generation"])
            if (
                latest["status"] != "success"
                or latest["completion_status"] != "empty"
                or generation >= max_generations
            ):
                return None
            next_generation = generation + 1
            evidence = {
                "recheck": {
                    "reason": "upstream_empty",
                    "root_job_id": root_job_id,
                    "previous_job_id": int(latest["job_id"]),
                    "generation": next_generation,
                }
            }
            cursor.execute(
                """
                INSERT INTO sys_collection_job (
                    task_name, parameters, max_attempts, idempotency_key,
                    parent_job_id, api_name, cadence, period_key, expected_for,
                    handler_type, handler_key, handler_version, code_revision,
                    priority, resource_class, job_kind, completion_evidence,
                    recheck_of_job_id, recheck_root_job_id, recheck_generation
                )
                SELECT
                    source.task_name, source.parameters, source.max_attempts, %s,
                    source.parent_job_id, source.api_name, source.cadence,
                    source.period_key, source.expected_for,
                    %s, %s, %s, %s,
                    source.priority, source.resource_class, source.job_kind,
                    %s::jsonb, source.job_id, %s, %s
                FROM sys_collection_job AS source
                JOIN sys_collection_job AS root ON root.job_id = %s
                WHERE source.job_id = %s
                  AND source.status = 'success'
                  AND source.completion_status = 'empty'
                  AND source.finished_at <= NOW() - (%s * INTERVAL '1 second')
                  AND root.created_at >= NOW() - (%s * INTERVAL '1 day')
                ON CONFLICT DO NOTHING
                RETURNING *
                """,
                (
                    f"empty-recheck-{root_job_id}-{next_generation}",
                    handler.handler_type,
                    handler.handler_key,
                    handler.handler_version,
                    handler.code_revision,
                    json.dumps(evidence, ensure_ascii=False),
                    root_job_id,
                    next_generation,
                    root_job_id,
                    latest["job_id"],
                    min_interval_seconds,
                    window_days,
                ),
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def list_fanout_values(
        self, source: str, *, as_of: date | None = None
    ) -> list[str]:
        """Return a fan-out universe from an allow-listed local dependency.

        SQL is intentionally selected from a closed map.  The batch API never
        accepts table or column names from callers.  Point-in-time filters keep
        full initialization from querying entities that were not yet listed or
        were already terminated at the campaign boundary.
        """
        queries = {
            "stock": """
                SELECT ts_code FROM stock_basic
                WHERE ts_code IS NOT NULL
                  AND (
                    %s::DATE IS NULL OR (
                      (NULLIF(list_date, '') IS NULL OR list_date <= TO_CHAR(%s::DATE, 'YYYYMMDD'))
                      AND (NULLIF(delist_date, '') IS NULL OR delist_date >= TO_CHAR(%s::DATE, 'YYYYMMDD'))
                    )
                  )
                ORDER BY ts_code
            """,
            "index": """
                SELECT ts_code FROM index_basic
                WHERE ts_code IS NOT NULL ORDER BY ts_code
            """,
            "ci_index": """
                SELECT DISTINCT ts_code FROM tushare_norm_ci_daily
                WHERE ts_code IS NOT NULL ORDER BY ts_code
            """,
            "sw_l3_index": """
                SELECT DISTINCT index_code FROM tushare_norm_index_classify
                WHERE index_code IS NOT NULL AND level = 'L3'
                ORDER BY index_code
            """,
            "convertible_bond": """
                WITH latest AS (
                  SELECT DISTINCT ON (ts_code) ts_code, list_date, delist_date
                  FROM tushare_norm_cb_basic
                  WHERE ts_code IS NOT NULL
                  ORDER BY ts_code, _source_collected_at DESC
                )
                SELECT ts_code FROM latest
                WHERE %s::DATE IS NULL OR (
                  (list_date IS NULL OR list_date <= %s::DATE)
                  AND (delist_date IS NULL OR delist_date >= %s::DATE)
                )
                ORDER BY ts_code
            """,
            "fund": """
                WITH latest AS (
                  SELECT DISTINCT ON (ts_code)
                    ts_code, list_date, found_date, delist_date, due_date
                  FROM tushare_norm_fund_basic
                  WHERE ts_code IS NOT NULL
                  ORDER BY ts_code, _source_collected_at DESC
                )
                SELECT ts_code FROM latest
                WHERE %s::DATE IS NULL OR (
                  (COALESCE(list_date, found_date) IS NULL OR COALESCE(list_date, found_date) <= %s::DATE)
                  AND (COALESCE(delist_date, due_date) IS NULL OR COALESCE(delist_date, due_date) >= %s::DATE)
                )
                ORDER BY ts_code
            """,
            "bc_bond": """
                SELECT DISTINCT ts_code FROM tushare_norm_bc_bestotcqt
                WHERE ts_code IS NOT NULL ORDER BY ts_code
            """,
            "etf_sh": """
                SELECT DISTINCT ts_code FROM tushare_norm_etf_basic
                WHERE ts_code IS NOT NULL AND ts_code LIKE '%.SH'
                ORDER BY ts_code
            """,
            "etf_sz": """
                SELECT DISTINCT ts_code FROM tushare_norm_etf_basic
                WHERE ts_code IS NOT NULL AND ts_code LIKE '%.SZ'
                ORDER BY ts_code
            """,
            "tdx_index": """
                SELECT DISTINCT ts_code FROM tdx_index
                WHERE ts_code IS NOT NULL ORDER BY ts_code
            """,
            "pro_data": """
                SELECT DISTINCT name FROM tushare_norm_p_list
                WHERE name IS NOT NULL ORDER BY name
            """,
            "factor_name": """
                SELECT DISTINCT factor_name FROM tushare_norm_factor_value
                WHERE factor_name IS NOT NULL AND factor_name <> ''
                ORDER BY factor_name
            """,
        }
        try:
            query = queries[source]
        except KeyError as exc:
            raise ValueError(f"unsupported fan-out universe: {source}") from exc
        with self._connection() as connection, connection.cursor() as cursor:
            if source in {"stock", "convertible_bond", "fund"}:
                cursor.execute(query, (as_of, as_of, as_of))
            else:
                cursor.execute(query)
            return [str(row[0]) for row in cursor.fetchall()]

    def create_batch(
        self,
        parameters: dict,
        children: list[BatchChildSpec],
        *,
        idempotency_key: str,
        api_name: str,
        period_key: str | None,
        expected_for: Any | None,
        completion_evidence: dict | None = None,
        cadence: str = "backfill",
        priority: int = 10,
        resource_class: str = "backfill",
    ) -> tuple[dict, bool]:
        """Atomically create one non-runnable parent and all retryable leaves."""
        if not children:
            raise ValueError("collection batch must contain at least one child")
        with (
            self._connection() as connection,
            connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor,
        ):
            cursor.execute(
                """
                INSERT INTO sys_collection_job (
                    task_name, parameters, status, max_attempts,
                    api_name, cadence, period_key, expected_for,
                    completion_status, completion_evidence, idempotency_key,
                    priority, resource_class, job_kind, started_at
                ) VALUES (
                    'collection_batch', %s::jsonb, 'running', 1,
                    %s, %s, %s, %s,
                    'running', %s::jsonb, %s,
                    %s, %s, 'batch', NOW()
                )
                ON CONFLICT (idempotency_key) DO NOTHING
                RETURNING *
                """,
                (
                    json.dumps(parameters, ensure_ascii=False),
                    api_name,
                    cadence,
                    period_key,
                    expected_for,
                    json.dumps(completion_evidence or {}, ensure_ascii=False),
                    idempotency_key,
                    priority,
                    resource_class,
                ),
            )
            parent = cursor.fetchone()
            if not parent:
                cursor.execute(
                    "SELECT * FROM sys_collection_job WHERE idempotency_key = %s",
                    (idempotency_key,),
                )
                return dict(cursor.fetchone()), False

            parent_id = int(parent["job_id"])
            for child in children:
                cursor.execute(
                    """
                    INSERT INTO sys_collection_job (
                        task_name, parameters, max_attempts, idempotency_key,
                        parent_job_id, api_name, cadence, period_key, expected_for,
                        handler_type, handler_key, handler_version, code_revision,
                        priority, resource_class, job_kind
                    ) VALUES (
                        %s, %s::jsonb, %s, %s,
                        %s, %s, %s, %s, %s,
                        %s, %s, %s, %s,
                        %s, %s, 'leaf'
                    )
                    """,
                    (
                        child.task_name,
                        json.dumps(child.parameters, ensure_ascii=False),
                        child.max_attempts,
                        child.idempotency_key,
                        parent_id,
                        child.api_name,
                        child.cadence,
                        child.period_key,
                        child.expected_for,
                        child.handler.handler_type,
                        child.handler.handler_key,
                        child.handler.handler_version,
                        child.handler.code_revision,
                        child.priority,
                        child.resource_class,
                    ),
                )
            cursor.execute(
                "SELECT * FROM sys_collection_job WHERE job_id = %s",
                (parent_id,),
            )
            return dict(cursor.fetchone()), True

    def list(
        self,
        *,
        task_name: str | None,
        status: str | None,
        api_name: str | None = None,
        period_key: str | None = None,
        completion_status: str | None = None,
        parent_job_id: int | None = None,
        job_kind: str | None = None,
        limit: int,
    ) -> list[dict]:
        conditions = []
        parameters: list[Any] = []
        if task_name:
            conditions.append("task_name = %s")
            parameters.append(task_name)
        if status:
            conditions.append("status = %s")
            parameters.append(status)
        if api_name:
            conditions.append("COALESCE(api_name, parameters->>'api_name') = %s")
            parameters.append(api_name)
        if period_key:
            conditions.append("period_key = %s")
            parameters.append(period_key)
        if completion_status:
            conditions.append("completion_status = %s")
            parameters.append(completion_status)
        if parent_job_id is not None:
            conditions.append("parent_job_id = %s")
            parameters.append(parent_job_id)
        if job_kind:
            conditions.append("job_kind = %s")
            parameters.append(job_kind)
        where = " AND ".join(conditions) if conditions else "TRUE"
        with (
            self._connection() as connection,
            connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor,
        ):
            cursor.execute(
                f"""
                    SELECT * FROM sys_collection_job
                    WHERE {where}
                    ORDER BY created_at DESC
                    LIMIT %s
                    """,
                (*parameters, limit),
            )
            return [dict(row) for row in cursor.fetchall()]

    def claim_next(
        self,
        worker_id: str,
        *,
        lease_seconds: int = 120,
        resource_classes: tuple[str, ...] | None = None,
    ) -> dict | None:
        """Atomically claim the highest-priority leaf accepted by this pool.

        ``None`` preserves the legacy all-resources worker.  An explicit tuple
        creates a hard queue boundary, so a long backfill cannot occupy the
        execution slot reserved for time-sensitive routine work.
        """
        if resource_classes is not None and not resource_classes:
            raise ValueError("resource_classes cannot be empty")
        with (
            self._connection() as connection,
            connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor,
        ):
            cursor.execute(
                """
                    WITH next_job AS (
                        SELECT job_id
                        FROM sys_collection_job
                        WHERE status = 'queued' AND available_at <= NOW()
                          AND job_kind = 'leaf'
                          AND (%s::TEXT[] IS NULL OR resource_class = ANY(%s::TEXT[]))
                        ORDER BY priority DESC, created_at, job_id
                        FOR UPDATE SKIP LOCKED
                        LIMIT 1
                    )
                    UPDATE sys_collection_job AS job
                    SET status = 'running',
                        completion_status = 'running',
                        started_at = NOW(),
                        finished_at = NULL,
                        attempt = attempt + 1,
                        worker_id = %s,
                        heartbeat_at = NOW(),
                        lease_expires_at = NOW() + (%s * INTERVAL '1 second'),
                        error_message = NULL
                    FROM next_job
                    WHERE job.job_id = next_job.job_id
                    RETURNING job.*
                    """,
                (
                    list(resource_classes) if resource_classes is not None else None,
                    list(resource_classes) if resource_classes is not None else None,
                    worker_id,
                    lease_seconds,
                ),
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def finish(
        self,
        job_id: int,
        *,
        rows_inserted: int,
        rows_fetched: int | None = None,
        completion_status: str = "unverified",
        completion_evidence: dict | None = None,
        worker_id: str | None = None,
        verification: dict | None = None,
    ) -> None:
        with self._connection() as connection, connection.cursor() as cursor:
            final_evidence = dict(completion_evidence or {})
            if verification:
                cursor.execute(
                    """
                    INSERT INTO sys_data_coverage_job
                        (dataset_name, start_date, end_date, idempotency_key,
                         max_attempts, collection_job_id)
                    VALUES (%s, %s, %s, %s, 2, %s)
                    ON CONFLICT (idempotency_key) DO NOTHING
                    RETURNING job_id
                    """,
                    (
                        verification["dataset_name"],
                        verification["start_date"],
                        verification["end_date"],
                        verification["idempotency_key"],
                        job_id,
                    ),
                )
                row = cursor.fetchone()
                if row:
                    verification_job_id = int(row[0])
                else:
                    cursor.execute(
                        """
                        SELECT job_id FROM sys_data_coverage_job
                        WHERE idempotency_key = %s
                        """,
                        (verification["idempotency_key"],),
                    )
                    verification_job_id = int(cursor.fetchone()[0])
                completion_status = "verifying"
                final_evidence["verification"] = {
                    "coverage_job_id": verification_job_id,
                    "dataset": verification["dataset_name"],
                    "start_date": verification["start_date"].isoformat(),
                    "end_date": verification["end_date"].isoformat(),
                    "status": "queued",
                }
            cursor.execute(
                """
                    UPDATE sys_collection_job
                    SET status = 'success', finished_at = NOW(),
                        rows_inserted = %s, rows_fetched = %s,
                        completion_status = %s,
                        completion_evidence = %s,
                        lease_expires_at = NULL
                    WHERE job_id = %s AND status = 'running'
                      AND (%s IS NULL OR worker_id = %s)
                    """,
                (
                    rows_inserted,
                    rows_fetched,
                    completion_status,
                    psycopg2.extras.Json(final_evidence),
                    job_id,
                    worker_id,
                    worker_id,
                ),
            )
            if cursor.rowcount != 1:
                raise JobLeaseLostError(f"collection job lease lost: {job_id}")

    def apply_verification_result(
        self,
        collection_job_id: int,
        *,
        audit_id: int,
        audit_status: str,
        dataset_name: str,
        missing_partitions: int,
        partial_partitions: int,
        coverage_ratio: float | None,
    ) -> None:
        completion_status = {
            "complete": "complete",
            "gaps": "incomplete",
            "empty": "empty",
            "unverified": "unverified",
            "observed_only": "unverified",
        }[audit_status]
        evidence = {
            "verification": {
                "audit_id": audit_id,
                "dataset": dataset_name,
                "status": audit_status,
                "missing_partitions": missing_partitions,
                "partial_partitions": partial_partitions,
                "coverage_ratio": coverage_ratio,
                "verified": audit_status in {"complete", "empty"},
            }
        }
        with self._connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE sys_collection_job
                SET completion_status = %s,
                    completion_evidence = completion_evidence || %s::jsonb
                WHERE job_id = %s AND status = 'success'
                """,
                (
                    completion_status,
                    json.dumps(evidence, ensure_ascii=False),
                    collection_job_id,
                ),
            )
            if cursor.rowcount != 1:
                raise JobLeaseLostError(
                    f"cannot apply coverage verification to collection job: "
                    f"{collection_job_id}"
                )

    def renew_lease(self, job_id: int, worker_id: str, lease_seconds: int) -> bool:
        with self._connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE sys_collection_job
                SET heartbeat_at = NOW(),
                    lease_expires_at = NOW() + (%s * INTERVAL '1 second')
                WHERE job_id = %s AND status = 'running' AND worker_id = %s
                """,
                (lease_seconds, job_id, worker_id),
            )
            return cursor.rowcount == 1

    def requeue_failed_batch_child(self, job_id: int) -> dict | None:
        """Re-open a failed leaf in the same batch so parent totals stay exact."""
        with (
            self._connection() as connection,
            connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor,
        ):
            cursor.execute(
                """
                UPDATE sys_collection_job AS child
                SET status = 'queued', completion_status = 'retrying',
                    available_at = NOW(), finished_at = NULL,
                    worker_id = NULL, heartbeat_at = NULL,
                    lease_expires_at = NULL, error_message = NULL,
                    max_attempts = GREATEST(child.max_attempts, child.attempt + 1)
                FROM sys_collection_job AS parent
                WHERE child.job_id = %s AND child.status = 'failed'
                  AND child.parent_job_id = parent.job_id
                  AND child.job_kind = 'leaf' AND parent.job_kind = 'batch'
                RETURNING child.*
                """,
                (job_id,),
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def fail_or_requeue(
        self,
        job: dict,
        error_message: str,
        *,
        retryable: bool = True,
        retry_after_seconds: int | None = None,
        defer_resource_class_seconds: int | None = None,
        failure_status: str = "failed",
        rows_inserted: int = 0,
        completion_evidence: dict | None = None,
    ) -> str:
        should_retry = retryable and job["attempt"] < job["max_attempts"]
        status = "queued" if should_retry else "failed"
        retry_delay = (
            max(retry_after_seconds, 1)
            if retry_after_seconds is not None
            else min(10 * (2 ** max(job["attempt"] - 1, 0)), 3600)
        )
        with self._connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                    UPDATE sys_collection_job
                    SET status = %s,
                        completion_status = %s,
                        available_at = CASE
                            WHEN %s THEN NOW() + (%s * INTERVAL '1 second')
                            ELSE available_at
                        END,
                        finished_at = CASE WHEN %s THEN NULL ELSE NOW() END,
                        lease_expires_at = NULL,
                        rows_inserted = GREATEST(rows_inserted, %s),
                        completion_evidence = CASE
                            WHEN %s::jsonb = '{}'::jsonb THEN completion_evidence
                            ELSE %s::jsonb
                        END,
                        error_message = %s
                    WHERE job_id = %s AND status = 'running'
                      AND worker_id = %s
                    """,
                (
                    status,
                    "retrying" if should_retry else failure_status,
                    should_retry,
                    retry_delay,
                    should_retry,
                    rows_inserted,
                    json.dumps(completion_evidence or {}, ensure_ascii=False),
                    json.dumps(completion_evidence or {}, ensure_ascii=False),
                    error_message[:4000],
                    job["job_id"],
                    job.get("worker_id"),
                ),
            )
            if cursor.rowcount != 1:
                raise JobLeaseLostError(
                    f"collection job lease lost: {job['job_id']}"
                )
            # A long retry delay signals a shared upstream quota window (for
            # example 1000 calls/day). Defer all still-queued leaves for the
            # same interface in the same transaction. This prevents a fan-out
            # page from burning every child attempt after the first child has
            # already proved that the token allocation is exhausted.
            if (
                should_retry
                and retry_after_seconds is not None
                and retry_after_seconds >= 3600
                and job.get("api_name")
            ):
                cursor.execute(
                    """
                    UPDATE sys_collection_job
                    SET available_at = GREATEST(
                        available_at,
                        NOW() + (%s * INTERVAL '1 second')
                    )
                    WHERE status = 'queued' AND job_kind = 'leaf'
                      AND api_name = %s
                    """,
                    (retry_delay, job["api_name"]),
                )
            if defer_resource_class_seconds and job.get("resource_class"):
                cursor.execute(
                    """
                    UPDATE sys_collection_job
                    SET available_at = GREATEST(
                        available_at,
                        NOW() + (%s * INTERVAL '1 second')
                    )
                    WHERE status = 'queued' AND job_kind = 'leaf'
                      AND resource_class = %s
                    """,
                    (
                        max(int(defer_resource_class_seconds), 1),
                        job["resource_class"],
                    ),
                )
            return status

    def defer_running(
        self,
        job: dict,
        *,
        retry_after_seconds: int,
        reason: str,
    ) -> str:
        """Release a leased job without consuming an execution attempt.

        This is used for known future rate-limit slots, not failures. The
        collector has not called the upstream API, so preserving the attempt
        budget and avoiding a false failed-task incident is essential.
        """
        delay = max(int(retry_after_seconds), 1)
        with self._connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE sys_collection_job
                SET status = 'queued', completion_status = 'retrying',
                    available_at = NOW() + (%s * INTERVAL '1 second'),
                    attempt = GREATEST(attempt - 1, 0),
                    worker_id = NULL, heartbeat_at = NULL,
                    lease_expires_at = NULL, finished_at = NULL,
                    error_message = %s
                WHERE job_id = %s AND status = 'running'
                  AND worker_id = %s
                """,
                (delay, reason[:4000], job["job_id"], job.get("worker_id")),
            )
            if cursor.rowcount != 1:
                raise JobLeaseLostError(
                    f"collection job lease lost: {job['job_id']}"
                )
        return "queued"

    def recover_stale(self, stale_after_seconds: int) -> int:
        with self._connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                    UPDATE sys_collection_job
                    SET status = CASE
                            WHEN attempt < max_attempts THEN 'queued'
                            ELSE 'failed'
                        END,
                        available_at = NOW(),
                        completion_status = CASE
                            WHEN attempt < max_attempts THEN 'retrying'
                            ELSE 'failed'
                        END,
                        worker_id = NULL,
                        lease_expires_at = NULL,
                        finished_at = CASE
                            WHEN attempt < max_attempts THEN NULL ELSE NOW()
                        END,
                        error_message = CASE
                            WHEN attempt < max_attempts
                                THEN 'worker lease expired before job completed'
                            ELSE 'worker lease expired after final attempt'
                        END
                    WHERE status = 'running' AND job_kind = 'leaf'
                      AND (
                        lease_expires_at < NOW()
                        OR (
                            lease_expires_at IS NULL
                            AND started_at < NOW() - (%s * INTERVAL '1 second')
                        )
                      )
                    """,
                (stale_after_seconds,),
            )
            return cursor.rowcount

    def health_snapshot(
        self,
        *,
        failed_since_hours: int = 6,
        queued_stale_minutes: int = 60,
        running_stale_minutes: int = 45,
    ) -> dict:
        """Return queue conditions that require operator attention."""
        with (
            self._connection() as connection,
            connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor,
        ):
            cursor.execute(
                """
                SELECT
                    count(*) FILTER (
                        WHERE status = 'failed' AND job_kind = 'leaf'
                          AND finished_at >= NOW() - (%s * INTERVAL '1 hour')
                          AND NOT EXISTS (
                              SELECT 1
                              FROM sys_collection_job AS recovered
                              WHERE recovered.job_id > sys_collection_job.job_id
                                AND recovered.status = 'success'
                                AND recovered.job_kind = 'leaf'
                                AND COALESCE(
                                      recovered.api_name,
                                      recovered.parameters->>'api_name',
                                      recovered.task_name
                                    ) = COALESCE(
                                      sys_collection_job.api_name,
                                      sys_collection_job.parameters->>'api_name',
                                      sys_collection_job.task_name
                                    )
                                AND (
                                      (sys_collection_job.expected_for IS NOT NULL
                                       AND recovered.expected_for = sys_collection_job.expected_for)
                                   OR (sys_collection_job.period_key IS NOT NULL
                                       AND recovered.period_key = sys_collection_job.period_key)
                                   OR (sys_collection_job.expected_for IS NULL
                                       AND sys_collection_job.period_key IS NULL)
                                )
                          )
                    ) AS recent_failed,
                    count(*) FILTER (
                        WHERE status = 'queued' AND job_kind = 'leaf'
                          AND available_at < NOW() - (%s * INTERVAL '1 minute')
                    ) AS stale_queued,
                    count(*) FILTER (
                        WHERE status = 'running' AND job_kind = 'leaf'
                          AND (
                            lease_expires_at < NOW()
                            OR (
                                lease_expires_at IS NULL
                                AND started_at < NOW() - (%s * INTERVAL '1 minute')
                            )
                          )
                    ) AS stale_running,
                    count(*) FILTER (WHERE status = 'queued' AND job_kind = 'leaf') AS queued,
                    count(*) FILTER (WHERE status = 'running' AND job_kind = 'leaf') AS running
                FROM sys_collection_job
                """,
                (failed_since_hours, queued_stale_minutes, running_stale_minutes),
            )
            return dict(cursor.fetchone())
