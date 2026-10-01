"""Reverse-chronological history recovery for audited dataset gaps.

The normal scheduler is intentionally forward-looking.  This module closes the
other half of the contract: once coverage auditing proves that history is
missing, build bounded upstream requests from the newest missing partition
backwards.  Newer research history therefore becomes usable first, while every
leaf remains idempotent, paginated and subject to the market-hours gate.
"""

from __future__ import annotations

from bisect import bisect_left
import calendar
from dataclasses import dataclass
from datetime import date
import hashlib
from typing import Iterable

from service.acquisition_runtime.models import (
    BatchChildSpec,
    HISTORICAL_MAX_ATTEMPTS,
)
from service.acquisition_runtime.fanout import FANOUT_DEFINITIONS
from service.acquisition_runtime.registry import TASKS
from service.history_baselines import (
    HistoryPartition,
    catalog_history_partitions,
    fixed_day_windows,
    generic_policy_history_partitions,
    research_history_partitions,
    UPSTREAM_HISTORY_STARTS,
)
from service.tushare_policy import TusharePolicyRegistry


# Public dataset names are stable research/data-service identities.  A few
# upstream APIs use a different transport name; this mapping keeps the V2 task,
# normalized table and coverage rule on one stable dataset identity.
DATASET_API_ALIASES = {
    "forex_daily": "fx_daily",
    "industry_daily": "ths_daily",
    "stock_suspend": "suspend_d",
    "trade_calendar": "trade_cal",
}

# These APIs have more precise history recipes than the generic policy engine
# (currency variants, seven-day safety windows, etc.).
CATALOG_RECIPE_APIS = {
    "gz_index", "libor", "shibor_lpr", "slb_len", "slb_len_mm",
    "slb_sec", "slb_sec_detail", "stk_account", "wz_index",
}
RESEARCH_RECIPE_APIS = {
    "hk_hold", "major_news", "report_rc", "repurchase", "share_float",
    "stk_holdernumber", "stk_holdertrade",
}
# Live offset-exhaustion evidence proves these former fan-out definitions can
# use a complete market-wide partition. Keep the definitions for compatibility
# with old campaigns, but prefer the much cheaper direct history plan.
# Live pagination probes proved that these provider endpoints can exhaust one
# bounded market-wide partition.  Keeping the legacy entity fan-out would turn
# a single V2 acquire node into tens of thousands of calls and make retry time
# proportional to the entire reference universe.
MARKET_WIDE_FANOUT_OVERRIDES = {
    "fund_nav",
    "fund_portfolio",
    "index_weekly",
    "index_monthly",
}


@dataclass(frozen=True, slots=True)
class ReverseRecoveryPlan:
    specs: tuple[BatchChildSpec, ...]
    unsupported: dict[str, str]


@dataclass(frozen=True, slots=True)
class ReverseFanoutScope:
    api_name: str
    request: dict[str, object]
    period_key: str
    expected_for: date

    @property
    def idempotency_key(self) -> str:
        payload = f"{self.api_name}:{self.period_key}:{self.request}"
        return f"reverse-fanout-v2-{hashlib.sha256(payload.encode()).hexdigest()}"


def upstream_api_name(dataset_name: str, collection_api_name: str | None) -> str:
    return collection_api_name or DATASET_API_ALIASES.get(dataset_name, dataset_name)


def _quarter_partitions(start: date, end: date) -> Iterable[HistoryPartition]:
    """GDP's optional quarter-range contract is misclassified as snapshot."""
    for year in range(start.year, end.year + 1):
        for quarter, month, day in (
            (1, 3, 31), (2, 6, 30), (3, 9, 30), (4, 12, 31)
        ):
            period = date(year, month, day)
            if start <= period <= end:
                value = f"{year}Q{quarter}"
                yield HistoryPartition(
                    api_name="cn_gdp",
                    start_date=period,
                    end_date=period,
                    variant=None,
                    parameters={"start_q": value, "end_q": value},
                )


def _month_partitions(
    api_name: str, start: date, end: date
) -> Iterable[HistoryPartition]:
    cursor = date(start.year, start.month, 1)
    while cursor <= end:
        month_end = date(
            cursor.year,
            cursor.month,
            calendar.monthrange(cursor.year, cursor.month)[1],
        )
        yield HistoryPartition(
            api_name=api_name,
            start_date=cursor,
            end_date=min(month_end, end),
            variant=None,
            parameters={"month": cursor.strftime("%Y%m")},
        )
        cursor = (
            date(cursor.year + 1, 1, 1)
            if cursor.month == 12
            else date(cursor.year, cursor.month + 1, 1)
        )


