"""Truthful business-day delivery planning and progress reporting."""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Iterable
from datetime import date, datetime, time, timedelta
from typing import Any

import psycopg2
import psycopg2.extras

from service.clock import SHANGHAI_TIMEZONE, business_now
from service.config import DB_CONFIG
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
                    SET title=EXCLUDED.title,
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
            connection.commit()
            return len(values)
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def list_with_execution(self, business_date: date) -> list[dict[str, Any]]:
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
                          CASE candidate.completion_status
                            WHEN 'complete' THEN 0 WHEN 'empty' THEN 1 ELSE 2
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
                    WHERE plan.business_date=%s
                    ORDER BY plan.scheduled_for, plan.source_type, plan.api_name
                    """,
                    (business_date,),
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
        if self._scheduler_factory is not None:
            return self._scheduler_factory()
        from collectors.scheduler import create_scheduler

        return create_scheduler(durabilize=False, set_active=False)

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
            expected_for = day
            if job.id == "index_daily_finalize":
                from service.tushare_scheduling import _latest_trade_date

                expected_for = date.fromisoformat(
                    _latest_trade_date(day - timedelta(days=1))
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
                    "period_key": _period_key(cadence, expected_for),
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
            expected_for, _ = _resolved_scope(policy.cadence, scope_day)
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
        items = [self._decorate(row, now) for row in self._repository.list_with_execution(day)]
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
        else:
            work_status = item.get("job_status")
            completion = item.get("job_completion_status")
            finished_at = item.get("job_finished_at")
            error = item.get("job_error_message")
            rows_fetched = item.get("job_rows_fetched")
            rows_inserted = item.get("job_rows_inserted")
            work_id = item.get("job_id")

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
