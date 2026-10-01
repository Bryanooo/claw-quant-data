"""Shared schedule semantics for late-published dataset repair."""

from __future__ import annotations

from datetime import datetime, time, timedelta


LATE_REPAIR_HOURS = (15, 18, 21, 23)
LATE_REPAIR_MINUTE = 58


def next_late_repair_at(now: datetime) -> datetime:
    """Return the next post-close repair window in the business timezone."""

    for hour in LATE_REPAIR_HOURS:
        candidate = datetime.combine(
            now.date(), time(hour, LATE_REPAIR_MINUTE), tzinfo=now.tzinfo
        )
        if candidate > now:
            return candidate
    return datetime.combine(
        now.date() + timedelta(days=1),
        time(LATE_REPAIR_HOURS[0], LATE_REPAIR_MINUTE),
        tzinfo=now.tzinfo,
    )
