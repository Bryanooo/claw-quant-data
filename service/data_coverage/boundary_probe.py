"""Conservative backward probing for unknown upstream history boundaries.

Coverage before the first locally observed partition is not automatically a
gap.  For reviewed dense time series we can nevertheless probe backwards from
the newest unknown period.  Successful empty responses are evidence, not an
authoritative provider launch date, so this module can only produce a
``provisional_boundary`` result.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from calendar import monthrange
from typing import Iterable, Mapping


@dataclass(frozen=True, slots=True)
class BoundaryProbePolicy:
    dataset_name: str
    granularity: str
    consecutive_empty_periods: int
    reason: str


@dataclass(frozen=True, slots=True)
class ProbePeriod:
    key: str
    start: date
    end: date


@dataclass(frozen=True, slots=True)
class BoundaryProbePlan:
    dataset_name: str
    status: str
    candidates: tuple[ProbePeriod, ...]
    provisional_boundary: date | None
    reason: str


# Sparse disclosures, constituent changes and adjustment events are
# deliberately absent. An empty response for those datasets says nothing about
# the provider's historical availability boundary.
BOUNDARY_PROBE_POLICIES: dict[str, BoundaryProbePolicy] = {
    name: BoundaryProbePolicy(name, "day", 20, "reviewed dense daily series")
    for name in (
        "dc_daily", "fund_daily", "idx_factor_pro", "margin",
        "margin_detail", "moneyflow", "moneyflow_ind_ths",
        "moneyflow_mkt_dc", "sge_daily", "shibor", "stk_auction",
        "stk_factor", "stk_factor_pro", "sz_daily_info",
    )
}
BOUNDARY_PROBE_POLICIES.update({
    "index_weekly": BoundaryProbePolicy(
        "index_weekly", "week", 8, "reviewed dense weekly series"
    ),
    "index_monthly": BoundaryProbePolicy(
        "index_monthly", "month", 6, "reviewed dense monthly series"
    ),
})


def _month_before(value: date) -> date:
    return (
        date(value.year - 1, 12, 1)
        if value.month == 1
        else date(value.year, value.month - 1, 1)
    )

def _periods_before(
    *, earliest_observed: date, granularity: str, trade_dates: Iterable[date]
) -> tuple[ProbePeriod, ...]:
    if granularity == "day":
        return tuple(
            ProbePeriod(day.isoformat(), day, day)
            for day in sorted(
                {day for day in trade_dates if day < earliest_observed},
                reverse=True,
            )
        )
    if granularity == "week":
        cursor = earliest_observed - timedelta(days=earliest_observed.weekday() + 1)
        periods = []
        for _ in range(5200):
            start = cursor - timedelta(days=cursor.weekday())
            iso_year, iso_week, _ = start.isocalendar()
            periods.append(ProbePeriod(
                f"{iso_year}-W{iso_week:02d}", start, start + timedelta(days=6)
            ))
            cursor = start - timedelta(days=1)
        return tuple(periods)
    if granularity == "month":
        cursor = _month_before(date(earliest_observed.year, earliest_observed.month, 1))
        periods = []
        for _ in range(1200):
            end = date(cursor.year, cursor.month, monthrange(cursor.year, cursor.month)[1])
            periods.append(ProbePeriod(cursor.strftime("%Y-%m"), cursor, end))
            cursor = _month_before(cursor)
        return tuple(periods)
    raise ValueError(f"unsupported boundary probe granularity: {granularity}")


def build_boundary_probe_plan(
    *,
    dataset_name: str,
    earliest_observed: date,
    trade_dates: Iterable[date] = (),
    evidence: Mapping[str, str] | None = None,
) -> BoundaryProbePlan:
    """Plan a small newest-first probe batch or assess accumulated evidence.

    Evidence values are ``data``, ``verified_empty`` or ``failed``.  Empty is
    accepted only after a successful, pagination-exhausted V2 acquisition and
    audit node; callers must never pass transport errors as empty evidence.
    """
    policy = BOUNDARY_PROBE_POLICIES.get(dataset_name)
    if policy is None:
        return BoundaryProbePlan(
            dataset_name, "ineligible", (), None,
            "sparse/event/entity-scoped dataset requires a declared contract boundary",
        )
    outcomes = dict(evidence or {})
    periods = _periods_before(
        earliest_observed=earliest_observed,
        granularity=policy.granularity,
        trade_dates=trade_dates,
    )
    if not periods:
        return BoundaryProbePlan(
            dataset_name, "insufficient_calendar", (), None,
            "no earlier candidate period is available",
        )

    invalid = sorted(set(outcomes.values()) - {"data", "verified_empty", "failed"})
    if invalid:
        raise ValueError(f"invalid boundary evidence states: {invalid}")

    for period in periods:
        if outcomes.get(period.key) == "data":
            return BoundaryProbePlan(
                dataset_name, "history_extended", (), None,
                "older data exists; move earliest_observed backward and restart probing",
            )

    required = periods[:policy.consecutive_empty_periods]
    retry = tuple(period for period in required if outcomes.get(period.key) == "failed")
    if retry:
        return BoundaryProbePlan(
            dataset_name, "retry_required", retry, None,
            "failed transport/audit cannot be interpreted as an empty period",
        )
    missing = tuple(period for period in required if period.key not in outcomes)
    if missing:
        return BoundaryProbePlan(
            dataset_name, "probe", missing, None,
            "probe the nearest unknown periods first",
        )
    if any(outcomes.get(period.key) != "verified_empty" for period in required):
        return BoundaryProbePlan(
            dataset_name, "inconclusive", (), None,
            "the contiguous evidence window is not fully verified empty",
        )

    # A separated older anchor protects against a short publication hiatus.
    anchor_index = min(
        len(periods) - 1,
        policy.consecutive_empty_periods * 2 - 1,
    )
    anchor = periods[anchor_index]
    anchor_state = outcomes.get(anchor.key)
    if anchor_state == "failed":
        return BoundaryProbePlan(
            dataset_name, "retry_required", (anchor,), None,
            "the older anchor failed and must be retried",
        )
    if anchor_state is None:
        return BoundaryProbePlan(
            dataset_name, "probe_anchor", (anchor,), None,
            "contiguous empty window verified; verify one separated older anchor",
        )
    if anchor_state == "data":
        return BoundaryProbePlan(
            dataset_name, "history_extended", (), None,
            "the older anchor contains data; continue from that earlier observation",
        )
    return BoundaryProbePlan(
        dataset_name,
        "provisional_boundary",
        (),
        earliest_observed,
        (
            "contiguous and separated empty evidence verified; this is an observed "
            "boundary, not an authoritative provider launch date"
        ),
    )
