"""Canonical market-business clock used by every containerized service."""

from contextlib import contextmanager
from contextvars import ContextVar
from datetime import date, datetime
from zoneinfo import ZoneInfo


SHANGHAI_TIMEZONE = ZoneInfo("Asia/Shanghai")
_BUSINESS_TIME_OVERRIDE: ContextVar[datetime | None] = ContextVar(
    "business_time_override", default=None
)


def business_now() -> datetime:
    return _BUSINESS_TIME_OVERRIDE.get() or datetime.now(SHANGHAI_TIMEZONE)


def business_today() -> date:
    return business_now().date()


@contextmanager
def business_time(value: str | datetime | None):
    """Execute catch-up work using its planned Shanghai business timestamp."""
    if value is None:
        yield
        return
    parsed = datetime.fromisoformat(value) if isinstance(value, str) else value
    if parsed.tzinfo is None:
        raise ValueError("business time override must include a timezone")
    token = _BUSINESS_TIME_OVERRIDE.set(parsed.astimezone(SHANGHAI_TIMEZONE))
    try:
        yield
    finally:
        _BUSINESS_TIME_OVERRIDE.reset(token)
