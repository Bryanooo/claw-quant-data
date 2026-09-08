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
        collection_job_id: int | None = None,
    ) -> tuple[dict, bool]:
        with (
            self._connection() as connection,
            connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor,
        ):
            cursor.execute(
                """
                INSERT INTO sys_data_coverage_job
                    (dataset_name, start_date, end_date, idempotency_key,
                     max_attempts, collection_job_id)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (idempotency_key) DO NOTHING
                RETURNING *
                """,
                (
                    dataset_name, start_date, end_date, idempotency_key,
                    max_attempts, collection_job_id,
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

    @staticmethod
    def _date_expression(rule: CoverageRule) -> sql.Composed:
        column = sql.Identifier(rule.date_column)
        if rule.date_storage == DateStorage.COMPACT:
            return sql.SQL("to_date(NULLIF({}, ''), 'YYYYMMDD')").format(column)
        return sql.SQL("{}::date").format(column)

    def actual_partitions(
        self,
        rule: CoverageRule,
        start_date: date,
        end_date: date,
    ) -> list[ActualPartition]:
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
            # Do not let partially persisted rows turn a fail-closed collection
            # result back into a false-positive "present" partition. A later
            # complete collection for the same interface/date resolves it.
            cursor.execute(
                """
                SELECT DISTINCT failed.expected_for AS partition_date
                FROM sys_collection_job AS failed
                WHERE failed.status IN ('failed', 'success')
                  AND failed.completion_status='incomplete'
                  AND failed.expected_for BETWEEN %s AND %s
                  AND COALESCE(
                        failed.api_name,
                        failed.parameters->>'api_name'
                      )=%s
                  AND NOT EXISTS (
                      SELECT 1
                      FROM sys_collection_job AS recovered
                      WHERE recovered.status='success'
                        AND recovered.completion_status IN ('complete', 'verifying')
                        AND recovered.job_id > failed.job_id
                        AND recovered.expected_for=failed.expected_for
                        AND COALESCE(
                              recovered.api_name,
                              recovered.parameters->>'api_name'
                            )=COALESCE(
                              failed.api_name,
                              failed.parameters->>'api_name'
                            )
                  )
                """,
                (start_date, end_date, rule.dataset_name),
            )
            incomplete_dates = {
                row["partition_date"]
                for row in cursor.fetchall()
                if row["partition_date"] is not None
            }
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
                    SELECT DISTINCT expected_for AS partition_date
                    FROM sys_collection_job
                    WHERE status='success' AND completion_status='empty'
                      AND expected_for BETWEEN %s AND %s
                      AND COALESCE(api_name, parameters->>'api_name')=%s
                      AND COALESCE(
                            (completion_evidence->>'verified')::boolean,
                            false
                          )=true
                    """,
                    (start_date, end_date, rule.dataset_name),
                )
                present_dates = {item.partition_date for item in partitions}
                partitions.extend(
                    ActualPartition(
                        partition_date=row["partition_date"],
                        row_count=0,
                        entity_count=None,
                        verified_empty=True,
                        known_incomplete=False,
                    )
                    for row in cursor.fetchall()
                    if row["partition_date"] not in present_dates
                )
            return sorted(partitions, key=lambda item: item.partition_date)

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

    def save_audit(self, job_id: int, result: CoverageAuditResult) -> int:
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
                WITH representative AS (
                    SELECT DISTINCT ON (dataset_name) *
                    FROM sys_data_coverage_audit
                    ORDER BY dataset_name, end_date DESC, start_date ASC,
                             finished_at DESC, audit_id DESC
                )
                SELECT representative.*,
                       current.expected_partitions AS current_expected_partitions,
                       current.present_partitions AS current_present_partitions,
                       current.missing_partitions AS current_missing_partitions,
                       current.partial_partitions AS current_partial_partitions
                FROM representative
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
                    row.get("expected_partitions", 0) > 0
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
