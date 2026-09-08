"""Policy-driven submission of recurring Tushare collection jobs."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
import hashlib
import json
from typing import Any
from zoneinfo import ZoneInfo

from service.collection_jobs.repository import JobRepository
from service.collection_jobs.registry import TASKS
from service.db import query
from service.tushare_catalog import TushareInterfaceCatalog
from service.tushare_policy import TushareCollectionPolicy, TusharePolicyRegistry
from service.clock import business_now


# These interfaces already have purpose-built scheduler jobs writing normalized
# tables. Policy dispatch must not duplicate them through raw collection.
DEDICATED_SCHEDULED_APIS = {
    "bak_basic", "balancesheet", "balancesheet_vip", "cashflow", "cashflow_vip",
    "daily", "disclosure_date", "express", "express_vip", "fina_indicator",
    "fina_indicator_vip", "fina_mainbz", "fina_mainbz_vip", "forecast",
    "forecast_vip", "fx_daily", "fx_obasic", "ggt_daily", "ggt_top10",
    "hsgt_top10", "income", "income_vip", "index_basic", "index_daily",
    "index_dailybasic", "index_global", "monthly", "new_share", "sge_basic",
    "sge_daily", "st", "stk_limit", "stk_weekly_monthly", "stock_basic",
    "stock_company", "stock_hsgt", "stock_st", "suspend_d", "ths_daily",
    "ths_member", "trade_cal", "weekly",
}

# One scheduler run can populate a normal endpoint and its VIP alias. Keeping
# the mapping explicit prevents the dashboard from guessing by task-id prefix.
DEDICATED_RUN_IDS: dict[str, tuple[str, ...]] = {
    "bak_basic": ("bak_basic_daily",),
    "balancesheet": ("balancesheet_quarterly",),
    "balancesheet_vip": ("balancesheet_quarterly",),
    "cashflow": ("cashflow_quarterly",),
    "cashflow_vip": ("cashflow_quarterly",),
    "daily": ("daily_daily",),
    "disclosure_date": ("disclosure_date_quarterly",),
    "express": ("express_annual",),
    "express_vip": ("express_annual",),
    "fina_indicator": ("fina_indicator_quarterly",),
    "fina_indicator_vip": ("fina_indicator_quarterly",),
    "fina_mainbz": ("mainbz_annual",),
    "fina_mainbz_vip": ("mainbz_annual",),
    "forecast": ("forecast_seasonal",),
    "forecast_vip": ("forecast_seasonal",),
    "fx_daily": ("fx_daily_daily",),
    "fx_obasic": ("fx_obasic_weekly",),
    "ggt_daily": ("ggt_daily_daily",),
    "ggt_top10": ("ggt_top10_daily",),
    "hsgt_top10": ("hsgt_top10_daily",),
    "income": ("income_quarterly",),
    "income_vip": ("income_quarterly",),
    "index_basic": ("index_basic_weekly",),
    "index_daily": ("index_daily_daily", "index_daily_finalize"),
    "index_dailybasic": ("index_dailybasic_daily",),
    "index_global": ("index_global_daily",),
    "monthly": ("stk_monthly_monthly_eom",),
    "new_share": ("new_share_weekly",),
    "sge_basic": ("sge_basic_weekly",),
    "sge_daily": ("sge_daily_daily",),
    "st": ("stock_st_daily",),
    "stk_limit": ("stk_limit_daily",),
    "stk_weekly_monthly": (
        "stk_weekly_monthly_week_daily",
        "stk_weekly_monthly_month_daily",
    ),
    "stock_basic": ("stock_basic_daily",),
    "stock_company": ("stock_company_weekly",),
    "stock_hsgt": ("stock_hsgt_daily",),
    "stock_st": ("stock_st_daily",),
    "suspend_d": ("suspend_d_daily",),
    "ths_daily": ("ths_daily_daily",),
    "ths_member": ("ths_member_weekly",),
    "trade_cal": ("trade_cal_daily",),
    "weekly": ("stk_weekly_weekly_fri",),
}

# Durable queue jobs need one canonical API identity so their verification
# result is visible at interface level.  VIP aliases deliberately share the
# normalized dataset populated by the same dedicated collector; prefer the
# non-VIP contract as the canonical identity.
DEDICATED_API_BY_RUN_ID: dict[str, str] = {}
for _api_name in sorted(
    DEDICATED_RUN_IDS,
    key=lambda value: (value.endswith("_vip"), value),
):
    for _run_id in DEDICATED_RUN_IDS[_api_name]:
        DEDICATED_API_BY_RUN_ID.setdefault(_run_id, _api_name)


SHANGHAI_TIMEZONE = ZoneInfo("Asia/Shanghai")

# Empty data is not treated as a transport failure: it may be a valid event
# partition or an upstream publication delay. Rechecks therefore happen as
# separate jobs, slowly enough to avoid blind polling and for a bounded window.
_EMPTY_RECHECK_POLICIES = {
    "daily": {"min_interval_seconds": 4 * 3600, "max_generations": 3, "window_days": 4},
    "weekly": {"min_interval_seconds": 24 * 3600, "max_generations": 5, "window_days": 14},
    "monthly": {"min_interval_seconds": 24 * 3600, "max_generations": 10, "window_days": 45},
    "quarterly": {"min_interval_seconds": 7 * 24 * 3600, "max_generations": 14, "window_days": 120},
}

# These daily interfaces can legitimately remain empty until the following
# morning.  Do not consume a bounded empty-recheck generation before their
# documented publication window has closed.
_NEXT_MORNING_RELEASES = {
    # doc 295: the previous trading day's CCASS aggregate is normally
    # published before 09:00 on the next trading day.
    "ccass_hold": time(9, 15),
    "etf_share_size": time(9, 15),
    "margin": time(9, 15),
    "margin_detail": time(9, 15),
}


def _publication_is_mature(api_name: str, expected_for: date | None) -> bool:
    release_after = _NEXT_MORNING_RELEASES.get(api_name)
    if not release_after or not expected_for:
        return True
    now = business_now().astimezone(SHANGHAI_TIMEZONE)
    publication_day = expected_for + timedelta(days=1)
    return now.date() > publication_day or (
        now.date() == publication_day and now.time().replace(tzinfo=None) >= release_after
    )


def local_today() -> date:
    return datetime.now(SHANGHAI_TIMEZONE).date()


def _latest_trade_date(today: date) -> str:
    rows = query(
        """
        SELECT max(cal_date) AS trade_date
        FROM trade_cal
        WHERE exchange = 'SSE' AND is_open = 1 AND cal_date <= %s
        """,
        (today,),
    )
    if rows and rows[0]["trade_date"]:
        return rows[0]["trade_date"].strftime("%Y%m%d")
    probe = today
    while probe.weekday() >= 5:
        probe -= timedelta(days=1)
    return probe.strftime("%Y%m%d")


def _previous_month(today: date) -> str:
    first = today.replace(day=1)
    return (first - timedelta(days=1)).strftime("%Y%m")


def _latest_report_period(today: date) -> str:
    year = today.year
    if today.month >= 10:
        return f"{year}0930"
    if today.month >= 7:
        return f"{year}0630"
    if today.month >= 4:
        return f"{year}0331"
    return f"{year - 1}1231"


def parameters_for_policy(
    policy: TushareCollectionPolicy,
    input_names: set[str],
    *,
    today: date,
    trade_date: str | None = None,
) -> dict[str, Any]:
    resolved_trade_date = trade_date or _latest_trade_date(today)
    strategy = policy.parameter_strategy
    if strategy == "snapshot":
        return {}
    if strategy == "trade_date":
        for name in (
            "trade_date",
            "date",
            "cal_date",
            "ann_date",
            "nav_date",
            "ex_date",
        ):
            if name in input_names:
                return {name: resolved_trade_date}
        if {"start_date", "end_date"} <= input_names:
            return {"start_date": resolved_trade_date, "end_date": resolved_trade_date}
    if strategy == "date_window":
        if {"start_date", "end_date"} <= input_names:
            return {"start_date": resolved_trade_date, "end_date": resolved_trade_date}
        for name in ("trade_date", "date"):
            if name in input_names:
                return {name: resolved_trade_date}
    if strategy == "month":
        month = _previous_month(today)
        if {"start_m", "end_m"} <= input_names:
            return {"start_m": month, "end_m": month}
        if {"start_month", "end_month"} <= input_names:
            return {"start_month": month, "end_month": month}
        for name in ("month", "m"):
            if name in input_names:
                return {name: month}
    if strategy == "report_period":
        period = _latest_report_period(today)
        for name in ("period", "report_date", "end_date"):
            if name in input_names:
                return {name: period}
    if strategy == "week":
        iso = today.isocalendar()
        week = f"{iso.year}{iso.week:02d}"
        if "week" in input_names:
            return {"week": week}
        if {"start_week", "end_week"} <= input_names:
            return {"start_week": week, "end_week": week}
    raise ValueError(
        f"cannot build parameters for {policy.api_name}: {policy.parameter_strategy}"
    )


def _scope_key(cadence: str, today: date, parameters: dict[str, Any]) -> str:
    period = _period_key(cadence, today)
    digest = hashlib.sha256(
        json.dumps(parameters, sort_keys=True).encode("utf-8")
    ).hexdigest()[:12]
    return f"policy-{cadence}-{period}-{digest}"


def _policy_job_key(
    api_name: str,
    cadence: str,
    scope_date: date,
    parameters: dict[str, Any],
    handler,
) -> str:
    """Keep retries idempotent while allowing intentional handler upgrades."""
    handler_digest = hashlib.sha256(
        f"{handler.handler_type}:{handler.handler_key}:{handler.handler_version}".encode()
    ).hexdigest()[:12]
    raw = (
        f"{api_name}-{_scope_key(cadence, scope_date, parameters)}"
        f"-handler-{handler_digest}"
    )
    if len(raw) <= 128:
        return raw
    return f"policy-{hashlib.sha256(raw.encode()).hexdigest()}"


def _period_key(cadence: str, today: date) -> str:
    if cadence == "daily":
        return today.isoformat()
    elif cadence == "weekly":
        iso = today.isocalendar()
        return f"{iso.year}-W{iso.week:02d}"
    elif cadence == "monthly":
        return today.strftime("%Y-%m")
    return _latest_report_period(today)


def _resolved_scope(cadence: str, target_date: date) -> tuple[date, str | None]:
    """Resolve job identity to the last trading day of a closed period."""
    if cadence == "daily":
        boundary = target_date
    elif cadence == "weekly":
        # ``target_date`` is any day in the intended closed week. Sunday is a
        # stable boundary; the calendar then supplies Friday or the preceding
        # holiday-adjusted last trading day.
        boundary = target_date + timedelta(days=6 - target_date.weekday())
    elif cadence == "monthly":
        # Monthly patrols collect the previous fully closed calendar month.
        boundary = target_date.replace(day=1) - timedelta(days=1)
    else:
        return target_date, None

    trade_date = _latest_trade_date(boundary)
    return (
        date(
            int(trade_date[:4]),
            int(trade_date[4:6]),
            int(trade_date[6:]),
        ),
        trade_date,
    )


def submit_policy_batch(
    cadence: str,
    *,
    today: date | None = None,
    repository: JobRepository | None = None,
) -> int:
    """Submit one idempotent job for every safe, unscheduled policy."""
    from service.initialization.repository import routine_collection_enabled

    if not routine_collection_enabled():
        return 0
    target_date = today or local_today()
    scope_date, resolved_trade_date = _resolved_scope(cadence, target_date)
    catalog = TushareInterfaceCatalog()
    policies = TusharePolicyRegistry()
    job_repository = repository or JobRepository()
    submitted = 0
    for contract in catalog.list():
        if not contract.collectable or contract.api_name in DEDICATED_SCHEDULED_APIS:
            continue
        policy = policies.get(contract.api_name)
        if not policy.automatic_safe or policy.cadence != cadence:
            continue
        input_names = {item["name"] for item in contract.input_parameters}
        parameters = parameters_for_policy(
            policy,
            input_names,
            today=target_date,
            trade_date=resolved_trade_date,
        )
        payload = {
            "api_name": contract.api_name,
            "parameters": parameters,
            "complete": True,
            "resume": True,
        }
        handler = TASKS.handler_metadata("tushare_interface", payload)
        idempotency_key = _policy_job_key(
            contract.api_name,
            cadence,
            scope_date,
            parameters,
            handler,
        )
        job, created = job_repository.create(
            "tushare_interface",
            payload,
            max_attempts=3,
            idempotency_key=idempotency_key,
            api_name=contract.api_name,
            cadence=cadence,
            period_key=_period_key(cadence, scope_date),
            expected_for=scope_date,
            handler_type=handler.handler_type,
            handler_key=handler.handler_key,
            handler_version=handler.handler_version,
            code_revision=handler.code_revision,
            priority={"daily": 80, "weekly": 60, "monthly": 50, "quarterly": 45}.get(cadence, 40),
            resource_class="generic",
        )
        submitted += int(created)
        if not created and _publication_is_mature(contract.api_name, scope_date):
            recheck = job_repository.create_empty_recheck(
                int(job["job_id"]),
                **_EMPTY_RECHECK_POLICIES[cadence],
                handler=handler,
            )
            submitted += int(recheck is not None)
    return submitted


def submit_latest_policy_batches(
    *,
    today: date | None = None,
    include_current_daily: bool = False,
) -> dict[str, int]:
    """Idempotently create the latest publishable scope for every cadence.

    Morning and midday patrols deliberately use the previous calendar day so
    they never request an unfinished market partition.  The post-close patrols
    opt into ``include_current_daily`` and submit the current trade date.  This
    gives same-day data two attempts (19:10 and 23:10) without sacrificing the
    safe startup/morning catch-up behaviour.
    """
    now = today or local_today()
    daily_scope = now if include_current_daily else now - timedelta(days=1)
    return {
        "daily": submit_policy_batch("daily", today=daily_scope),
        "weekly": submit_policy_batch("weekly", today=now - timedelta(days=7)),
        "monthly": submit_policy_batch("monthly", today=now),
        "quarterly": submit_policy_batch("quarterly", today=now),
    }
