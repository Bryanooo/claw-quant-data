"""PostgreSQL persistence for coverage jobs, audits and partitions."""

from collections.abc import Callable
from contextlib import contextmanager
from datetime import date
from typing import Any

import psycopg2
import psycopg2.extras
from psycopg2 import sql

from service.config import DB_CONFIG
from service.data_coverage.models import (
    ActualPartition,
    CoverageAuditResult,
    CoverageRule,
    CoverageStrategy,
)
from service.data_service.models import DateStorage


class CoverageRepository:
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

    def create_job(
        self,
        dataset_name: str,
        start_date: date,
        end_date: date,
        *,
        idempotency_key: str,
        max_attempts: int = 2,
    ) -> tuple[dict, bool]:
        with (
            self._connection() as connection,
            connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor,
        ):
            cursor.execute(
                """
                INSERT INTO sys_data_coverage_job
                    (dataset_name, start_date, end_date, idempotency_key,
                     max_attempts)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (idempotency_key) DO NOTHING
                RETURNING *
                """,
                (
                    dataset_name, start_date, end_date, idempotency_key,
                    max_attempts,
                ),
            )
            row = cursor.fetchone()
            if row:
                return dict(row), True
            cursor.execute(
                "SELECT * FROM sys_data_coverage_job WHERE idempotency_key = %s",
                (idempotency_key,),
            )
            return dict(cursor.fetchone()), False

    def list_jobs(self, *, status: str | None = None, limit: int = 50) -> list[dict]:
        where = "WHERE status = %s" if status else ""
        params: tuple[Any, ...] = (status, limit) if status else (limit,)
        with (
            self._connection() as connection,
            connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor,
        ):
            cursor.execute(
                f"""
                SELECT * FROM sys_data_coverage_job
                {where}
                ORDER BY created_at DESC, job_id DESC
                LIMIT %s
                """,
                params,
            )
            return [dict(row) for row in cursor.fetchall()]

    def claim_next(self, worker_id: str) -> dict | None:
        with (
            self._connection() as connection,
            connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor,
        ):
            cursor.execute(
                """
                WITH next_job AS (
                    SELECT job_id FROM sys_data_coverage_job
                    WHERE status = 'queued' AND available_at <= NOW()
                    ORDER BY created_at, job_id
                    FOR UPDATE SKIP LOCKED
                    LIMIT 1
                )
                UPDATE sys_data_coverage_job AS job
                SET status = 'running', attempt = attempt + 1,
                    started_at = NOW(), finished_at = NULL,
                    worker_id = %s, error_message = NULL
                FROM next_job
                WHERE job.job_id = next_job.job_id
                RETURNING job.*
                """,
                (worker_id,),
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def finish_job(self, job_id: int) -> None:
        with self._connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE sys_data_coverage_job
                SET status = 'success', finished_at = NOW()
                WHERE job_id = %s AND status = 'running'
                """,
                (job_id,),
            )

    def fail_or_requeue(self, job: dict, error_message: str) -> str:
        retry = job["attempt"] < job["max_attempts"]
        next_status = "queued" if retry else "failed"
        delay = min(30 * (2 ** max(job["attempt"] - 1, 0)), 900)
        with self._connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE sys_data_coverage_job
                SET status = %s,
                    available_at = CASE WHEN %s
                        THEN NOW() + (%s * INTERVAL '1 second')
                        ELSE available_at END,
                    finished_at = CASE WHEN %s THEN NULL ELSE NOW() END,
                    error_message = %s
                WHERE job_id = %s AND status = 'running'
                """,
                (next_status, retry, delay, retry, error_message[:4000], job["job_id"]),
            )
        return next_status

    def recover_stale(self, stale_after_seconds: int) -> int:
        with self._connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE sys_data_coverage_job
                SET status = CASE
                        WHEN attempt < max_attempts THEN 'queued'
                        ELSE 'failed'
                    END,
                    available_at = NOW(), worker_id = NULL,
                    finished_at = CASE
                        WHEN attempt < max_attempts THEN NULL ELSE NOW()
                    END,
                    error_message = CASE
                        WHEN attempt < max_attempts
                            THEN 'auditor stopped before job completed'
                        ELSE 'auditor stopped during final attempt'
                    END
                WHERE status = 'running'
                  AND started_at < NOW() - (%s * INTERVAL '1 second')
                """,
                (stale_after_seconds,),
            )
            return cursor.rowcount

    def recover_orphaned(self, heartbeat_timeout_seconds: int = 60) -> int:
        """Requeue jobs whose owning auditor no longer has a live heartbeat.

        ``running`` is not evidence of liveness.  Matching the persisted
        worker id to the auditor heartbeat lets a replacement container
        recover work immediately without stealing a long audit from a live
        peer.
        """
        with self._connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE sys_data_coverage_job AS job
                SET status = CASE
                        WHEN attempt < max_attempts THEN 'queued'
                        ELSE 'failed'
                    END,
                    available_at = NOW(), worker_id = NULL,
                    finished_at = CASE
                        WHEN attempt < max_attempts THEN NULL ELSE NOW()
                    END,
                    error_message = CASE
                        WHEN attempt < max_attempts
                            THEN 'auditor heartbeat disappeared before job completed'
                        ELSE 'auditor heartbeat disappeared during final attempt'
                    END
                WHERE job.status='running'
                  AND NOT EXISTS (
                      SELECT 1
                      FROM sys_service_heartbeat AS heartbeat
                      WHERE heartbeat.component='auditor'
                        AND heartbeat.instance_id=job.worker_id
                        AND heartbeat.last_seen_at >= NOW() - (
                            %s * INTERVAL '1 second'
                        )
                  )
                """,
                (heartbeat_timeout_seconds,),
            )
            return cursor.rowcount

    def requeue_stale_rule_audits(
        self,
        dataset_name: str,
        *,
        rule_revision: int,
        limit: int = 500,
    ) -> int:
        """Re-run audits produced by an obsolete coverage-rule revision.

        Coverage is an independent data-plane concern in V2.  Re-auditing a
        changed rule must never mutate or require a retired V1 execution row.
        """
        with self._connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                WITH candidates AS (
                    SELECT coverage.job_id
                    FROM sys_data_coverage_job AS coverage
                    JOIN sys_data_coverage_audit AS audit
                      ON audit.job_id=coverage.job_id
                    WHERE audit.dataset_name=%s
                      AND audit.status='gaps'
                      AND CASE
                            WHEN COALESCE(audit.evidence->>'rule_revision', '')
                                 ~ '^[0-9]+$'
                            THEN (audit.evidence->>'rule_revision')::integer
                            ELSE 0
                          END < %s
                      AND coverage.status IN ('success', 'failed')
                    ORDER BY coverage.job_id
                    FOR UPDATE OF coverage SKIP LOCKED
                    LIMIT %s
                )
                UPDATE sys_data_coverage_job AS coverage
                SET status='queued', attempt=0, available_at=NOW(),
                    started_at=NULL, finished_at=NULL, worker_id=NULL,
                    error_message=NULL
                FROM candidates
                WHERE coverage.job_id=candidates.job_id
                """,
                (dataset_name, rule_revision, limit),
            )
            return cursor.rowcount

    @staticmethod
    def _date_expression(rule: CoverageRule) -> sql.Composed:
        column = sql.Identifier(rule.date_column)
        # Some upstream monthly series (for example cn_lpr) persist the
        # publication day as a real DATE, while the coverage contract is one
        # observation per calendar month. Normalize those physical dates to
        # the same month-end key produced by ``completed_months``.
        if (
            rule.strategy == CoverageStrategy.CALENDAR_MONTHLY
            and rule.date_storage == DateStorage.DATE
        ):
            return sql.SQL(
                "(date_trunc('month', {}::date) + "
                "INTERVAL '1 month - 1 day')::date"
            ).format(column)
        if rule.date_storage == DateStorage.COMPACT:
            return sql.SQL("to_date(NULLIF({}, ''), 'YYYYMMDD')").format(column)
        if rule.date_storage == DateStorage.MONTH:
            return sql.SQL(
                "(to_date(NULLIF({}, ''), 'YYYYMM') + "
                "INTERVAL '1 month - 1 day')::date"
            ).format(column)
        if rule.date_storage == DateStorage.QUARTER:
            return sql.SQL(
                "(make_date(split_part(NULLIF({}, ''), 'Q', 1)::integer, "
                "split_part(NULLIF({}, ''), 'Q', 2)::integer * 3, 1) + "
                "INTERVAL '1 month - 1 day')::date"
            ).format(column, column)
        return sql.SQL("{}::date").format(column)

    def actual_partitions(
        self,
        rule: CoverageRule,
        start_date: date,
        end_date: date,
        *,
        verified_transport_dates: set[date] | None = None,
        verified_empty_transport_dates: set[date] | None = None,
    ) -> list[ActualPartition]:
        current_transport_dates = verified_transport_dates or set()
        current_empty_dates = verified_empty_transport_dates or set()
        collection_api_name = rule.collection_api_name or rule.dataset_name
        date_expression = self._date_expression(rule)
        entity_expression = (
            sql.SQL("count(DISTINCT {})").format(sql.Identifier(rule.entity_column))
            if rule.entity_column
            else sql.SQL("NULL::bigint")
        )
        statement = sql.SQL(
            """
            SELECT {date_expression} AS partition_date,
                   count(*)::bigint AS row_count,
                   {entity_expression}::bigint AS entity_count
            FROM {table}
            WHERE {date_expression} BETWEEN %s AND %s
            GROUP BY {date_expression}
            ORDER BY {date_expression}
            """
        ).format(
            date_expression=date_expression,
            entity_expression=entity_expression,
            table=sql.Identifier(rule.table),
        )
        with (
            self._connection() as connection,
            connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor,
        ):
            cursor.execute(statement, (start_date, end_date))
            partitions = [
                ActualPartition(
                    partition_date=row["partition_date"],
                    row_count=int(row["row_count"]),
                    entity_count=(
                        int(row["entity_count"])
                        if row["entity_count"] is not None
                        else None
                    ),
                )
                for row in cursor.fetchall()
                if row["partition_date"] is not None
            ]
            # V2 dataset state is the authoritative data fact.  A current
            # gaps/partial state keeps physical rows fail-closed until a later
            # V2 validation publishes a complete state for the same period.
            cursor.execute(
                """
                SELECT observation_start AS partition_date
                FROM (
                    SELECT DISTINCT ON (dataset_name, observation_key)
                           dataset_name, observation_key, observation_start,
                           data_status
                    FROM orchestration_v2.dataset_state
                    WHERE dataset_name=%s
                      AND observation_start BETWEEN %s AND %s
                    ORDER BY dataset_name, observation_key, revision DESC,
                             updated_at DESC, dataset_state_id DESC
                ) AS current_state
                WHERE data_status IN ('gaps','partial','indeterminate')
                """,
                (rule.dataset_name, start_date, end_date),
            )
            incomplete_dates = {
                row["partition_date"]
                for row in cursor.fetchall()
                if row["partition_date"] is not None
            }
            transport_proof_dates: set[date] = set()
            if rule.require_transport_proof:
                if rule.strategy == CoverageStrategy.CALENDAR_MONTHLY:
                    cursor.execute(
                        """
                        SELECT DISTINCT execution.observation_end AS partition_date
                        FROM orchestration_v2.task_execution AS execution
                        JOIN orchestration_v2.task_execution_event AS event
                          USING (task_execution_id)
                        WHERE execution.task_key=%s
                          AND execution.status='success'
                          AND execution.observation_end BETWEEN %s AND %s
                          AND event.event_type='node.acquire.request_completed'
                          AND event.payload->'completion_evidence'->>'verified'='true'
                        """,
                        (collection_api_name, start_date, end_date),
                    )
                else:
                    cursor.execute(
                        """
                        SELECT DISTINCT execution.observation_end AS partition_date
                        FROM orchestration_v2.task_execution AS execution
                        JOIN orchestration_v2.task_execution_event AS event
                          USING (task_execution_id)
                        WHERE execution.task_key=%s
                          AND execution.status='success'
                          AND execution.observation_end BETWEEN %s AND %s
                          AND event.event_type='node.acquire.request_completed'
                          AND event.payload->'completion_evidence'->>'verified'='true'
                        """,
                        (collection_api_name, start_date, end_date),
                    )
                transport_proof_dates = {
                    row["partition_date"]
                    for row in cursor.fetchall()
                    if row["partition_date"] is not None
                }
                incomplete_dates.update(
                    item.partition_date
                    for item in partitions
                    if item.partition_date not in transport_proof_dates
                )
            # A verified acquire event is newer, execution-scoped evidence
            # for the same logical period. It may retire a stale legacy
            # ``completion_status=incomplete`` marker, but it does not make a
            # missing/undersized business partition complete; the calculator
            # still evaluates those conditions below.
            transport_proof_dates.update(current_transport_dates)
            incomplete_dates.difference_update(current_transport_dates)
            if incomplete_dates:
                partitions = [
                    ActualPartition(
                        partition_date=item.partition_date,
                        row_count=item.row_count,
                        entity_count=item.entity_count,
                        verified_empty=item.verified_empty,
                        known_incomplete=item.partition_date in incomplete_dates,
                    )
                    for item in partitions
                ]
            if rule.accept_verified_empty:
                cursor.execute(
                    """
                    -- V2 repair executions describe a complete logical period.
                    -- The materialized partition key for accepted empty
                    -- monthly/quarterly scopes is the period end (daily scopes
                    -- have identical start/end dates).  Reading the period
                    -- start here made a provider-verified empty quarter look
                    -- missing again during the next independent full audit.
                    SELECT DISTINCT observation_end AS partition_date
                    FROM orchestration_v2.dataset_state
                    WHERE dataset_name=%s
                      AND data_status='empty_verified' AND ready
                      AND observation_end BETWEEN %s AND %s
                    """,
                    (rule.dataset_name, start_date, end_date),
                )
                persisted_empty_dates = {
                    row["partition_date"] for row in cursor.fetchall()
                }
                # The validate node runs before its dataset_state is
                # published.  Accept an authoritative zero-row result from
                # the *current* acquire node without waiting for a second
                # execution, but never infer emptiness from a non-empty
                # transport whose rows landed under the wrong partition.
                verified_empty_dates = persisted_empty_dates | current_empty_dates
                present_dates = {item.partition_date for item in partitions}
                partitions.extend(
                    ActualPartition(
                        partition_date=partition_date,
                        row_count=0,
                        entity_count=None,
                        verified_empty=True,
                        known_incomplete=False,
                    )
                    for partition_date in verified_empty_dates
                    if partition_date not in present_dates
                    and (
                        not rule.require_transport_proof
                        or partition_date in transport_proof_dates
                    )
                )
            return sorted(partitions, key=lambda item: item.partition_date)

    def snapshot_evidence(self, rule: CoverageRule) -> dict:
        """Return fail-closed proof for a non-temporal exhaustive snapshot."""
        api_name = rule.collection_api_name or rule.dataset_name
        count_statement = sql.SQL("SELECT count(*)::bigint AS count FROM {}").format(
            sql.Identifier(rule.table)
        )
        with (
            self._connection() as connection,
            connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor,
        ):
            cursor.execute(count_statement)
            row_count = int(cursor.fetchone()["count"])
            cursor.execute(
                """
                SELECT execution.task_execution_id AS job_id,
                       execution.status,
                       state.data_status AS completion_status,
                       state.actual_count AS rows_fetched,
                       state.actual_count AS rows_inserted,
                       execution.finished_at,
                       state.validation_summary AS completion_evidence
                FROM orchestration_v2.task_execution AS execution
                JOIN orchestration_v2.dataset_state AS state
                  ON state.source_execution_id=execution.task_execution_id
                 AND state.dataset_name=%s
                WHERE execution.task_key=%s AND execution.status='success'
                  AND state.ready
                ORDER BY execution.finished_at DESC NULLS LAST,
                         execution.task_execution_id DESC
                LIMIT 1
                """,
                (rule.dataset_name, api_name),
            )
            success = cursor.fetchone()
            cursor.execute(
                """
                SELECT count(*)::bigint AS failures
                FROM orchestration_v2.task_execution AS failed
                WHERE failed.task_key=%s AND failed.status='attention'
                  AND NOT EXISTS (
                      SELECT 1
                      FROM orchestration_v2.task_execution AS recovered
                      WHERE recovered.task_key=failed.task_key
                        AND recovered.observation_key=failed.observation_key
                        AND recovered.status='success'
                        AND recovered.task_execution_id > failed.task_execution_id
                  )
                """,
                (api_name,),
            )
            unresolved_failures = int(cursor.fetchone()["failures"])
            cursor.execute(
                """
                SELECT count(*)::bigint AS active
                FROM orchestration_v2.task_execution
                WHERE task_key=%s
                  AND purpose IN ('backfill','initialization','repair')
                  AND status IN (
                    'created','queued','running','waiting_dependency','retrying',
                    'validating','publishing'
                  )
                """,
                (api_name,),
            )
            active_history_jobs = int(cursor.fetchone()["active"])
        evidence = dict(success["completion_evidence"] or {}) if success else {}
        verified = bool(evidence.get("verified")) if success else False
        return {
            "api_name": api_name,
            "row_count": row_count,
            "latest_success": dict(success) if success else None,
            "verified": verified,
            "unresolved_failures": unresolved_failures,
            "active_history_jobs": active_history_jobs,
        }

    def collection_scope_evidence(self, rule: CoverageRule) -> dict:
        """Audit terminal transport proof for every declared historical scope."""
        api_name = rule.collection_api_name or rule.dataset_name
        with (
            self._connection() as connection,
            connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor,
        ):
            cursor.execute(
                f"""
                SELECT
                    count(*) FILTER (
                        WHERE purpose IN ('backfill','initialization','repair')
                    )::bigint AS declared_jobs,
                    count(*) FILTER (
                        WHERE purpose IN ('backfill','initialization','repair')
                          AND status IN (
                            'created','queued','running','waiting_dependency',
                            'retrying','validating','publishing'
                          )
                    )::bigint AS active_jobs,
                    count(*) FILTER (
                        WHERE purpose IN ('backfill','initialization','repair')
                          AND status='success'
                    )::bigint AS verified_terminal_jobs,
                    count(*) FILTER (
                        WHERE status='attention'
                          AND NOT EXISTS (
                            SELECT 1
                            FROM orchestration_v2.task_execution AS recovered
                            WHERE recovered.task_key=execution.task_key
                              AND recovered.observation_key=execution.observation_key
                              AND recovered.status='success'
                              AND recovered.task_execution_id > execution.task_execution_id
                          )
                    )::bigint AS unresolved_failures
                FROM orchestration_v2.task_execution AS execution
                WHERE execution.task_key=%s
                """,
                (api_name,),
            )
            row = dict(cursor.fetchone())
        return {
            "api_name": api_name,
            **{key: int(value or 0) for key, value in row.items()},
        }

    def expected_market_partitions(
        self,
        rule: CoverageRule,
        start_date: date,
        cutoff_date: date,
    ) -> list[date]:
        if start_date > cutoff_date:
            return []
        if rule.strategy == CoverageStrategy.TRADING_DAILY:
            statement = """
                SELECT cal_date AS partition_date
                FROM trade_cal
                WHERE exchange = %s AND is_open = 1
                  AND cal_date BETWEEN %s AND %s
                ORDER BY cal_date
            """
            params = (rule.calendar_exchange, start_date, cutoff_date)
        elif rule.strategy == CoverageStrategy.TRADING_WEEKLY:
            statement = """
                SELECT max(cal_date) AS partition_date
                FROM trade_cal
                WHERE exchange = %s AND is_open = 1
                  AND cal_date BETWEEN %s AND %s
                  AND date_trunc('week', cal_date)::date + 6 <= %s
                GROUP BY date_trunc('week', cal_date)
                ORDER BY partition_date
            """
            params = (
                rule.calendar_exchange,
                start_date,
                cutoff_date,
                cutoff_date,
            )
        elif rule.strategy == CoverageStrategy.TRADING_MONTHLY:
            statement = """
                SELECT max(cal_date) AS partition_date
                FROM trade_cal
                WHERE exchange = %s AND is_open = 1
                  AND cal_date BETWEEN %s AND %s
                  AND (date_trunc('month', cal_date)
                       + INTERVAL '1 month - 1 day')::date <= %s
                GROUP BY date_trunc('month', cal_date)
                ORDER BY partition_date
            """
            params = (
                rule.calendar_exchange,
                start_date,
                cutoff_date,
                cutoff_date,
            )
        else:
            return []
        with (
            self._connection() as connection,
            connection.cursor() as cursor,
        ):
            cursor.execute(statement, params)
            return [row[0] for row in cursor.fetchall()]

    def expected_entity_count(self, rule: CoverageRule, partition_date: date) -> int | None:
        """Estimate the point-in-time universe for supported reference tables."""
        # Through 1992 the mainland market contained only a handful of symbols;
        # one legitimate non-trading symbol makes a percentage threshold
        # unstable. daily and daily_basic are independent upstream endpoints,
        # so agreement between their exact-date universes is the strongest
        # available historical baseline. From 1993 onward the larger listed
        # universe makes the stock_basic ratio useful for detecting staggered
        # exchange publication again.
        if partition_date < date(1993, 1, 1):
            historical_counterparts = {
                "stock_daily": ("tushare_current_daily_basic", "trade_date"),
                "stock_daily_basic": ("daily", "trade_date"),
            }
            counterpart = historical_counterparts.get(rule.dataset_name)
            if counterpart:
                table, date_column = counterpart
                with self._connection() as connection, connection.cursor() as cursor:
                    cursor.execute(
                        sql.SQL(
                            "SELECT count(DISTINCT ts_code) FROM {} WHERE {}=%s"
                        ).format(sql.Identifier(table), sql.Identifier(date_column)),
                        (partition_date,),
                    )
                    value = int(cursor.fetchone()[0])
                    return value or None
        statements = {
            "stock_basic": """
                SELECT count(*) FROM stock_basic
                WHERE NULLIF(list_date, '') IS NOT NULL
                  AND to_date(list_date, 'YYYYMMDD') <= %s
                  AND (NULLIF(delist_date, '') IS NULL
                       OR to_date(delist_date, 'YYYYMMDD') >= %s)
            """,
            "index_basic": """
                SELECT count(*) FROM index_basic
                WHERE NULLIF(list_date, '') IS NOT NULL
                  AND to_date(list_date, 'YYYYMMDD') <= %s
                  -- Tushare's index_daily contract explicitly excludes SW
                  -- industry indexes; those are collected by sw_daily.
                  AND COALESCE(market, '') <> 'SW'
            """,
            "ths_index": """
                SELECT count(*) FROM ths_index
                WHERE NULLIF(list_date, '') IS NULL
                   OR to_date(list_date, 'YYYYMMDD') <= %s
            """,
            # The Beijing Stock Exchange enabled margin trading on 2023-02-13.
            # Current daily summaries are complete only when SSE, SZSE and BSE
            # are all present; older partitions legitimately contain two.
            "margin_exchanges": """
                SELECT CASE WHEN %s >= DATE '2023-02-13' THEN 3 ELSE 2 END
            """,
            # ``margin_detail`` contains only margin-eligible securities, so
            # all listed stocks are not a precise denominator.  The daily
            # ``margin_secs`` universe is the point-in-time contract for this
            # dataset; when that reference date is unavailable the calculator
            # conservatively skips entity-ratio enforcement for that date.
            "margin_secs": """
                SELECT count(DISTINCT ts_code) FROM margin_secs
                WHERE trade_date=to_char(%s::date, 'YYYYMMDD')
            """,
        }
        statement = statements.get(rule.entity_reference)
        if not statement:
            return None
        params = (
            (partition_date, partition_date)
            if rule.entity_reference == "stock_basic"
            else (partition_date,)
        )
        with self._connection() as connection, connection.cursor() as cursor:
            cursor.execute(statement, params)
            value = int(cursor.fetchone()[0])
            return value or None

    def expected_entity_counts(
        self, rule: CoverageRule, partition_dates: list[date]
    ) -> dict[date, int | None]:
        """Batch point-in-time denominators to avoid one query per partition."""
        dates = sorted(set(partition_dates))
        if not dates or not rule.entity_reference:
            return {}
        result: dict[date, int | None] = {}
        early_dates = (
            [item for item in dates if item < date(1993, 1, 1)]
            if rule.dataset_name in {"stock_daily", "stock_daily_basic"}
            else []
        )
        if early_dates:
            counterpart = {
                "stock_daily": ("tushare_current_daily_basic", "trade_date"),
                "stock_daily_basic": ("daily", "trade_date"),
            }[rule.dataset_name]
            with self._connection() as connection, connection.cursor() as cursor:
                cursor.execute(
                    sql.SQL(
                        "SELECT {date_column}::date, count(DISTINCT ts_code) "
                        "FROM {table} WHERE {date_column}::date=ANY(%s::date[]) "
                        "GROUP BY {date_column}::date"
                    ).format(
                        table=sql.Identifier(counterpart[0]),
                        date_column=sql.Identifier(counterpart[1]),
                    ),
                    (early_dates,),
                )
                result.update({row[0]: int(row[1]) or None for row in cursor.fetchall()})
        remaining = [item for item in dates if item not in set(early_dates)]
        if not remaining:
            return result
        statements = {
            "stock_basic": """
                SELECT target.partition_date, count(stock.*)::bigint
                FROM unnest(%s::date[]) AS target(partition_date)
                LEFT JOIN stock_basic AS stock
                  ON NULLIF(stock.list_date, '') IS NOT NULL
                 AND to_date(stock.list_date, 'YYYYMMDD') <= target.partition_date
                 AND (NULLIF(stock.delist_date, '') IS NULL
                      OR to_date(stock.delist_date, 'YYYYMMDD') >= target.partition_date)
                GROUP BY target.partition_date
            """,
            "index_basic": """
                SELECT target.partition_date, count(index_row.*)::bigint
                FROM unnest(%s::date[]) AS target(partition_date)
                LEFT JOIN index_basic AS index_row
                  ON NULLIF(index_row.list_date, '') IS NOT NULL
                 AND to_date(index_row.list_date, 'YYYYMMDD') <= target.partition_date
                 AND COALESCE(index_row.market, '') <> 'SW'
                GROUP BY target.partition_date
            """,
            "ths_index": """
                SELECT target.partition_date, count(index_row.*)::bigint
                FROM unnest(%s::date[]) AS target(partition_date)
                LEFT JOIN ths_index AS index_row
                  ON (NULLIF(index_row.list_date, '') IS NULL
                      OR to_date(index_row.list_date, 'YYYYMMDD') <= target.partition_date)
                GROUP BY target.partition_date
            """,
            "margin_exchanges": """
                SELECT partition_date,
                       CASE WHEN partition_date >= DATE '2023-02-13' THEN 3 ELSE 2 END
                FROM unnest(%s::date[]) AS target(partition_date)
            """,
            "margin_secs": """
                SELECT target.partition_date, count(DISTINCT universe.ts_code)::bigint
                FROM unnest(%s::date[]) AS target(partition_date)
                LEFT JOIN margin_secs AS universe
                  ON universe.trade_date=to_char(target.partition_date, 'YYYYMMDD')
                GROUP BY target.partition_date
            """,
        }
        statement = statements.get(rule.entity_reference)
        if not statement:
            return {
                item: self.expected_entity_count(rule, item) for item in dates
            }
        with self._connection() as connection, connection.cursor() as cursor:
            cursor.execute(statement, (remaining,))
            result.update(
                {row[0]: (int(row[1]) or None) for row in cursor.fetchall()}
            )
        return result

    def calendar_coverage(
        self,
        exchange: str,
        start_date: date,
        end_date: date,
    ) -> tuple[date | None, date | None, int]:
        with self._connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT min(cal_date), max(cal_date),
                       count(DISTINCT cal_date) FILTER (
                           WHERE cal_date BETWEEN %s AND %s
                       )
                FROM trade_cal
                WHERE exchange = %s
                """,
                (start_date, end_date, exchange),
            )
            row = cursor.fetchone()
            return row[0], row[1], int(row[2])

    def save_audit(self, job_id: int | None, result: CoverageAuditResult) -> int:
        """Persist an audit from the audit queue or V2 validation.

        ``job_id`` is intentionally nullable in the schema. V2 validation is
        owned by its task execution/event ledger, so manufacturing a second
        coverage job merely to refresh the shared materialized partition
        state would create a second and misleading execution identity.
        """
        with self._connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO sys_data_coverage_audit
                    (job_id, dataset_name, strategy, start_date, end_date,
                     expected_partitions, present_partitions, missing_partitions,
                     observed_partitions, partial_partitions, coverage_ratio,
                     status, evidence)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (job_id) WHERE job_id IS NOT NULL DO UPDATE SET
                    dataset_name = EXCLUDED.dataset_name,
                    strategy = EXCLUDED.strategy,
                    start_date = EXCLUDED.start_date,
                    end_date = EXCLUDED.end_date,
                    expected_partitions = EXCLUDED.expected_partitions,
                    present_partitions = EXCLUDED.present_partitions,
                    missing_partitions = EXCLUDED.missing_partitions,
                    observed_partitions = EXCLUDED.observed_partitions,
                    partial_partitions = EXCLUDED.partial_partitions,
                    coverage_ratio = EXCLUDED.coverage_ratio,
                    status = EXCLUDED.status,
                    evidence = EXCLUDED.evidence,
                    finished_at = NOW()
                RETURNING audit_id
                """,
                (
                    job_id,
                    result.dataset_name,
                    result.strategy,
                    result.start_date,
                    result.end_date,
                    result.expected_partitions,
                    result.present_partitions,
                    result.missing_partitions,
                    result.observed_partitions,
                    result.partial_partitions,
                    result.coverage_ratio,
                    result.status,
                    psycopg2.extras.Json(result.evidence),
                ),
            )
            audit_id = int(cursor.fetchone()[0])
            # ``sys_data_coverage_partition`` is the current materialized
            # ledger, while audit summaries above remain immutable history.
            # A rule revision may legitimately remove old expectations (for
            # example a newly verified provider availability boundary). Merely
            # upserting the new rows leaves those obsolete missing partitions
            # behind and makes the API report the superseded rule forever.
            # Atomically replace only this audit's bounded range.
            cursor.execute(
                """
                DELETE FROM sys_data_coverage_partition
                WHERE dataset_name=%s
                  AND partition_date BETWEEN %s AND %s
                """,
                (result.dataset_name, result.start_date, result.end_date),
            )
            if result.partitions:
                values = [
                    (
                        result.dataset_name,
                        item.partition_date,
                        item.status,
                        item.row_count,
                        item.entity_count,
                        item.expected_entity_count,
                        item.entity_coverage_ratio,
                        item.expected,
                        psycopg2.extras.Json(
                            {"semantics": "partition_and_entity_completeness"}
                        ),
                        audit_id,
                    )
                    for item in result.partitions
                ]
                psycopg2.extras.execute_values(
                    cursor,
                    """
                    INSERT INTO sys_data_coverage_partition
                        (dataset_name, partition_date, status, row_count,
                         entity_count, expected_entity_count,
                         entity_coverage_ratio, expected, evidence, audit_id)
                    VALUES %s
                    ON CONFLICT (dataset_name, partition_date) DO UPDATE SET
                        status = EXCLUDED.status,
                        row_count = EXCLUDED.row_count,
                        entity_count = EXCLUDED.entity_count,
                        expected_entity_count = EXCLUDED.expected_entity_count,
                        entity_coverage_ratio = EXCLUDED.entity_coverage_ratio,
                        expected = EXCLUDED.expected,
                        evidence = EXCLUDED.evidence,
                        audit_id = EXCLUDED.audit_id,
                        checked_at = NOW()
                    """,
                    values,
                )
            return audit_id

    def latest_audits(self) -> dict[str, dict]:
        """Return the most representative current audit for each dataset.

        A targeted repair can audit an old single day after the regular
        rolling-window audit has finished.  Ordering only by execution time
        made that historical point check replace the current health view.  A
        newer covered end date is authoritative; for the same end date the
        wider interval is more representative, with execution time used only
        as the final tie-breaker.
        """
        with (
            self._connection() as connection,
            connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor,
        ):
            cursor.execute(
                """
                WITH trusted_ranges AS (
                    SELECT dataset_name, start_date, end_date,
                           max(end_date) OVER (
                               PARTITION BY dataset_name
                               ORDER BY start_date, end_date
                               ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
                           ) AS previous_frontier
                    FROM sys_data_coverage_audit
                    WHERE status IN ('complete', 'empty')
                      AND missing_partitions=0
                      AND partial_partitions=0
                ), marked_ranges AS (
                    SELECT *,
                           CASE
                               WHEN previous_frontier IS NULL THEN 1
                               WHEN start_date <= previous_frontier + 1 THEN 0
                               WHEN EXISTS (
                                   SELECT 1
                                   FROM trade_cal
                                   WHERE exchange='SSE' AND is_open=1
                                     AND cal_date > previous_frontier
                                     AND cal_date < start_date
                               ) THEN 1
                               ELSE 0
                           END AS starts_new_span
                    FROM trusted_ranges
                ), grouped_ranges AS (
                    SELECT *,
                           sum(starts_new_span) OVER (
                               PARTITION BY dataset_name
                               ORDER BY start_date, end_date
                           ) AS span_id
                    FROM marked_ranges
                ), verified_spans AS (
                    SELECT dataset_name, span_id,
                           min(start_date) AS verified_start_date,
                           max(end_date) AS verified_end_date
                    FROM grouped_ranges
                    GROUP BY dataset_name, span_id
                ), representative AS (
                    SELECT DISTINCT ON (dataset_name) *
                    FROM sys_data_coverage_audit
                    ORDER BY dataset_name, end_date DESC, start_date ASC,
                             finished_at DESC, audit_id DESC
                )
                SELECT representative.*,
                       span.verified_start_date,
                       span.verified_end_date,
                       current.expected_partitions AS current_expected_partitions,
                       current.present_partitions AS current_present_partitions,
                       current.missing_partitions AS current_missing_partitions,
                       current.partial_partitions AS current_partial_partitions
                FROM representative
                LEFT JOIN LATERAL (
                    SELECT verified_start_date, verified_end_date
                    FROM verified_spans
                    WHERE verified_spans.dataset_name=representative.dataset_name
                      AND verified_start_date <= representative.end_date
                      AND verified_end_date >= representative.end_date
                    ORDER BY verified_start_date
                    LIMIT 1
                ) AS span ON TRUE
                LEFT JOIN LATERAL (
                    SELECT
                        count(*) FILTER (WHERE partition.expected) AS expected_partitions,
                        count(*) FILTER (
                            WHERE partition.expected AND partition.status='present'
                        ) AS present_partitions,
                        count(*) FILTER (
                            WHERE partition.expected AND partition.status='missing'
                        ) AS missing_partitions,
                        count(*) FILTER (
                            WHERE partition.expected AND partition.status='partial'
                        ) AS partial_partitions
                    FROM sys_data_coverage_partition AS partition
                    WHERE partition.dataset_name=representative.dataset_name
                      AND partition.partition_date BETWEEN
                          representative.start_date AND representative.end_date
                ) AS current ON TRUE
                ORDER BY representative.dataset_name
                """
            )
            result = {}
            for raw in cursor.fetchall():
                row = dict(raw)
                current_expected = int(
                    row.pop("current_expected_partitions") or 0
                )
                current_present = int(
                    row.pop("current_present_partitions") or 0
                )
                current_missing = int(
                    row.pop("current_missing_partitions") or 0
                )
                current_partial = int(
                    row.pop("current_partial_partitions") or 0
                )
                # A narrow post-repair audit updates the durable partition
                # ledger.  When every partition represented by the wider
                # health audit has since been checked, that current ledger is
                # more authoritative than the old aggregate counters. This
                # prevents a repaired day from remaining a false red alert
                # until tomorrow's rolling audit.
                if (
                    row.get("strategy") not in {
                        CoverageStrategy.OBSERVED_ONLY.value,
                        CoverageStrategy.NON_TEMPORAL.value,
                    }
                    and row.get("expected_partitions", 0) > 0
                    and current_expected >= int(row["expected_partitions"])
                ):
                    row["present_partitions"] = current_present
                    row["missing_partitions"] = current_missing
                    row["partial_partitions"] = current_partial
                    row["coverage_ratio"] = (
                        current_present / current_expected
                        if current_expected
                        else None
                    )
                    row["status"] = (
                        "gaps" if current_missing or current_partial else "complete"
                    )
                result[row["dataset_name"]] = row
            return result

    def list_partitions(
        self,
        dataset_name: str,
        *,
        start_date: date | None,
        end_date: date | None,
        status: str | None,
        limit: int,
    ) -> list[dict]:
        conditions = ["dataset_name = %s"]
        params: list[Any] = [dataset_name]
        if start_date:
            conditions.append("partition_date >= %s")
            params.append(start_date)
        if end_date:
            conditions.append("partition_date <= %s")
            params.append(end_date)
        if status:
            if status == "problem":
                conditions.append("status IN ('missing', 'partial')")
            else:
                conditions.append("status = %s")
                params.append(status)
        with (
            self._connection() as connection,
            connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor,
        ):
            cursor.execute(
                f"""
                SELECT dataset_name, partition_date, status, row_count,
                       entity_count, expected_entity_count, entity_coverage_ratio,
                       expected, evidence, audit_id, checked_at
                FROM sys_data_coverage_partition
                WHERE {' AND '.join(conditions)}
                ORDER BY partition_date DESC
                LIMIT %s
                """,
                (*params, limit),
            )
            return [dict(row) for row in cursor.fetchall()]

    def data_calendar(self, start_date: date, end_date: date) -> list[dict]:
        """Aggregate the durable audit ledger by *data* date.

        The calendar deliberately reads ``sys_data_coverage_partition`` rather
        than an orchestration-engine table.  This keeps historical evidence
        visible across scheduler/runtime migrations and prevents a UI from
        exposing internal generation labels such as V1/V2.
        """
        with (
            self._connection() as connection,
            connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor,
        ):
            cursor.execute(
                """
                SELECT partition_date AS data_date,
                       count(*)::integer AS dataset_states,
                       count(*) FILTER (
                           WHERE expected AND status='present'
                       )::integer AS ready,
                       count(*) FILTER (
                           WHERE NOT expected AND status='observed_only'
                       )::integer AS observed,
                       count(*) FILTER (
                           WHERE status IN ('missing','partial')
                       )::integer AS problems,
                       count(*) FILTER (WHERE status='pending')::integer AS active,
                       COALESCE(sum(row_count), 0)::bigint AS rows
                FROM sys_data_coverage_partition
                WHERE partition_date BETWEEN %s AND %s
                GROUP BY partition_date
                ORDER BY partition_date
                """,
                (start_date, end_date),
            )
            return [dict(row) for row in cursor.fetchall()]

    def calendar_day(self, data_date: date) -> list[dict]:
        """Return every audited dataset state for one logical data date."""
        with (
            self._connection() as connection,
            connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor,
        ):
            cursor.execute(
                """
                SELECT dataset_name, partition_date, status, row_count,
                       entity_count, expected_entity_count,
                       entity_coverage_ratio, expected, checked_at
                FROM sys_data_coverage_partition
                WHERE partition_date=%s
                ORDER BY CASE status
                           WHEN 'missing' THEN 0 WHEN 'partial' THEN 1
                           WHEN 'pending' THEN 2 WHEN 'present' THEN 3 ELSE 4
                         END,
                         dataset_name
                """,
                (data_date,),
            )
            return [dict(row) for row in cursor.fetchall()]

    def covering_audit(
        self,
        dataset_name: str,
        *,
        start_date: date | None,
        end_date: date | None,
    ) -> dict | None:
        """Return the narrowest completed audit that proves the requested range."""
        conditions = ["dataset_name=%s"]
        params: list[Any] = [dataset_name]
        if start_date:
            conditions.append("start_date <= %s")
            params.append(start_date)
        if end_date:
            conditions.append("end_date >= %s")
            params.append(end_date)
        with (
            self._connection() as connection,
            connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor,
        ):
            cursor.execute(
                f"""
                SELECT audit_id, status, start_date, end_date, finished_at
                FROM sys_data_coverage_audit
                WHERE {' AND '.join(conditions)}
                ORDER BY (end_date - start_date), finished_at DESC, audit_id DESC
                LIMIT 1
                """,
                params,
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def recent_missing(self, dataset_name: str, limit: int = 10) -> list[date]:
        rows = self.list_partitions(
            dataset_name,
            start_date=None,
            end_date=None,
            status="missing",
            limit=limit,
        )
        return [row["partition_date"] for row in rows]

    def recent_missing_by_dataset(self, limit: int = 10) -> dict[str, list[date]]:
        with (
            self._connection() as connection,
            connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor,
        ):
            cursor.execute(
                """
                SELECT dataset_name,
                       array_agg(partition_date ORDER BY partition_date DESC) AS dates
                FROM (
                    SELECT dataset_name, partition_date,
                           row_number() OVER (
                               PARTITION BY dataset_name
                               ORDER BY partition_date DESC
                           ) AS position
                    FROM sys_data_coverage_partition
                    WHERE status IN ('missing', 'partial')
                ) ranked
                WHERE position <= %s
                GROUP BY dataset_name
                """,
                (limit,),
            )
            return {row["dataset_name"]: list(row["dates"]) for row in cursor.fetchall()}

    def queue_counts(self) -> dict:
        with (
            self._connection() as connection,
            connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor,
        ):
            cursor.execute(
                """
                SELECT count(*) FILTER (WHERE status = 'queued') AS queued,
                       count(*) FILTER (WHERE status = 'running') AS running,
                       count(*) FILTER (
                           WHERE status = 'failed'
                             AND NOT EXISTS (
                                 SELECT 1
                                 FROM sys_data_coverage_job AS recovered
                                 WHERE recovered.dataset_name = job.dataset_name
                                   AND recovered.status = 'success'
                                   AND recovered.job_id > job.job_id
                                   AND recovered.start_date <= job.start_date
                                   AND recovered.end_date >= job.end_date
                             )
                       ) AS failed
                FROM sys_data_coverage_job AS job
                """
            )
            return dict(cursor.fetchone())