def _contains_target(
    partition: HistoryPartition, sorted_targets: tuple[date, ...]
) -> bool:
    if not sorted_targets:
        return True
    index = bisect_left(sorted_targets, partition.start_date)
    return index < len(sorted_targets) and sorted_targets[index] <= partition.end_date


def _safe_key(value: str) -> str:
    if len(value) <= 128:
        return value
    return f"reverse-history-v2-{hashlib.sha256(value.encode()).hexdigest()}"


def _priority(partition_end: date, history_end: date) -> int:
    age_days = (history_end - partition_end).days
    if age_days <= 366:
        return 30
    if age_days <= 366 * 5:
        return 25
    if age_days <= 366 * 10:
        return 20
    return 15


def build_reverse_recovery_plan(
    *,
    dataset_apis: dict[str, str],
    targets_by_dataset: dict[str, Iterable[date]],
    history_start: date,
    history_end: date,
    trade_dates: Iterable[date],
) -> ReverseRecoveryPlan:
    """Build idempotent direct-interface leaves, globally newest first.

    ``targets_by_dataset`` contains dates proven missing/partial by coverage.
    An empty iterable means the dataset needs a declared historical transport
    scope (for example an observed-only dataset that has rows but no backfill
    certificate), so every bounded partition is planned.
    """
    if history_start > history_end:
        raise ValueError("history_start must not be later than history_end")

    policies = TusharePolicyRegistry()
    api_to_datasets: dict[str, list[str]] = {}
    unsupported: dict[str, str] = {}
    for dataset_name, api_name in dataset_apis.items():
        if api_name == "ggt_monthly":
            api_to_datasets.setdefault(api_name, []).append(dataset_name)
            continue
        if (
            api_name in FANOUT_DEFINITIONS
            and api_name not in MARKET_WIDE_FANOUT_OVERRIDES
        ):
            unsupported[dataset_name] = "requires bounded fan-out history campaign"
            continue
        try:
            policy = policies.get(api_name)
        except Exception as exc:  # catalog raises a domain-specific KeyError wrapper
            unsupported[dataset_name] = str(exc)
            continue
        if not policy.automatic_safe and api_name != "ggt_top10":
            unsupported[dataset_name] = policy.automatic_reason
            continue
        api_to_datasets.setdefault(api_name, []).append(dataset_name)

    partitions: list[HistoryPartition] = []
    requested_apis = set(api_to_datasets)
    special_apis = requested_apis & (CATALOG_RECIPE_APIS | RESEARCH_RECIPE_APIS)
    if special_apis:
        partitions.extend(
            item for item in catalog_history_partitions(history_start, history_end)
            if item.api_name in special_apis
        )
        partitions.extend(
            item for item in research_history_partitions(history_start, history_end)
            if item.api_name in special_apis
        )
    if "cn_gdp" in requested_apis:
        partitions.extend(_quarter_partitions(history_start, history_end))
    if "ggt_monthly" in requested_apis:
        partitions.extend(
            _month_partitions("ggt_monthly", history_start, history_end)
        )

    generic_apis = requested_apis - special_apis - {
        "cn_gdp", "ggt_monthly", "ggt_top10"
    }
    partitions.extend(
        item
        for item in generic_policy_history_partitions(
            history_start,
            history_end,
            trade_dates=tuple(trade_dates),
            excluded_api_names=requested_apis - generic_apis,
        )
        if item.api_name in generic_apis
    )
    # ggt_top10 is a legacy SDK endpoint whose current generated catalog lacks
    # its historical parameters.  Exact trading dates are the proven contract.
    if "ggt_top10" in requested_apis:
        ggt_start = max(
            history_start,
            UPSTREAM_HISTORY_STARTS["ggt_top10"],
        )
        partitions.extend(
            HistoryPartition(
                api_name="ggt_top10",
                start_date=trade_date,
                end_date=trade_date,
                variant=None,
                parameters={"trade_date": trade_date.strftime("%Y%m%d")},
            )
            for trade_date in trade_dates
            if ggt_start <= trade_date <= history_end
        )

    targets = {
        name: tuple(sorted(set(values)))
        for name, values in targets_by_dataset.items()
    }
    selected: list[tuple[str, HistoryPartition]] = []
    seen: set[tuple[str, str]] = set()
    for partition in partitions:
        for dataset_name in api_to_datasets.get(partition.api_name, ()):  # aliases
            if not _contains_target(partition, targets.get(dataset_name, ())):
                continue
            identity = (dataset_name, partition.key)
            if identity not in seen:
                selected.append((dataset_name, partition))
                seen.add(identity)

    # Priority gives the queue a durable global ordering; list order makes the
    # ordering deterministic even when rows receive the same created_at value.
    selected.sort(
        key=lambda item: (item[1].end_date, item[0], item[1].key), reverse=True
    )
    specs: list[BatchChildSpec] = []
    for dataset_name, partition in selected:
        if partition.api_name == "ggt_monthly":
            task_name = "ggt_monthly"
            parameters = dict(partition.parameters)
        else:
            task_name = "tushare_interface"
            policy = policies.get(partition.api_name)
            parameters = {
                "api_name": partition.api_name,
                "parameters": partition.parameters,
                "complete": True,
                "page_size": policy.page_size,
                "max_pages": max(policy.max_pages, 1000),
                "resume": True,
            }
        scope_identity = f"{dataset_name}:{partition.key}"
        period_key = (
            f"rh:{partition.end_date:%Y%m%d}:"
            f"{hashlib.sha256(scope_identity.encode()).hexdigest()[:12]}"
        )
        specs.append(
            BatchChildSpec(
                task_name=task_name,
                parameters=parameters,
                idempotency_key=_safe_key(
                    f"reverse-history-v2:{scope_identity}"
                ),
                api_name=partition.api_name,
                cadence="backfill",
                period_key=period_key,
                expected_for=partition.end_date,
                handler=TASKS.handler_metadata(task_name, parameters),
                max_attempts=HISTORICAL_MAX_ATTEMPTS,
                priority=_priority(partition.end_date, history_end),
                resource_class="backfill",
            )
        )
    return ReverseRecoveryPlan(tuple(specs), unsupported)


