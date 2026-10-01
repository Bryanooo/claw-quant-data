"""Idempotent routine dispatch for the V2 orchestration control plane."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from service.config import APP_REVISION
from service.db import query
from service.orchestration_v2.catalog import acquisition_task_blueprints
from service.orchestration_v2.contracts import ExecutionRequest
from service.orchestration_v2.contracts import NEXT_MORNING_TASKS
from service.orchestration_v2.repository import OrchestrationV2Repository


def _routine_scope(cadence: str, as_of_date: date) -> tuple[str, date, date, date]:
    """Return identity, observation range and provider parameter anchor.

    Weekly and monthly collection always targets the most recently *closed*
    period.  The separate anchor preserves provider policies such as
    ``previous month`` without shifting the observation range twice.
    """
    if cadence == "weekly":
        this_monday = as_of_date - timedelta(days=as_of_date.weekday())
        start = this_monday - timedelta(days=7)
        end = start + timedelta(days=6)
        iso = start.isocalendar()
        return f"{iso.year}-W{iso.week:02d}", start, end, start
    if cadence == "monthly":
        first = as_of_date.replace(day=1)
        end = first - timedelta(days=1)
        start = end.replace(day=1)
        return end.strftime("%Y-%m"), start, end, as_of_date
    if cadence == "quarterly":
        if as_of_date.month >= 10:
            end = date(as_of_date.year, 9, 30)
        elif as_of_date.month >= 7:
            end = date(as_of_date.year, 6, 30)
        elif as_of_date.month >= 4:
            end = date(as_of_date.year, 3, 31)
        else:
            end = date(as_of_date.year - 1, 12, 31)
        start = date(end.year, ((end.month - 1) // 3) * 3 + 1, 1)
        return end.isoformat(), start, end, as_of_date
    raise ValueError(f"unsupported routine cadence: {cadence}")


def is_trade_day(value: date) -> bool:
    rows = query(
        "SELECT is_open FROM trade_cal "
        "WHERE exchange='SSE' AND cal_date=%s LIMIT 1",
        (value,),
    )
    return bool(rows and int(rows[0]["is_open"]) == 1)


def dispatch_daily_acquisitions(
    target_date: date,
    *,
    delayed_target_date: date | None = None,
    repository: OrchestrationV2Repository | None = None,
) -> dict[str, Any]:
    """Create one V2 execution per due daily acquisition task.

    The idempotency key is the business identity of the run, so startup catch-up,
    the 19:15 patrol and the 23:15 patrol can all call this function safely.
    Pagination, exchange partitions and symbols remain inside the acquire node.
    """

    if not is_trade_day(target_date):
        return {
            "target_date": target_date.isoformat(),
            "trade_day": False,
            "eligible": 0,
            "created": 0,
            "existing": 0,
            "skipped": "not_a_trade_day",
            "errors": {},
        }

    store = repository or OrchestrationV2Repository()
    task_keys = tuple(
        blueprint.task_key
        for blueprint in acquisition_task_blueprints()
        if blueprint.cadence == "daily"
    )
    created = 0
    existing = 0
    errors: dict[str, str] = {}
    delayed_date = delayed_target_date or target_date
    for task_key in task_keys:
        observation_date = (
            delayed_date if task_key in NEXT_MORNING_TASKS else target_date
        )
        observation_key = observation_date.isoformat()
        try:
            _row, was_created = store.create_execution(ExecutionRequest(
                task_key=task_key,
                purpose="daily",
                trigger_source="schedule",
                idempotency_key=f"v2:daily:{task_key}:{observation_key}",
                observation_key=observation_key,
                observation_start=observation_date,
                observation_end=observation_date,
                observation_period=observation_key,
                publication_date=observation_date,
                frozen_scope={
                    "dispatch": "v2_daily_acquisition",
                    "logical_period": observation_key,
                    "pagination_and_partitions": "within_acquire_node",
                },
                app_revision=APP_REVISION,
            ))
            created += int(was_created)
            existing += int(not was_created)
        except Exception as exc:
            errors[task_key] = f"{type(exc).__name__}: {exc}"
    return {
        "target_date": target_date.isoformat(),
        "delayed_target_date": delayed_date.isoformat(),
        "trade_day": True,
        "eligible": len(task_keys),
        "created": created,
        "existing": existing,
        "skipped": None,
        "errors": errors,
    }


def dispatch_due_acquisitions(
    as_of_date: date,
    *,
    include_current_daily: bool,
    repository: OrchestrationV2Repository | None = None,
) -> dict[str, Any]:
    """Idempotently create every due V2 routine acquisition.

    This is the sole routine scheduler after cutover.  Manual interfaces stay
    explicit; daily, weekly, monthly and quarterly definitions are all owned
    here so a V2 cutover cannot silently omit non-daily datasets.
    """
    store = repository or OrchestrationV2Repository()
    daily = dispatch_latest_daily_acquisitions(
        as_of_date,
        include_current_daily=include_current_daily,
        repository=store,
    )
    totals = {
        "eligible": int(daily.get("eligible") or 0),
        "created": int(daily.get("created") or 0),
        "existing": int(daily.get("existing") or 0),
    }
    errors = dict(daily.get("errors") or {})
    cadences: dict[str, dict[str, Any]] = {"daily": daily}
    for cadence in ("weekly", "monthly", "quarterly"):
        key, start, end, anchor = _routine_scope(cadence, as_of_date)
        task_keys = tuple(
            item.task_key
            for item in acquisition_task_blueprints()
            if item.cadence == cadence
        )
        created = existing = 0
        cadence_errors: dict[str, str] = {}
        for task_key in task_keys:
            try:
                _row, was_created = store.create_execution(ExecutionRequest(
                    task_key=task_key,
                    purpose="daily",
                    trigger_source="schedule",
                    idempotency_key=f"v2:routine:{cadence}:{task_key}:{key}",
                    observation_key=key,
                    observation_start=start,
                    observation_end=end,
                    observation_period=key,
                    publication_date=end,
                    frozen_scope={
                        "dispatch": "v2_routine_acquisition",
                        "cadence": cadence,
                        "logical_period": key,
                        "policy_anchor_date": anchor.isoformat(),
                        "pagination_and_partitions": "within_acquire_node",
                    },
                    app_revision=APP_REVISION,
                ))
                created += int(was_created)
                existing += int(not was_created)
            except Exception as exc:
                cadence_errors[task_key] = f"{type(exc).__name__}: {exc}"
        cadences[cadence] = {
            "observation_key": key,
            "observation_start": start.isoformat(),
            "observation_end": end.isoformat(),
            "eligible": len(task_keys),
            "created": created,
            "existing": existing,
            "errors": cadence_errors,
        }
        totals["eligible"] += len(task_keys)
        totals["created"] += created
        totals["existing"] += existing
        errors.update({f"{cadence}:{key}": value for key, value in cadence_errors.items()})
    return {
        "as_of_date": as_of_date.isoformat(),
        **totals,
        "manual_not_scheduled": sum(
            item.cadence == "manual" for item in acquisition_task_blueprints()
        ),
        "cadences": cadences,
        "errors": errors,
    }


def dispatch_latest_daily_acquisitions(
    as_of_date: date,
    *,
    include_current_daily: bool,
    repository: OrchestrationV2Repository | None = None,
) -> dict[str, Any]:
    """Resolve normal and T+1 scopes before dispatching routine work."""

    rows = query(
        "SELECT cal_date FROM trade_cal WHERE exchange='SSE' AND is_open=1 "
        "AND cal_date <= %s ORDER BY cal_date DESC LIMIT 3",
        (as_of_date,),
    )
    dates = [row["cal_date"] for row in rows]
    if not dates:
        return {
            "target_date": None,
            "delayed_target_date": None,
            "trade_day": False,
            "eligible": 0,
            "created": 0,
            "existing": 0,
            "skipped": "trade_calendar_has_no_prior_open_day",
            "errors": {},
        }
    if include_current_daily and dates[0] == as_of_date:
        target = dates[0]
        delayed = dates[1] if len(dates) > 1 else dates[0]
    else:
        target = next((item for item in dates if item < as_of_date), dates[0])
        delayed = target
    return dispatch_daily_acquisitions(
        target,
        delayed_target_date=delayed,
        repository=repository,
    )
