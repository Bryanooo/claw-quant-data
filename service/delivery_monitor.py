"""Truthful business-day delivery planning and progress reporting."""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Iterable
from datetime import date, datetime, time, timedelta
from typing import Any

import psycopg2
import psycopg2.extras
from psycopg2 import sql

from service.clock import SHANGHAI_TIMEZONE, business_now
from service.config import DB_CONFIG
from service.data_coverage.models import CoverageStrategy
from service.data_coverage.registry import COVERAGE_RULES
from service.data_service.models import DateStorage
from service.fanout_scheduling import SCHEDULED_FANOUT_RECIPES, _recipe_scope
from service.tushare_catalog import TushareInterfaceCatalog
from service.tushare_policy import TusharePolicyRegistry
from service.tushare_scheduling import (
    DEDICATED_SCHEDULED_APIS,
    _period_key,
    _resolved_scope,
)


CONTROL_SCHEDULES = {
    "inspector_15min",
    "tushare_policy_dispatch",
    "data_coverage_dispatch",
    "service_heartbeat",
    "collection_schedule_reconciler",
    "collection_initialization_reconciler",
    "fanout_campaign_reconciler",
    "delivery_plan_reconciler",
}


def _local_datetime(day: date, value: time) -> datetime:
    return datetime.combine(day, value, SHANGHAI_TIMEZONE)


def _json_time(value: Any) -> Any:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


