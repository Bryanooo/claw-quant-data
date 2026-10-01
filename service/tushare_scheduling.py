"""Pure Tushare policy-to-request parameter resolution for V2."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from service.db import query
from service.tushare_policy import TushareCollectionPolicy


SHANGHAI_TIMEZONE = ZoneInfo("Asia/Shanghai")
DEDICATED_SCHEDULED_APIS: set[str] = set()
DEDICATED_RUN_IDS: dict[str, tuple[str, ...]] = {}
DEDICATED_API_BY_RUN_ID: dict[str, str] = {}


def local_today() -> date:
    return datetime.now(SHANGHAI_TIMEZONE).date()


def _latest_trade_date(today: date) -> str:
    rows = query(
        "SELECT max(cal_date) AS trade_date FROM trade_cal "
        "WHERE exchange='SSE' AND is_open=1 AND cal_date<=%s",
        (today,),
    )
    if rows and rows[0]["trade_date"]:
        return rows[0]["trade_date"].strftime("%Y%m%d")
    probe = today
    while probe.weekday() >= 5:
        probe -= timedelta(days=1)
    return probe.strftime("%Y%m%d")


def _previous_month(today: date) -> str:
    return (today.replace(day=1) - timedelta(days=1)).strftime("%Y%m")


def _latest_report_period(today: date) -> str:
    if today.month >= 10:
        return f"{today.year}0930"
    if today.month >= 7:
        return f"{today.year}0630"
    if today.month >= 4:
        return f"{today.year}0331"
    return f"{today.year - 1}1231"


def parameters_for_policy(
    policy: TushareCollectionPolicy,
    input_names: set[str],
    *,
    today: date,
    trade_date: str | None = None,
) -> dict[str, Any]:
    """Resolve one bounded provider request; no task is created here."""
    resolved_trade_date = trade_date or _latest_trade_date(today)
    strategy = policy.parameter_strategy
    if strategy == "snapshot":
        return {}
    if strategy == "trade_date":
        for name in ("trade_date", "date", "cal_date", "ann_date", "nav_date", "ex_date"):
            if name in input_names:
                return {name: resolved_trade_date}
        if {"start_date", "end_date"} <= input_names:
            return {"start_date": resolved_trade_date, "end_date": resolved_trade_date}
        # Tushare's machine-readable catalog omits the request schema for a
        # handful of legacy endpoints even though the provider accepts the
        # documented ``trade_date`` argument.  Keep this closed allow-list so
        # missing catalog metadata cannot turn into an unbounded request.
        if policy.api_name in {"ggt_daily", "ggt_top10"}:
            return {"trade_date": resolved_trade_date}
    if strategy == "date_window":
        if {"start_date", "end_date"} <= input_names:
            if policy.api_name == "eco_cal":
                anchor = datetime.strptime(resolved_trade_date, "%Y%m%d").date()
                return {
                    "start_date": (anchor - timedelta(days=7)).strftime("%Y%m%d"),
                    "end_date": (anchor + timedelta(days=45)).strftime("%Y%m%d"),
                }
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
        if {"start_q", "end_q"} <= input_names:
            quarter = (int(period[4:6]) - 1) // 3 + 1
            value = f"{period[:4]}Q{quarter}"
            return {"start_q": value, "end_q": value}
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
