"""Idempotent routine dispatch for the V2 orchestration control plane."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from service.config import APP_REVISION
from service.clock import business_now
from service.db import query
from service.orchestration_v2.catalog import (
    acquisition_task_blueprints,
    transformation_task_blueprints,
)
from service.orchestration_v2.contracts import ExecutionRequest
from service.orchestration_v2.contracts import (
    NEXT_MORNING_TASKS,
    US_COMPLETED_SESSION_TASKS,
)
from service.orchestration_v2.repository import OrchestrationV2Repository
from service.orchestration_v2.recovery_policy import DEFERRED_RESEARCH_DATASETS
from service.orchestration_v2.transformations import (
    SUPPORTED_TRANSFORMATION_TASK_KEYS,
)


# These inputs have financial/event periods, not the daily bar observation key.
TRANSFORMATION_AUXILIARY_INPUTS = {
    "local_factor_snapshot": ("income", "balancesheet", "cashflow", "financial_indicator", "dividend"),
    "valuation_percentile_snapshot": ("index_weight",),
}


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


def dispatch_ready_transformations(
    *,
    repository: OrchestrationV2Repository | None = None,
) -> dict[str, Any]:
    """Create derived executions only for a common, certified input scope."""

    store = repository or OrchestrationV2Repository()
    active = store.active_task_keys()
    created = existing = 0
    eligible = 0
    waiting: dict[str, list[str]] = {}
    errors: dict[str, str] = {}
    for blueprint in transformation_task_blueprints():
        if (
            blueprint.task_key not in active
            or blueprint.task_key not in SUPPORTED_TRANSFORMATION_TASK_KEYS
        ):
            continue
        eligible += 1
        try:
            if blueprint.task_key == 'valuation_percentile_snapshot':
                dispatch_group_weight_refresh(store, as_of=business_now().date())
            auxiliary_names = TRANSFORMATION_AUXILIARY_INPUTS.get(blueprint.task_key, ())
            daily_inputs = tuple(name for name in blueprint.input_datasets if name not in auxiliary_names)
            states = store.latest_common_ready_input_states(daily_inputs)
            missing = sorted(set(daily_inputs) - set(states))
            if missing:
                waiting[blueprint.task_key] = missing
                continue
            representative = next(iter(states.values()))
            observation_key = str(representative["observation_key"])
            start = min(
                state["observation_start"]
                for state in states.values()
                if state.get("observation_start") is not None
            )
            end = max(
                state["observation_end"]
                for state in states.values()
                if state.get("observation_end") is not None
            )
            auxiliary = {}
            auxiliary_names = TRANSFORMATION_AUXILIARY_INPUTS.get(blueprint.task_key, ())
            if auxiliary_names:
                auxiliary = store.auxiliary_input_revision(auxiliary_names, end)
                if auxiliary["pending_count"]:
                    waiting[blueprint.task_key] = ["auxiliary_input_repairs_pending"]
                    continue
            input_identity = ",".join(
                f"{name}:{state['dataset_state_id']}:{state['revision']}"
                for name, state in sorted(states.items())
            )
            if auxiliary:
                input_identity += f":aux:{auxiliary['revision_digest']}"
            _row, was_created = store.create_execution(ExecutionRequest(
                task_key=blueprint.task_key,
                purpose="daily",
                trigger_source="dependency",
                idempotency_key=(
                    f"v2:derived:{blueprint.task_key}:"
                    f"{blueprint.implementation_version}:{observation_key}:"
                    f"{input_identity}"
                ),
                observation_key=observation_key,
                observation_start=start,
                observation_end=end,
                observation_period=observation_key,
                publication_date=end,
                frozen_scope={
                    "dispatch": "v2_dependency_transformation",
                    "implementation_version": blueprint.implementation_version,
                    "auxiliary_input_revision": auxiliary,
                    "input_dataset_states": {
                        name: {
                            "dataset_state_id": state["dataset_state_id"],
                            "revision": state["revision"],
                        }
                        for name, state in states.items()
                    },
                },
                app_revision=APP_REVISION,
            ))
            created += int(was_created)
            existing += int(not was_created)
        except Exception as exc:
            errors[blueprint.task_key] = f"{type(exc).__name__}: {exc}"
    return {
        "eligible": eligible,
        "created": created,
        "existing": existing,
        "waiting": waiting,
        "errors": errors,
    }


def dispatch_group_weight_refresh(store, *, as_of: date):
    """One bounded V2 execution for the last closed month, never all indices.

    A failed/empty monthly refresh stays visible; idempotency prevents endless
    resubmission. This is not an Ant request and does not enable old fanouts.
    """
    end = as_of.replace(day=1) - timedelta(days=1)
    start = end.replace(day=1)
    rows = query(
        "SELECT index_code,max(trade_date) AS latest FROM tushare_current_index_weight "
        "WHERE index_code=ANY(%s) AND trade_date<=%s GROUP BY index_code",
        (['000300.SH', '000688.SH'], as_of),
    )
    latest = {row['index_code']: row['latest'] for row in rows}
    if all(latest.get(code) is not None and latest[code] >= start
           for code in ('000300.SH', '000688.SH')):
        return None
    return store.create_execution(ExecutionRequest(
        task_key='index_weight', purpose='repair', trigger_source='dependency',
        idempotency_key=f'v2:group-weight-refresh:{start}:{end}:v1',
        observation_key=f'history:{start}:{end}',
        observation_start=start, observation_end=end,
        frozen_scope={'recovery_scope': 'quota_guarded_history',
                      'fanout_values': ['000300.SH', '000688.SH'],
                      'dispatch': 'group_valuation_monthly_dependency'},
    ))


def dispatch_weekly_reference_profiles(as_of: date, *, repository=None):
    from service.orchestration_v2.automation_status import WEEKLY_REFERENCE_PROFILES
    store = repository or OrchestrationV2Repository()
    active = store.active_task_keys()
    week = (as_of - timedelta(days=as_of.weekday())).isoformat()
    created = existing = 0
    errors = {}
    for key in WEEKLY_REFERENCE_PROFILES:
        if key not in active:
            continue
        try:
            _, added = store.create_execution(ExecutionRequest(
                task_key=key, purpose='daily', trigger_source='schedule',
                idempotency_key=f'v2:reference-weekly:{key}:{week}:v1',
                observation_key=f'snapshot:{as_of}', observation_start=as_of, observation_end=as_of,
                frozen_scope={'reference_profile': key, 'profile_version': 1,
                              'dispatch': 'bounded_weekly_reference', 'collection_week': week},
            ))
        except Exception as exc:
            errors[key] = f'{type(exc).__name__}: {exc}'
            continue
        created += int(added)
        existing += int(not added)
    return {'created': created, 'existing': existing, 'errors': errors}


def dispatch_daily_acquisitions(
    target_date: date,
    *,
    delayed_target_date: date | None = None,
    us_target_date: date,
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
        if (
            blueprint.cadence == "daily"
            and blueprint.task_key not in DEFERRED_RESEARCH_DATASETS
        )
    )
    created = 0
    existing = 0
    errors: dict[str, str] = {}
    delayed_date = delayed_target_date or target_date
    for task_key in task_keys:
        observation_date = (
            us_target_date
            if task_key in US_COMPLETED_SESSION_TASKS
            else delayed_date
            if task_key in NEXT_MORNING_TASKS
            else target_date
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
        "us_target_date": us_target_date.isoformat(),
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
    next_morning_released: bool = False,
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
        next_morning_released=next_morning_released,
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
            if (
                item.cadence == cadence
                and item.task_key not in DEFERRED_RESEARCH_DATASETS
            )
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
    next_morning_released: bool = False,
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
    if dates[0] == as_of_date:
        if include_current_daily:
            target = dates[0]
        else:
            target = dates[1] if len(dates) > 1 else dates[0]
        if next_morning_released:
            delayed = dates[1] if len(dates) > 1 else dates[0]
        else:
            delayed = dates[2] if len(dates) > 2 else target
    else:
        target = next((item for item in dates if item < as_of_date), dates[0])
        # Next-morning datasets publish on the following *calendar* morning,
        # not the following trading day (verified live: etf_share_size,
        # margin and margin_detail expose Friday's partition by Saturday).
        # Once the 09:15 release gate has passed, a weekend/holiday may
        # therefore attempt the most recently closed day instead of staying
        # pinned to the day before it.
        delayed = (
            target
            if next_morning_released
            else next((item for item in dates if item < target), target)
        )
    us_rows = query(
        "SELECT cal_date FROM tushare_norm_us_tradecal WHERE is_open=1 "
        "AND cal_date < %s ORDER BY cal_date DESC LIMIT 1",
        (as_of_date,),
    )
    if not us_rows:
        return {
            "target_date": target.isoformat(),
            "delayed_target_date": delayed.isoformat(),
            "us_target_date": None,
            "trade_day": True,
            "eligible": 0,
            "created": 0,
            "existing": 0,
            "skipped": "us_trade_calendar_has_no_completed_open_day",
            "errors": {"us_daily": "US trade calendar has no completed open day"},
        }
    us_target = us_rows[0]["cal_date"]
    store = repository or OrchestrationV2Repository()
    superseded = []
    requeued = []
    if delayed != target:
        superseded = store.supersede_not_expected_daily_scope(
            target,
            tuple(sorted(NEXT_MORNING_TASKS)),
            reason=(
                "next-business-morning datasets are not due for "
                f"{target.isoformat()}; current eligible partition is "
                f"{delayed.isoformat()}"
            ),
        )
    elif next_morning_released:
        requeued = store.requeue_due_daily_scope(
            target,
            tuple(sorted(NEXT_MORNING_TASKS)),
            reason=(
                "next-business-morning publication gate opened for "
                f"{target.isoformat()}"
            ),
        )
    result = dispatch_daily_acquisitions(
        target,
        delayed_target_date=delayed,
        us_target_date=us_target,
        repository=store,
    )
    result["superseded_not_due"] = len(superseded)
    result["requeued_after_release"] = len(requeued)
    return result