class DeliveryPlanRepository:
    """PostgreSQL persistence and execution linkage for delivery plans."""

    def __init__(self, connection_factory: Callable[..., Any] = psycopg2.connect):
        self._connection_factory = connection_factory

    def upsert(self, plans: Iterable[dict[str, Any]]) -> int:
        plans = list(plans)
        values = [
            (
                item["business_date"], item["plan_key"], item["source_type"],
                item["source_key"], item["api_name"], item["title"],
                item["cadence"], item["scheduled_for"], item["due_at"],
                item.get("expected_for"), item.get("period_key"),
                psycopg2.extras.Json(item.get("metadata") or {}),
            )
            for item in plans
        ]
        if not values:
            return 0
        connection = self._connection_factory(**DB_CONFIG)
        try:
            with connection.cursor() as cursor:
                psycopg2.extras.execute_values(
                    cursor,
                    """
                    INSERT INTO sys_collection_delivery_plan
                        (business_date, plan_key, source_type, source_key,
                         api_name, title, cadence, scheduled_for, due_at,
                         expected_for, period_key, metadata)
                    VALUES %s
                    ON CONFLICT (business_date, plan_key) DO UPDATE
                    SET source_type=EXCLUDED.source_type,
                        source_key=EXCLUDED.source_key,
                        api_name=EXCLUDED.api_name,
                        title=EXCLUDED.title,
                        cadence=EXCLUDED.cadence,
                        scheduled_for=EXCLUDED.scheduled_for,
                        due_at=EXCLUDED.due_at,
                        expected_for=EXCLUDED.expected_for,
                        period_key=EXCLUDED.period_key,
                        metadata=EXCLUDED.metadata,
                        updated_at=NOW()
                    """,
                    values,
                    page_size=len(values),
                )
                plans_by_day: dict[date, list[str]] = {}
                for item in plans:
                    plans_by_day.setdefault(item["business_date"], []).append(
                        item["plan_key"]
                    )
                for business_date, plan_keys in plans_by_day.items():
                    cursor.execute(
                        """
                        DELETE FROM sys_collection_delivery_plan
                        WHERE business_date=%s
                          AND NOT (plan_key = ANY(%s))
                        """,
                        (business_date, plan_keys),
                    )
            connection.commit()
            return len(values)
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    @staticmethod
    def _daily_rules():
        return tuple(
            rule for rule in COVERAGE_RULES.scheduled()
            if rule.strategy == CoverageStrategy.TRADING_DAILY
        )

    def list_daily_data_facts(
        self, start_date: date, end_date: date
    ) -> list[dict[str, Any]]:
        """Read physical daily partitions; task rows are never treated as data."""
        statements = []
        parameters: list[Any] = []
        for rule in self._daily_rules():
            column = sql.Identifier(rule.date_column)
            if rule.date_storage == DateStorage.COMPACT:
                date_expression = sql.SQL(
                    "to_date(NULLIF({column}::text, ''), 'YYYYMMDD')"
                ).format(column=column)
                lower, upper = (
                    start_date.strftime("%Y%m%d"), end_date.strftime("%Y%m%d")
                )
            else:
                date_expression = column
                lower, upper = start_date, end_date
            statements.append(
                sql.SQL(
                    """
                    SELECT %s::text AS dataset_name,
                           {date_expression} AS data_date,
                           count(*)::bigint AS row_count
                    FROM {table}
                    WHERE {column} BETWEEN %s AND %s
                    GROUP BY {column}
                    """
                ).format(
                    date_expression=date_expression,
                    table=sql.Identifier(rule.table),
                    column=column,
                )
            )
            parameters.extend((rule.dataset_name, lower, upper))
        if not statements:
            return []
        connection = self._connection_factory(**DB_CONFIG)
        try:
            with connection.cursor(
                cursor_factory=psycopg2.extras.RealDictCursor
            ) as cursor:
                cursor.execute(sql.SQL(" UNION ALL ").join(statements), parameters)
                return [dict(row) for row in cursor.fetchall()]
        finally:
            connection.close()

    def list_daily_coverage_evidence(
        self, start_date: date, end_date: date
    ) -> list[dict[str, Any]]:
        names = [rule.dataset_name for rule in self._daily_rules()]
        if not names:
            return []
        connection = self._connection_factory(**DB_CONFIG)
        try:
            with connection.cursor(
                cursor_factory=psycopg2.extras.RealDictCursor
            ) as cursor:
                cursor.execute(
                    """
                    SELECT partition.dataset_name, partition.partition_date,
                           partition.status, partition.row_count,
                           partition.entity_count,
                           partition.expected_entity_count,
                           partition.entity_coverage_ratio,
                           partition.expected, partition.checked_at,
                           NULLIF(audit.evidence->>'rule_revision', '')::integer
                               AS rule_revision
                    FROM sys_data_coverage_partition AS partition
                    JOIN sys_data_coverage_audit AS audit
                      ON audit.audit_id=partition.audit_id
                    WHERE partition.dataset_name=ANY(%s)
                      AND partition.partition_date BETWEEN %s AND %s
                    ORDER BY partition.partition_date, partition.dataset_name
                    """,
                    (names, start_date, end_date),
                )
                return [dict(row) for row in cursor.fetchall()]
        finally:
            connection.close()

    def list_market_dates(self, start_date: date, end_date: date) -> set[date]:
        connection = self._connection_factory(**DB_CONFIG)
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT cal_date FROM trade_cal
                    WHERE exchange='SSE' AND is_open=1
                      AND cal_date BETWEEN %s AND %s
                    """,
                    (start_date, end_date),
                )
                return {row[0] for row in cursor.fetchall()}
        finally:
            connection.close()

    def daily_data_bounds(self) -> tuple[date | None, date | None]:
        """Use the canonical stock daily table as the historical anchor."""
        rule = COVERAGE_RULES.get("stock_daily")
        column = sql.Identifier(rule.date_column)
        value = (
            sql.SQL("to_date(NULLIF({}::text, ''), 'YYYYMMDD')").format(column)
            if rule.date_storage == DateStorage.COMPACT
            else column
        )
        connection = self._connection_factory(**DB_CONFIG)
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    sql.SQL("SELECT min({value}), max({value}) FROM {table}").format(
                        value=value, table=sql.Identifier(rule.table)
                    )
                )
                return cursor.fetchone()
        finally:
            connection.close()

    def list_calendar_with_execution(
        self,
        start_date: date,
        end_date: date,
        *,
        date_basis: str = "business_date",
    ) -> list[dict[str, Any]]:
        """Resolve plans in bulk using either their run date or data date."""
        if date_basis not in {"business_date", "expected_for"}:
            raise ValueError("date_basis must be business_date or expected_for")
        connection = self._connection_factory(**DB_CONFIG)
        try:
            with connection.cursor(
                cursor_factory=psycopg2.extras.RealDictCursor
            ) as cursor:
                cursor.execute(
                    f"""
                    SELECT * FROM sys_collection_delivery_plan
                    WHERE {date_basis} BETWEEN %s AND %s
                    ORDER BY {date_basis}, scheduled_for,
                             source_type, api_name
                    """,
                    (start_date, end_date),
                )
                plans = [dict(row) for row in cursor.fetchall()]
                if not plans:
                    return []
                empty_execution = {
                    "job_id": None,
                    "job_status": None,
                    "job_completion_status": None,
                    "job_rows_fetched": None,
                    "job_rows_inserted": None,
                    "job_attempt": None,
                    "job_max_attempts": None,
                    "job_available_at": None,
                    "job_started_at": None,
                    "job_finished_at": None,
                    "job_error_message": None,
                    "job_evidence": None,
                    "campaign_id": None,
                    "campaign_status": None,
                    "campaign_completion_status": None,
                    "campaign_rows_fetched": None,
                    "campaign_rows_inserted": None,
                    "campaign_updated_at": None,
                    "campaign_finished_at": None,
                    "campaign_error_message": None,
                    "completed_offset": None,
                    "universe_total": None,
                    "pages_completed": None,
                    "pages_created": None,
                }
                for plan in plans:
                    plan.update(empty_execution)
                cursor.execute(
                    """
                    CREATE TEMP TABLE delivery_calendar_target (
                        delivery_plan_id BIGINT PRIMARY KEY,
                        business_date DATE NOT NULL,
                        source_type TEXT NOT NULL,
                        source_key TEXT NOT NULL,
                        api_name TEXT NOT NULL,
                        cadence TEXT NOT NULL,
                        expected_for DATE,
                        period_key TEXT
                    ) ON COMMIT DROP
                    """
                )
                psycopg2.extras.execute_values(
                    cursor,
                    """
                    INSERT INTO delivery_calendar_target
                        (delivery_plan_id, business_date, source_type,
                         source_key, api_name, cadence, expected_for,
                         period_key)
                    VALUES %s
                    """,
                    [
                        (
                            plan["delivery_plan_id"], plan["business_date"],
                            plan["source_type"], plan["source_key"],
                            plan["api_name"], plan["cadence"],
                            plan.get("expected_for"), plan.get("period_key"),
                        )
                        for plan in plans
                    ],
                    page_size=1000,
                )
                by_id = {plan["delivery_plan_id"]: plan for plan in plans}
                job_projection = """
                    target.delivery_plan_id,
                    candidate.job_id,
                    candidate.status AS job_status,
                    candidate.completion_status AS job_completion_status,
                    candidate.rows_fetched AS job_rows_fetched,
                    candidate.rows_inserted AS job_rows_inserted,
                    candidate.attempt AS job_attempt,
                    candidate.max_attempts AS job_max_attempts,
                    candidate.available_at AS job_available_at,
                    candidate.started_at AS job_started_at,
                    candidate.finished_at AS job_finished_at,
                    candidate.error_message AS job_error_message,
                    candidate.completion_evidence AS job_evidence
                """
                cursor.execute(
                    f"""
                    SELECT DISTINCT ON (target.delivery_plan_id)
                           {job_projection}
                    FROM delivery_calendar_target AS target
                    JOIN sys_collection_job AS candidate
                      ON target.source_type='policy'
                     AND candidate.job_kind IN ('leaf', 'batch')
                     AND COALESCE(candidate.api_name,
                                  candidate.parameters->>'api_name')=target.api_name
                     AND candidate.cadence=target.cadence
                     AND (
                       (target.expected_for IS NOT NULL
                        AND candidate.expected_for=target.expected_for)
                       OR (target.period_key IS NOT NULL
                           AND candidate.period_key=target.period_key)
                     )
                    ORDER BY target.delivery_plan_id,
                      CASE
                        WHEN candidate.completion_status IN ('complete', 'empty')
                         AND (
                           COALESCE((candidate.completion_evidence->>'verified')::boolean, FALSE)
                           OR COALESCE((candidate.completion_evidence->'verification'->>'verified')::boolean, FALSE)
                         ) THEN 0
                        WHEN candidate.completion_status IN ('complete', 'empty') THEN 1
                        ELSE 2
                      END,
                      candidate.created_at DESC, candidate.job_id DESC
                    """
                )
                self._merge_calendar_rows(by_id, cursor.fetchall())
                cursor.execute(
                    f"""
                    SELECT DISTINCT ON (target.delivery_plan_id)
                           {job_projection}
                    FROM delivery_calendar_target AS target
                    JOIN sys_collection_job AS candidate
                      ON target.source_type='dedicated'
                     AND candidate.job_kind IN ('leaf', 'batch')
                     AND candidate.parameters->>'schedule_id'=target.source_key
                     AND ((candidate.parameters->>'scheduled_for')::timestamptz
                          AT TIME ZONE 'Asia/Shanghai')::date=target.business_date
                    ORDER BY target.delivery_plan_id,
                      CASE
                        WHEN candidate.completion_status IN ('complete', 'empty')
                         AND (
                           COALESCE((candidate.completion_evidence->>'verified')::boolean, FALSE)
                           OR COALESCE((candidate.completion_evidence->'verification'->>'verified')::boolean, FALSE)
                         ) THEN 0
                        WHEN candidate.completion_status IN ('complete', 'empty') THEN 1
                        ELSE 2
                      END,
                      candidate.created_at DESC, candidate.job_id DESC
                    """
                )
                self._merge_calendar_rows(by_id, cursor.fetchall())
                cursor.execute(
                    """
                    SELECT DISTINCT ON (target.delivery_plan_id)
                           target.delivery_plan_id,
                           candidate.campaign_id,
                           candidate.status AS campaign_status,
                           candidate.completion_status AS campaign_completion_status,
                           candidate.rows_fetched AS campaign_rows_fetched,
                           candidate.rows_inserted AS campaign_rows_inserted,
                           candidate.updated_at AS campaign_updated_at,
                           candidate.finished_at AS campaign_finished_at,
                           candidate.error_message AS campaign_error_message,
                           candidate.completed_offset,
                           candidate.universe_total,
                           candidate.pages_completed,
                           candidate.pages_created
                    FROM delivery_calendar_target AS target
                    JOIN sys_collection_fanout_campaign AS candidate
                      ON target.source_type='fanout'
                     AND candidate.api_name=target.api_name
                     AND candidate.cadence=target.cadence
                     AND (
                       (target.expected_for IS NOT NULL
                        AND candidate.expected_for=target.expected_for)
                       OR (target.period_key IS NOT NULL
                           AND candidate.period_key=target.period_key)
                     )
                    ORDER BY target.delivery_plan_id,
                      CASE candidate.completion_status
                        WHEN 'complete' THEN 0 WHEN 'empty' THEN 1 ELSE 2
                      END,
                      candidate.created_at DESC, candidate.campaign_id DESC
                    """
                )
                self._merge_calendar_rows(by_id, cursor.fetchall())
                return plans
        finally:
            connection.close()

    @staticmethod
    def _merge_calendar_rows(
        plans: dict[int, dict[str, Any]], rows: Iterable[dict[str, Any]]
    ) -> None:
        for raw in rows:
            row = dict(raw)
            plan_id = row.pop("delivery_plan_id")
            plans[plan_id].update(row)

    def list_with_execution(self, business_date: date) -> list[dict[str, Any]]:
        return self.list_calendar_with_execution(business_date, business_date)

    def list_range_with_execution(
        self, start_date: date, end_date: date
    ) -> list[dict[str, Any]]:
        connection = self._connection_factory(**DB_CONFIG)
        try:
            with connection.cursor(
                cursor_factory=psycopg2.extras.RealDictCursor
            ) as cursor:
                cursor.execute(
                    """
                    SELECT plan.*,
                           job.job_id, job.status AS job_status,
                           job.completion_status AS job_completion_status,
                           job.rows_fetched AS job_rows_fetched,
                           job.rows_inserted AS job_rows_inserted,
                           job.attempt AS job_attempt,
                           job.max_attempts AS job_max_attempts,
                           job.available_at AS job_available_at,
                           job.started_at AS job_started_at,
                           job.finished_at AS job_finished_at,
                           job.error_message AS job_error_message,
                           job.completion_evidence AS job_evidence,
                           campaign.campaign_id,
                           campaign.status AS campaign_status,
                           campaign.completion_status AS campaign_completion_status,
                           campaign.rows_fetched AS campaign_rows_fetched,
                           campaign.rows_inserted AS campaign_rows_inserted,
                           campaign.updated_at AS campaign_updated_at,
                           campaign.finished_at AS campaign_finished_at,
                           campaign.error_message AS campaign_error_message,
                           campaign.completed_offset,
                           campaign.universe_total,
                           campaign.pages_completed,
                           campaign.pages_created
                    FROM sys_collection_delivery_plan AS plan
                    LEFT JOIN LATERAL (
                        SELECT candidate.*
                        FROM sys_collection_job AS candidate
                        WHERE plan.source_type <> 'fanout'
                          AND candidate.job_kind IN ('leaf', 'batch')
                          AND (
                            (
                              plan.source_type='dedicated'
                              AND candidate.parameters->>'schedule_id'=plan.source_key
                              AND ((candidate.parameters->>'scheduled_for')::timestamptz
                                   AT TIME ZONE 'Asia/Shanghai')::date=plan.business_date
                            ) OR (
                              plan.source_type='policy'
                              AND COALESCE(candidate.api_name,
                                           candidate.parameters->>'api_name')=plan.api_name
                              AND candidate.cadence=plan.cadence
                              AND (
                                (plan.expected_for IS NOT NULL
                                 AND candidate.expected_for=plan.expected_for)
                                OR (plan.period_key IS NOT NULL
                                    AND candidate.period_key=plan.period_key)
                              )
                            )
                          )
                        ORDER BY
                          CASE
                            WHEN candidate.completion_status IN ('complete', 'empty')
                             AND (
                               COALESCE((candidate.completion_evidence->>'verified')::boolean, FALSE)
                               OR COALESCE((candidate.completion_evidence->'verification'->>'verified')::boolean, FALSE)
                             ) THEN 0
                            WHEN candidate.completion_status IN ('complete', 'empty') THEN 1
                            ELSE 2
                          END,
                          candidate.created_at DESC, candidate.job_id DESC
                        LIMIT 1
                    ) AS job ON TRUE
                    LEFT JOIN LATERAL (
                        SELECT candidate.*
                        FROM sys_collection_fanout_campaign AS candidate
                        WHERE plan.source_type='fanout'
                          AND candidate.api_name=plan.api_name
                          AND candidate.cadence=plan.cadence
                          AND (
                            (plan.expected_for IS NOT NULL
                             AND candidate.expected_for=plan.expected_for)
                            OR (plan.period_key IS NOT NULL
                                AND candidate.period_key=plan.period_key)
                          )
                        ORDER BY
                          CASE candidate.completion_status
                            WHEN 'complete' THEN 0 WHEN 'empty' THEN 1 ELSE 2
                          END,
                          candidate.created_at DESC, candidate.campaign_id DESC
                        LIMIT 1
                    ) AS campaign ON TRUE
                    WHERE plan.business_date BETWEEN %s AND %s
                    ORDER BY plan.business_date, plan.scheduled_for,
                             plan.source_type, plan.api_name
                    """,
                    (start_date, end_date),
                )
                return [dict(row) for row in cursor.fetchall()]
        finally:
            connection.close()


class DeliveryPlanBuilder:
    """Derive bounded expectations from the same scheduler and policy registries."""

    def __init__(
        self,
        *,
        market_open: Callable[[date], bool] | None = None,
        scheduler_factory: Callable[[], Any] | None = None,
    ):
        self._market_open = market_open or self._is_market_open
        self._scheduler_factory = scheduler_factory
        self._cached_scheduler: Any | None = None
        self._scope_cache: dict[tuple[str, date], tuple[date, str | None]] = {}

    @staticmethod
    def _is_market_open(day: date) -> bool:
        from service.db import query

        rows = query(
            """
            SELECT EXISTS(
                SELECT 1 FROM trade_cal
                WHERE exchange='SSE' AND cal_date=%s AND is_open=1
            ) AS is_open
            """,
            (day,),
        )
        return bool(rows and rows[0]["is_open"])

    def _scheduler(self):
        if self._cached_scheduler is None:
            if self._scheduler_factory is not None:
                self._cached_scheduler = self._scheduler_factory()
            else:
                from collectors.scheduler import create_scheduler

                self._cached_scheduler = create_scheduler(
                    durabilize=False, set_active=False
                )
        return self._cached_scheduler

    @staticmethod
    def _cadence_due(cadence: str, day: date, market_open: bool) -> bool:
        if cadence == "daily":
            return market_open
        if cadence == "weekly":
            return day.weekday() == 0
        if cadence == "monthly":
            return day.day == 1
        if cadence == "quarterly":
            return day.day == 1 and day.month in {1, 4, 7, 10}
        return False

    def build(self, business_date: date) -> list[dict[str, Any]]:
        market_open = self._market_open(business_date)
        plans = self._dedicated(business_date)
        plans.extend(self._policy(business_date, market_open))
        plans.extend(self._fanout(business_date, market_open))
        return plans

    def _dedicated(self, day: date) -> list[dict[str, Any]]:
        from service.tushare_scheduling import DEDICATED_API_BY_RUN_ID

        scheduler = self._scheduler()
        policies = TusharePolicyRegistry()
        start = _local_datetime(day, time.min)
        end = _local_datetime(day, time.max)
        plans: list[dict[str, Any]] = []
        for job in scheduler.get_jobs():
            if job.id in CONTROL_SCHEDULES:
                continue
            occurrences: list[datetime] = []
            previous = start - timedelta(microseconds=1)
            fire = job.trigger.get_next_fire_time(None, previous)
            while fire is not None and fire <= end:
                occurrences.append(fire.astimezone(SHANGHAI_TIMEZONE))
                previous = fire
                fire = job.trigger.get_next_fire_time(
                    fire, fire + timedelta(microseconds=1)
                )
            if not occurrences:
                continue
            api_name = DEDICATED_API_BY_RUN_ID.get(job.id)
            if not api_name:
                continue
            cadence = policies.get(api_name).cadence
            if job.id.endswith("_daily") or job.id.endswith("_finalize"):
                cadence = "daily"
            elif job.id.endswith("_weekly") or job.id.endswith("_weekly_fri"):
                cadence = "weekly"
            elif job.id.endswith("_monthly_eom"):
                cadence = "monthly"
            elif job.id.endswith("_quarterly"):
                cadence = "quarterly"
            expected_for = day
            if job.id == "index_daily_finalize":
                from service.tushare_scheduling import _latest_trade_date

                expected_for = date.fromisoformat(
                    _latest_trade_date(day - timedelta(days=1))
                )
            elif cadence == "quarterly":
                period = _period_key(cadence, day)
                expected_for = date(
                    int(period[:4]), int(period[4:6]), int(period[6:8])
                )
            elif job.id.endswith("_monthly_eom"):
                from calendar import monthrange
                from service.tushare_scheduling import _latest_trade_date

                month_end = day.replace(day=monthrange(day.year, day.month)[1])
                latest_trade = date.fromisoformat(_latest_trade_date(month_end))
                if day != latest_trade:
                    continue
                expected_for = latest_trade
            elif cadence in {"weekly", "monthly"}:
                expected_for, _ = _resolved_scope(cadence, day)
            period_key = (
                expected_for.strftime("%Y%m%d")
                if cadence == "quarterly"
                else _period_key(cadence, expected_for)
            )
            plans.append(
                {
                    "business_date": day,
                    "plan_key": f"dedicated:{job.id}",
                    "source_type": "dedicated",
                    "source_key": job.id,
                    "api_name": api_name,
                    "title": job.name,
                    "cadence": cadence,
                    "scheduled_for": occurrences[0],
                    "due_at": occurrences[-1] + timedelta(hours=1),
                    "expected_for": expected_for,
                    "period_key": period_key,
                    "metadata": {
                        "schedule_id": job.id,
                        "fire_times": [item.isoformat() for item in occurrences],
                    },
                }
            )
        return plans

    def _policy(self, day: date, market_open: bool) -> list[dict[str, Any]]:
        catalog = TushareInterfaceCatalog()
        policies = TusharePolicyRegistry()
        fanout_names = {item.api_name for item in SCHEDULED_FANOUT_RECIPES}
        plans: list[dict[str, Any]] = []
        for contract in catalog.list():
            if (
                not contract.collectable
                or contract.api_name in DEDICATED_SCHEDULED_APIS
                or contract.api_name in fanout_names
            ):
                continue
            policy = policies.get(contract.api_name)
            if not policy.automatic_safe or not self._cadence_due(
                policy.cadence, day, market_open
            ):
                continue
            scope_day = day - timedelta(days=7) if policy.cadence == "weekly" else day
            scope_key = (policy.cadence, scope_day)
            if scope_key not in self._scope_cache:
                self._scope_cache[scope_key] = _resolved_scope(
                    policy.cadence, scope_day
                )
            expected_for, _ = self._scope_cache[scope_key]
            scheduled_for = _local_datetime(
                day, time(19, 15) if policy.cadence == "daily" else time(7, 15)
            )
            plans.append(
                {
                    "business_date": day,
                    "plan_key": f"policy:{policy.api_name}:{policy.cadence}",
                    "source_type": "policy",
                    "source_key": policy.api_name,
                    "api_name": policy.api_name,
                    "title": contract.title,
                    "cadence": policy.cadence,
                    "scheduled_for": scheduled_for,
                    "due_at": _local_datetime(day, time(23, 59)),
                    "expected_for": expected_for,
                    "period_key": _period_key(policy.cadence, expected_for),
                    "metadata": {"parameter_strategy": policy.parameter_strategy},
                }
            )
        return plans

    def _fanout(self, day: date, market_open: bool) -> list[dict[str, Any]]:
        catalog = TushareInterfaceCatalog()
        plans: list[dict[str, Any]] = []
        for recipe in SCHEDULED_FANOUT_RECIPES:
            if not self._cadence_due(recipe.cadence, day, market_open):
                continue
            _, period_key, expected_for = _recipe_scope(
                recipe, day, include_current_daily=recipe.cadence == "daily"
            )
            scheduled_for = _local_datetime(
                day, time(19, 15) if recipe.cadence == "daily" else time(7, 15)
            )
            plans.append(
                {
                    "business_date": day,
                    "plan_key": f"fanout:{recipe.api_name}:{recipe.cadence}",
                    "source_type": "fanout",
                    "source_key": recipe.api_name,
                    "api_name": recipe.api_name,
                    "title": catalog.get(recipe.api_name).title,
                    "cadence": recipe.cadence,
                    "scheduled_for": scheduled_for,
                    "due_at": scheduled_for + timedelta(hours=24),
                    "expected_for": expected_for,
                    "period_key": period_key,
                    "metadata": {"plan_version": recipe.plan_version},
                }
            )
        return plans


class DeliveryMonitorService:
    def __init__(
        self,
        repository: DeliveryPlanRepository | None = None,
        builder: DeliveryPlanBuilder | None = None,
        now_factory: Callable[[], datetime] = business_now,
    ):
        self._repository = repository or DeliveryPlanRepository()
        self._builder = builder or DeliveryPlanBuilder()
        self._now = now_factory

    def materialize(self, business_date: date) -> int:
        return self._repository.upsert(self._builder.build(business_date))

    def today(self, business_date: date | None = None) -> dict[str, Any]:
        now = self._now().astimezone(SHANGHAI_TIMEZONE)
        day = business_date or now.date()
        self.materialize(day)
        return self._progress(
            day, self._repository.list_with_execution(day), now
        )

    def calendar(self, start_date: date, end_date: date) -> dict[str, Any]:
        """Return task-run-day delivery states for backwards compatibility."""
        self._validate_calendar_range(start_date, end_date)

        now = self._now().astimezone(SHANGHAI_TIMEZONE)
        days: list[date] = []
        cursor = start_date
        while cursor <= end_date:
            days.append(cursor)
            cursor += timedelta(days=1)
        # Reading history must never invent a past expectation. Doing so would
        # turn days from before delivery-plan retention into false overdue
        # incidents. Only today is materialized as part of a read; older days
        # are reported as untracked when no contemporaneous snapshot exists.
        if start_date <= now.date() <= end_date:
            self.materialize(now.date())
        rows_by_day: dict[date, list[dict[str, Any]]] = {
            day: [] for day in days
        }
        list_range = getattr(
            self._repository,
            "list_calendar_with_execution",
            self._repository.list_range_with_execution,
        )
        for row in list_range(
            start_date, end_date
        ):
            rows_by_day[row["business_date"]].append(row)

        calendar_days: list[dict[str, Any]] = []
        for day in days:
            progress = self._progress(day, rows_by_day[day], now)
            summary = progress["summary"]
            if day > now.date():
                status = "future"
            elif summary["attention"]:
                status = "issue"
            elif not summary["total"]:
                status = "untracked"
            elif summary["completed_total"] == summary["total"]:
                status = "complete"
            else:
                status = "in_progress"
            calendar_days.append(
                {
                    "business_date": day.isoformat(),
                    "status": status,
                    **summary,
                }
            )
        counts = Counter(item["status"] for item in calendar_days)
        return {
            "generated_at": now.isoformat(),
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "summary": {
                "days": len(calendar_days),
                "complete_days": counts["complete"],
                "issue_days": counts["issue"],
                "in_progress_days": counts["in_progress"],
                "untracked_days": counts["untracked"],
                "future_days": counts["future"],
            },
            "days": calendar_days,
        }

    def data_calendar(self, start_date: date, end_date: date) -> dict[str, Any]:
        """Return data-date states from physical rows and current audit evidence.

        Delivery plans remain useful execution evidence, but they never make a
        calendar day green on their own. This distinction is essential for old
        history, where data exists long before delivery-plan retention began.
        """
        self._validate_calendar_range(start_date, end_date)
        now = self._now().astimezone(SHANGHAI_TIMEZONE)
        if start_date <= now.date() <= end_date:
            self.materialize(now.date())

        rows = self._repository.list_calendar_with_execution(
            start_date, end_date, date_basis="expected_for"
        )
        rows_by_day: dict[date, list[dict[str, Any]]] = {}
        for row in rows:
            data_date = row.get("expected_for")
            if data_date is None or self._effective_cadence(row) != "daily":
                continue
            rows_by_day.setdefault(data_date, []).append(row)

        facts = self._repository_call(
            "list_daily_data_facts", start_date, end_date, default=[]
        )
        evidence = self._current_coverage_evidence(
            self._repository_call(
                "list_daily_coverage_evidence", start_date, end_date, default=[]
            )
        )
        market_dates = self._repository_call(
            "list_market_dates", start_date, end_date, default=set()
        )
        facts_by_day: dict[date, list[dict[str, Any]]] = {}
        for item in facts:
            if item.get("data_date") is not None:
                facts_by_day.setdefault(item["data_date"], []).append(item)
        evidence_by_day: dict[date, list[dict[str, Any]]] = {}
        for item in evidence:
            evidence_by_day.setdefault(item["partition_date"], []).append(item)

        calendar_days: list[dict[str, Any]] = []
        cursor = start_date
        while cursor <= end_date:
            task_progress = self._data_date_progress(
                cursor, rows_by_day.get(cursor, []), now
            )
            progress = self._combine_data_evidence(
                cursor,
                task_progress,
                facts_by_day.get(cursor, []),
                evidence_by_day.get(cursor, []),
                cursor in market_dates,
                now,
            )
            calendar_days.append(
                {"data_date": cursor.isoformat(), **progress}
            )
            cursor += timedelta(days=1)

        counts = Counter(item["status"] for item in calendar_days)
        bounds = self._repository_call(
            "daily_data_bounds", default=(None, None)
        )
        return {
            "generated_at": now.isoformat(),
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "basis": "data_date",
            "requirement_source": "scheduled_daily_coverage_registry",
            "validation_basis": "physical_partitions_plus_current_coverage_audit",
            "monitored_dataset_count": len(self._daily_rules()),
            "observed_min_date": bounds[0].isoformat() if bounds[0] else None,
            "observed_max_date": bounds[1].isoformat() if bounds[1] else None,
            "summary": {
                "days": len(calendar_days),
                "complete_days": counts["complete"],
                "observed_days": counts["observed"],
                "issue_days": counts["issue"],
                "in_progress_days": counts["in_progress"],
                "untracked_days": counts["untracked"],
                "future_days": counts["future"],
            },
            "days": calendar_days,
        }

    def data_calendar_day(self, data_date: date) -> dict[str, Any]:
        """Return physical data validation first, with task evidence attached."""
        now = self._now().astimezone(SHANGHAI_TIMEZONE)
        if data_date == now.date():
            self.materialize(data_date)
        rows = self._repository.list_calendar_with_execution(
            data_date, data_date, date_basis="expected_for"
        )
        task_progress = self._data_date_progress(data_date, rows, now)
        facts = self._repository_call(
            "list_daily_data_facts", data_date, data_date, default=[]
        )
        evidence = self._current_coverage_evidence(
            self._repository_call(
                "list_daily_coverage_evidence", data_date, data_date, default=[]
            )
        )
        market_dates = self._repository_call(
            "list_market_dates", data_date, data_date, default=set()
        )
        data_items = self._data_items(
            data_date, facts, evidence, task_progress["items"],
            data_date in market_dates,
        )
        summary = self._combine_data_evidence(
            data_date, task_progress, facts, evidence,
            data_date in market_dates, now,
        )
        production_data_path = hasattr(self._repository, "list_daily_data_facts")
        compact_task_items = [
            {
                key: item.get(key)
                for key in (
                    "api_name", "title", "delivery_status", "business_dates",
                    "work_id", "final_due_at", "attention",
                    "planned_attempt_total", "error_message", "validation_state",
                )
            }
            for item in task_progress["items"]
        ]
        return {
            "generated_at": now.isoformat(),
            "data_date": data_date.isoformat(),
            "basis": "data_date",
            "requirement_source": "scheduled_daily_coverage_registry",
            "validation_basis": "physical_partitions_plus_current_coverage_audit",
            "monitored_dataset_count": len(self._daily_rules()),
            "summary": summary,
            "data_items": data_items,
            "task_evidence": {
                "summary": task_progress["summary"],
                "items": compact_task_items,
                "issues": [item for item in compact_task_items if item["attention"]],
            },
            # Task-only repositories are retained for compatibility tests and
            # third-party adapters. Production clients should render
            # ``data_items``; duplicating complete task payloads made one day
            # exceed 700 KiB and slowed the console materially.
            "items": (
                compact_task_items if production_data_path else task_progress["items"]
            ),
            "issues": [item for item in data_items if item["attention"]],
        }

    @staticmethod
    def _daily_rules():
        return tuple(
            rule for rule in COVERAGE_RULES.scheduled()
            if rule.strategy == CoverageStrategy.TRADING_DAILY
        )

    def _current_coverage_evidence(
        self, rows: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        revisions = {rule.dataset_name: rule.revision for rule in self._daily_rules()}
        return [
            row for row in rows
            if row.get("rule_revision") == revisions.get(row.get("dataset_name"))
        ]

    def _combine_data_evidence(
        self,
        data_date: date,
        task_progress: dict[str, Any],
        facts: list[dict[str, Any]],
        evidence: list[dict[str, Any]],
        market_open: bool,
        now: datetime,
    ) -> dict[str, Any]:
        # Compatibility repositories have task evidence only. Production uses
        # the physical fact path below, so task success cannot manufacture a
        # green data day.
        if not hasattr(self._repository, "list_daily_data_facts"):
            return task_progress["summary"]

        monitored = len(self._daily_rules())
        facts_by_name = {item["dataset_name"]: item for item in facts}
        evidence_by_name = {item["dataset_name"]: item for item in evidence}
        audited_expected = [item for item in evidence if item.get("expected")]
        audited_present = [
            item for item in audited_expected if item.get("status") == "present"
        ]
        audited_issues = [
            item for item in audited_expected
            if item.get("status") in {"missing", "partial"}
        ]
        task_summary = task_progress["summary"]
        if data_date > now.date():
            status = "future"
        elif audited_issues or task_summary.get("attention"):
            status = "issue"
        elif market_open and len(audited_present) == monitored:
            status = "complete"
        elif data_date == now.date() and (
            facts_by_name or evidence_by_name or task_summary.get("total")
        ):
            status = "in_progress"
        elif facts_by_name or evidence_by_name:
            status = "observed"
        else:
            status = "untracked"
        return {
            "status": status,
            "market_open": market_open,
            "monitored_datasets": monitored,
            "observed_datasets": len(facts_by_name),
            "observed_rows": sum(int(item.get("row_count") or 0) for item in facts),
            "audited_expected": len(audited_expected),
            "audited_present": len(audited_present),
            "audited_issues": len(audited_issues),
            "audit_coverage_ratio": (
                len(audited_present) / monitored if market_open and monitored else None
            ),
            "task_status": task_summary.get("status"),
            "task_total": task_summary.get("total", 0),
            "task_completed": task_summary.get("completed_total", 0),
            "task_attention": task_summary.get("attention", 0),
            # Compatibility aliases used by existing dashboard clients.
            "total": monitored if market_open else len(facts_by_name),
            "completed_total": len(audited_present),
            "attention": len(audited_issues) + int(task_summary.get("attention") or 0),
            "overdue": task_summary.get("overdue", 0),
            "running": task_summary.get("running", 0),
            "queued": task_summary.get("queued", 0),
            "waiting": task_summary.get("waiting", 0),
            "unverified": max(monitored - len(evidence_by_name), 0) if market_open else 0,
            "empty": task_summary.get("empty", 0),
        }

    def _data_items(
        self,
        data_date: date,
        facts: list[dict[str, Any]],
        evidence: list[dict[str, Any]],
        task_items: list[dict[str, Any]],
        market_open: bool,
    ) -> list[dict[str, Any]]:
        facts_by_name = {item["dataset_name"]: item for item in facts}
        evidence_by_name = {item["dataset_name"]: item for item in evidence}
        task_by_api = {item["api_name"]: item for item in task_items}
        items: list[dict[str, Any]] = []
        for rule in self._daily_rules():
            fact = facts_by_name.get(rule.dataset_name)
            audit = evidence_by_name.get(rule.dataset_name)
            api_name = rule.collection_api_name or rule.dataset_name
            task = task_by_api.get(api_name)
            if not market_open and fact is None and audit is None and task is None:
                continue
            if audit is not None:
                validation_status = audit["status"]
            elif fact is not None:
                validation_status = "observed"
            else:
                validation_status = "unverified"
            availability_state = None
            if validation_status == "unverified" and rule.release_after:
                availability_state = "waiting_publication"
            elif validation_status == "unverified" and api_name == "ths_hot":
                availability_state = "waiting_recheck"
            attention = validation_status in {"missing", "partial"} or bool(
                task and task.get("attention")
            )
            if validation_status == "missing":
                action = "按该数据日期创建精确补采，并在写入后重新执行覆盖审计"
            elif validation_status == "partial":
                action = "检查截面/分页证据，修复后重采该数据日期"
            elif validation_status == "observed":
                action = "数据已存在；需要同规则版本覆盖审计后才能标记严格完成"
            elif validation_status == "unverified" and rule.release_after:
                release = rule.release_after.strftime("%H:%M")
                action = (
                    f"上游在下一自然日 {release} 后发布；到期后系统自动复采并审计，"
                    "当前不判为缺失"
                )
            elif validation_status == "unverified" and api_name == "ths_hot":
                action = (
                    "热榜数据分批发布至 22:00；系统在 23:15 及后续巡航自动复查，"
                    "成熟后仍为空才升级为异常"
                )
            elif validation_status == "unverified":
                action = "尚无当前规则版本的物理分区审计，不能判定缺失或完成"
            else:
                action = "当前规则版本覆盖审计已通过"
            items.append(
                {
                    "dataset_name": rule.dataset_name,
                    "api_name": api_name,
                    "data_date": data_date.isoformat(),
                    "description": rule.description,
                    "validation_status": validation_status,
                    "availability_state": availability_state,
                    "row_count": int((fact or audit or {}).get("row_count") or 0),
                    "entity_count": (audit or {}).get("entity_count"),
                    "expected_entity_count": (audit or {}).get(
                        "expected_entity_count"
                    ),
                    "entity_coverage_ratio": (audit or {}).get(
                        "entity_coverage_ratio"
                    ),
                    "audit_checked_at": _json_time((audit or {}).get("checked_at")),
                    "task": (
                        {
                            key: task.get(key)
                            for key in (
                                "api_name", "delivery_status", "business_dates",
                                "work_id", "final_due_at", "attention",
                                "planned_attempt_total", "error_message",
                                "validation_state",
                            )
                        }
                        if task else None
                    ),
                    "attention": attention,
                    "action": action,
                }
            )
        return sorted(
            items,
            key=lambda item: (
                not item["attention"],
                item["validation_status"] == "present",
                item["dataset_name"],
            ),
        )

    def _repository_call(self, name: str, *args, default):
        # Tests and third-party repositories written before the data-fact
        # calendar can still exercise task-only compatibility behavior.
        method = getattr(self._repository, name, None)
        return method(*args) if method is not None else default

    @staticmethod
    def _validate_calendar_range(start_date: date, end_date: date) -> None:
        if start_date > end_date:
            raise ValueError("start_date must not be after end_date")
        if (end_date - start_date).days > 62:
            raise ValueError("delivery calendar range cannot exceed 63 days")

    def _data_date_progress(
        self,
        data_date: date,
        rows: list[dict[str, Any]],
        now: datetime,
    ) -> dict[str, Any]:
        primary_snapshot_present = any(
            row.get("business_date") == data_date
            and self._effective_cadence(row) == "daily"
            for row in rows
        )
        groups: dict[tuple[str, date], list[dict[str, Any]]] = {}
        for row in rows:
            expected_for = row.get("expected_for")
            if expected_for != data_date or self._effective_cadence(row) != "daily":
                continue
            row = {**row, "cadence": "daily"}
            groups.setdefault((row["api_name"], expected_for), []).append(
                self._decorate(row, now)
            )

        items = [
            self._collapse_data_requirement(group, now)
            for group in groups.values()
        ]
        items.sort(key=lambda item: (item["attention"] is False, item["api_name"]))
        counts = Counter(item["delivery_status"] for item in items)
        completed = sum(
            item["delivery_status"] in {"complete", "empty"} for item in items
        )
        attention = sum(item["attention"] for item in items)
        if data_date > now.date():
            status = "future"
        elif not primary_snapshot_present:
            # A later T+1 task can leave isolated evidence for a date that
            # predates plan retention. It does not establish the denominator
            # of fixed daily requirements and therefore must never turn green.
            status = "untracked"
        elif attention:
            status = "issue"
        elif not items:
            status = "untracked"
        elif completed == len(items):
            status = "complete"
        else:
            status = "in_progress"
        summary = {
            "status": status,
            "requirement_snapshot_complete": primary_snapshot_present,
            "total": len(items),
            "completed_total": completed,
            "attention": attention,
            "overdue": sum(
                item["delivery_status"] in {"overdue", "failed", "incomplete"}
                for item in items
            ),
            "running": counts["running"] + counts["retrying"],
            "queued": counts["queued"],
            "waiting": counts["waiting"] + counts["not_due"],
            "unverified": counts["unverified"] + counts["verifying"],
            "empty": counts["empty"],
        }
        return {
            "summary": summary,
            "items": items,
            "issues": [item for item in items if item["attention"]],
        }

    @staticmethod
    def _effective_cadence(row: dict[str, Any]) -> str | None:
        """Recover the true cadence from dedicated schedule IDs.

        Old delivery-plan snapshots could inherit a catalog cadence that did
        not describe the dedicated cron task. The immutable source key is the
        authoritative schedule identity and keeps historical calendars honest.
        """
        cadence = row.get("cadence")
        if row.get("source_type") != "dedicated":
            return cadence
        schedule_id = str(row.get("source_key") or "")
        if schedule_id.endswith("_daily") or schedule_id.endswith("_finalize"):
            return "daily"
        if schedule_id.endswith("_weekly") or schedule_id.endswith("_weekly_fri"):
            return "weekly"
        if schedule_id.endswith("_monthly_eom"):
            return "monthly"
        if schedule_id.endswith("_quarterly"):
            return "quarterly"
        return cadence

    def _collapse_data_requirement(
        self, attempts: list[dict[str, Any]], now: datetime
    ) -> dict[str, Any]:
        attempts.sort(key=lambda item: item["scheduled_for"])
        terminal = [
            item for item in attempts
            if item["delivery_status"] in {"complete", "empty"}
        ]
        final_due = max(item["due_at"] for item in attempts)
        if terminal:
            completed = [
                item for item in terminal if item["delivery_status"] == "complete"
            ]
            selected = (completed or terminal)[-1]
            status = selected["delivery_status"]
            validation_state = f"verified_{status}"
        elif now <= final_due:
            priority = {
                "running": 0, "retrying": 1, "queued": 2,
                "verifying": 3, "unverified": 4, "waiting": 5,
                "not_due": 6, "failed": 7, "incomplete": 8, "overdue": 9,
            }
            selected = min(
                attempts, key=lambda item: priority.get(item["delivery_status"], 10)
            )
            if selected["delivery_status"] in {"failed", "incomplete", "overdue"}:
                status = "waiting"
            else:
                status = selected["delivery_status"]
            validation_state = "pending_final_attempt"
        else:
            selected = max(
                attempts,
                key=lambda item: (
                    item.get("finished_at") or item["scheduled_for"],
                    item.get("work_id") or 0,
                ),
            )
            statuses = {item["delivery_status"] for item in attempts}
            if "incomplete" in statuses or statuses & {"unverified", "verifying"}:
                status = "incomplete"
            elif "failed" in statuses:
                status = "failed"
            else:
                status = "overdue"
            validation_state = "missing_verified_completion"

        result = self._serialize(selected)
        result.update(
            {
                "data_date": selected["expected_for"].isoformat(),
                "business_dates": sorted(
                    {item["business_date"].isoformat() for item in attempts}
                ),
                "planned_attempt_total": len(attempts),
                "scheduled_for": attempts[0]["scheduled_for"].isoformat(),
                "final_due_at": final_due.isoformat(),
                "delivery_status": status,
                "attention": status in {"failed", "incomplete", "overdue"},
                "validation_state": validation_state,
                "attempts": [
                    {
                        "business_date": item["business_date"].isoformat(),
                        "scheduled_for": item["scheduled_for"].isoformat(),
                        "due_at": item["due_at"].isoformat(),
                        "source_type": item["source_type"],
                        "work_id": item.get("work_id"),
                        "delivery_status": item["delivery_status"],
                        "completion_evidence": item.get("completion_evidence") or {},
                        "error_message": item.get("error_message"),
                    }
                    for item in attempts
                ],
            }
        )
        return result

    def _progress(
        self,
        day: date,
        rows: list[dict[str, Any]],
        now: datetime,
    ) -> dict[str, Any]:
        items = [self._decorate(row, now) for row in rows]
        counts = Counter(item["delivery_status"] for item in items)
        due_items = [item for item in items if item["scheduled_for"] <= now]
        complete_states = {"complete", "empty"}
        due_complete = sum(item["delivery_status"] in complete_states for item in due_items)
        all_complete = sum(item["delivery_status"] in complete_states for item in items)
        attention = sum(item["attention"] for item in items)
        next_items = [item for item in items if item["scheduled_for"] > now]
        return {
            "generated_at": now.isoformat(),
            "business_date": day.isoformat(),
            "summary": {
                "due_now": len(due_items),
                "completed_due": due_complete,
                "due_progress_ratio": due_complete / len(due_items) if due_items else 1.0,
                "total": len(items),
                "completed_total": all_complete,
                "total_progress_ratio": all_complete / len(items) if items else 1.0,
                "attention": attention,
                "overdue": counts["overdue"],
                "running": counts["running"] + counts["retrying"],
                "queued": counts["queued"],
                "waiting": counts["waiting"],
                "not_due": counts["not_due"],
                "unverified": counts["unverified"] + counts["verifying"],
                "empty": counts["empty"],
                "next_scheduled_for": (
                    next_items[0]["scheduled_for"].isoformat() if next_items else None
                ),
            },
            "items": [self._serialize(item) for item in items],
            "issues": [self._serialize(item) for item in items if item["attention"]],
        }

    @staticmethod
    def _decorate(row: dict[str, Any], now: datetime) -> dict[str, Any]:
        item = dict(row)
        if item["source_type"] == "fanout":
            work_status = item.get("campaign_status")
            completion = item.get("campaign_completion_status")
            finished_at = item.get("campaign_finished_at")
            error = item.get("campaign_error_message")
            rows_fetched = item.get("campaign_rows_fetched")
            rows_inserted = item.get("campaign_rows_inserted")
            work_id = item.get("campaign_id")
            evidence = {
                "verified": completion in {"complete", "empty"},
                "verification_type": "fanout_campaign_aggregate",
                "pages_completed": item.get("pages_completed"),
                "pages_created": item.get("pages_created"),
                "universe_total": item.get("universe_total"),
            }
        else:
            work_status = item.get("job_status")
            completion = item.get("job_completion_status")
            finished_at = item.get("job_finished_at")
            error = item.get("job_error_message")
            rows_fetched = item.get("job_rows_fetched")
            rows_inserted = item.get("job_rows_inserted")
            work_id = item.get("job_id")
            evidence = item.get("job_evidence") or {}
            verified = bool(
                evidence.get("verified")
                or (evidence.get("verification") or {}).get("verified")
            )
            if completion in {"complete", "empty"} and not verified:
                completion = "unverified"

        if completion == "complete":
            status = "complete"
        elif completion == "empty":
            status = "empty"
        elif completion in {"unverified", "verifying"}:
            status = "incomplete" if now > item["due_at"] else completion
        elif completion == "incomplete":
            # Intraday publishers can expose a partial partition before their
            # final release.  Coverage evidence should keep that delivery in
            # the recovery window until its explicit deadline; surfacing it as
            # an incident earlier creates a false failure on every normal day.
            status = "incomplete" if now > item["due_at"] else "waiting"
        elif work_status == "running":
            status = "running"
        elif work_status == "queued":
            status = "retrying" if int(item.get("job_attempt") or 0) else "queued"
        elif work_status in {"failed", "attention", "paused"}:
            status = "failed"
        elif now < item["scheduled_for"]:
            status = "not_due"
        elif now <= item["due_at"]:
            status = "waiting"
        else:
            status = "overdue"

        attention = status in {"failed", "incomplete", "overdue"}
        item.update(
            {
                "delivery_status": status,
                "attention": attention,
                "work_id": work_id,
                "rows_fetched": rows_fetched,
                "rows_inserted": rows_inserted,
                "finished_at": finished_at,
                "error_message": error,
                "completion_evidence": evidence,
                "execution_status": work_status,
                "completion_status": completion,
                "on_time": bool(
                    status in {"complete", "empty"}
                    and finished_at
                    and finished_at <= item["due_at"]
                ),
            }
        )
        return item

    @staticmethod
    def _serialize(item: dict[str, Any]) -> dict[str, Any]:
        public = {
            key: _json_time(value)
            for key, value in item.items()
            if not key.startswith("job_") and not key.startswith("campaign_")
        }
        public.pop("delivery_plan_id", None)
        public.pop("created_at", None)
        public.pop("updated_at", None)
        return public
