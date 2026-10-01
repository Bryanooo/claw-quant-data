"""Failure classification and market-hours protection for V2 acquisition."""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime, timedelta

from service.clock import SHANGHAI_TIMEZONE, business_now
from service.config import (
    HISTORY_COLLECTION_PAUSE_START_TIME,
    HISTORY_COLLECTION_RESUME_TIME,
)


logger = logging.getLogger("acquisition-runtime")
HISTORICAL_PURPOSES = frozenset({"backfill", "initialization", "repair"})
HISTORICAL_RESOURCE_CLASSES = frozenset({"v2-backfill"})


def _is_sse_trade_day(value) -> bool:
    from service.db import query

    try:
        rows = query(
            "SELECT is_open FROM trade_cal "
            "WHERE exchange='SSE' AND cal_date=%s",
            (value,),
        )
    except Exception:
        logger.exception("cannot read SSE trade calendar for history gate")
        return value.weekday() < 5
    if not rows:
        logger.warning("SSE trade calendar has no row for %s", value)
        return value.weekday() < 5
    return bool(rows[0]["is_open"])


def historical_resume_at(
    purpose: str | None,
    *,
    resource_class: str | None = None,
    now: datetime | None = None,
    trade_day_checker: Callable[[object], bool] | None = None,
) -> datetime | None:
    """Return the next safe time when history is paused during live trading."""
    if (
        purpose not in HISTORICAL_PURPOSES
        and resource_class not in HISTORICAL_RESOURCE_CLASSES
    ):
        return None
    current = (now or business_now()).astimezone(SHANGHAI_TIMEZONE)
    local_time = current.time().replace(tzinfo=None)
    pause = HISTORY_COLLECTION_PAUSE_START_TIME
    resume = HISTORY_COLLECTION_RESUME_TIME
    if pause < resume:
        blocked = pause <= local_time < resume
        resume_day = current.date()
    else:
        blocked = local_time >= pause or local_time < resume
        resume_day = current.date() + timedelta(days=int(local_time >= pause))
    if not blocked or not (trade_day_checker or _is_sse_trade_day)(current.date()):
        return None
    return datetime.combine(resume_day, resume, tzinfo=SHANGHAI_TIMEZONE)


def classify_failure(exc: Exception) -> str:
    """Return a stable operator-facing failure category."""
    name = type(exc).__name__.lower()
    message = str(exc).lower()
    if "ratelimit" in name or "quota" in message or "频率" in message:
        return "quota"
    if isinstance(exc, TimeoutError) or "timeout" in name or "timed out" in message:
        return "timeout"
    if "incomplete" in name or "truncat" in message or "cap (" in message:
        return "completeness"
    if "permission" in message or "访问权限" in message or "token" in message:
        return "permission"
    if (
        "validation" in name
        or "invalid" in name
        or "parameter" in message
        or "参数" in message
    ):
        return "invalid_request"
    if "handler" in name and "mismatch" in name:
        return "deployment_mismatch"
    if "psycopg" in name or "database" in name or "sql" in name:
        return "storage"
    if any(marker in name or marker in message for marker in (
        "connection", "network", "httperror", "connection reset", "dns",
        "gaierror", "name or service not known", "name resolution",
        "nodename nor servname",
    )):
        return "network"
    return "upstream_or_internal"
