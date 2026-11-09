"""Shared schedule semantics for late-published dataset repair."""

from __future__ import annotations

from datetime import datetime, time, timedelta

from service.data_coverage.publication import NEXT_DAY_EMPTY_CONFIRMATION


LATE_REPAIR_HOURS = (15, 18, 21, 23)
LATE_REPAIR_MINUTE = 58
LATE_PUBLISHED_DATASETS = NEXT_DAY_EMPTY_CONFIRMATION | frozenset({
    "ccass_hold",
    # Use dataset keys (ths_daily publishes industry_daily). Both can be
    # incomplete at the initial evening run even when transport succeeded.
    "industry_daily",
    "index_daily",
    "etf_share_size",
    # Provider factor snapshots are published progressively after the close.
    # The first daily pass can be verified-empty or only partially cover the
    # stock/fund universe, so bounded fresh executions must revisit them.
    "fund_factor_pro",
    "margin",
    "margin_detail",
    "stk_factor",
    "stk_factor_pro",
})


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