def build_reverse_fanout_scopes(
    *,
    api_names: Iterable[str],
    history_start: date,
    history_end: date,
    trade_dates: Iterable[date],
) -> tuple[ReverseFanoutScope, ...]:
    """Build bounded fan-out campaigns without materializing their leaves.

    The campaign reconciler freezes the universe and creates small pages.  We
    keep the scopes newest-first and allow the scheduler to advance only after
    the current scope reaches a verified terminal state.
    """
    if history_start > history_end:
        raise ValueError("history_start must not be later than history_end")
    dates = tuple(sorted(set(trade_dates)))
    scopes: list[ReverseFanoutScope] = []
    for api_name in sorted(set(api_names)):
        definition = FANOUT_DEFINITIONS.get(api_name)
        if definition is None:
            continue
        requests: list[tuple[dict[str, object], date, date]] = []
        if definition.scope == "none":
            requests.append(({}, history_start, history_end))
        elif definition.scope == "period":
            for year in range(history_start.year, history_end.year + 1):
                for month, day in ((3, 31), (6, 30), (9, 30), (12, 31)):
                    period = date(year, month, day)
                    if history_start <= period <= history_end:
                        requests.append(({"period": period}, period, period))
        elif definition.scope == "date_window" or definition.allow_date_window:
            for window_start, window_end in fixed_day_windows(
                history_start, history_end, days=definition.max_window_days
            ):
                requests.append((
                    {"start_date": window_start, "end_date": window_end},
                    window_start,
                    window_end,
                ))
        elif definition.scope in {"trade_date", "ann_date"}:
            for partition_date in dates:
                if history_start <= partition_date <= history_end:
                    requests.append((
                        {definition.scope: partition_date},
                        partition_date,
                        partition_date,
                    ))
        for request, scope_start, scope_end in requests:
            scopes.append(
                ReverseFanoutScope(
                    api_name=api_name,
                    request={"api_name": api_name, "page_size": 200, **request},
                    # api_name is already a typed campaign column; keeping the
                    # compact range here stays within VARCHAR(32).
                    period_key=f"rh:{scope_start:%Y%m%d}:{scope_end:%Y%m%d}",
                    expected_for=scope_end,
                )
            )
    scopes.sort(
        key=lambda item: (item.expected_for, item.api_name, item.period_key),
        reverse=True,
    )
    return tuple(scopes)
