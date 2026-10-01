"""Shared, bounded history partitions for initialization and live recovery."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Collection, Iterator

from service.major_news import MAJOR_NEWS_SOURCES


CATALOG_WINDOW_HISTORY = {
    "gz_index": date(1990, 12, 19),
    "libor": date(1990, 12, 19),
    "shibor_lpr": date(2013, 10, 25),
    "stk_account": date(2015, 5, 29),
    "wz_index": date(2012, 12, 7),
}
CATALOG_MONTHLY_WINDOW_HISTORY = {
    "slb_len": date(2012, 1, 1),
    "slb_len_mm": date(2012, 1, 1),
    "slb_sec": date(2012, 1, 1),
    "slb_sec_detail": date(2012, 1, 1),
}

# Research-layer facts that were historically absent despite their interfaces
# being collectable. Full initialization treats these as durable history, not
# as an operator-run repair script. Analyst reports remain calendar-day scoped;
# news uses large source windows because its collector persists adaptive split
# checkpoints and can resume safely after the strict daily request quota.
RESEARCH_DAILY_WINDOW_HISTORY = {
    "report_rc": date(2010, 1, 1),
}
RESEARCH_MONTHLY_WINDOW_HISTORY = {
    "stk_holdertrade": date(2010, 1, 1),
    "stk_holdernumber": date(2010, 1, 1),
    "repurchase": date(2015, 1, 1),
}
RESEARCH_ONE_DAY_WINDOW_HISTORY = {
    # A single share_float date can exceed 20,000 rows.  Month windows can hit
    # the upstream hard offset ceiling of 100,000 and are therefore impossible
    # to prove complete even when pagination itself is working correctly.
    "share_float": date(2005, 1, 1),
}
RESEARCH_SEVEN_DAY_WINDOW_HISTORY = {
    # A whole month can exceed the upstream offset ceiling of 100,000 rows.
    # Seven calendar days keep every page sequence bounded while avoiding one
    # request job per natural day (weekends simply produce fewer rows).
    "hk_hold": date(2017, 3, 17),
}
RESEARCH_SOURCE_ADAPTIVE_WINDOW_HISTORY = {
    "major_news": (date(2018, 1, 1), MAJOR_NEWS_SOURCES),
}

# The live ``etf_share_size`` endpoint returns verified empty partitions before
# 2009 and populated SSE/SZSE observations from 2009-01-05 onward.  Keeping the
# boundary explicit prevents a full initialization from manufacturing years of
# meaningless empty jobs while still retaining the 2015 and 2024 state-support
# episodes needed to calibrate ETF-flow research.
ETF_SHARE_SIZE_HISTORY_START = date(2009, 1, 5)
# Verified provider-side history boundaries. These are not local retention
# dates: live probes returned authoritative empty results before the boundary
# and populated results on the boundary. Keeping them here aligns planning,
# repair and coverage semantics.
UPSTREAM_HISTORY_STARTS = {
    # Adjacent trading-day probes establish the first complete backup-market
    # cross-section; later isolated empty dates remain legitimate partitions.
    "bak_daily": date(2017, 6, 14),
    # Live probes: 2016-08-08 is empty and 2016-08-09 is the first populated
    # backup-basic snapshot. Later isolated empty days are provider behaviour,
    # not evidence that the interface existed before this boundary.
    "bak_basic": date(2016, 8, 9),
    # A bounded 1990-1996 request returns only 735 rows, so it is not capped;
    # its earliest convertible-bond daily record is 1993-02-10.
    "cb_daily": date(1993, 2, 10),
    # Exact probes remain empty through 2001-09-07 and return the first FX
    # cross-section on 2001-09-10.
    "fx_daily": date(2001, 9, 10),
    # Shanghai/Shenzhen-Hong Kong Stock Connect launched on 2014-11-17. Live
    # probes return empty on the preceding trading day and data on launch day.
    "ggt_top10": date(2014, 11, 17),
    # Exact-date probes return no CITIC industry bars through 2009-12-31 and
    # the complete cross-section on the first 2010 trading day.
    "ci_daily": date(2010, 1, 4),
    # The official contract states January 2004; exact probes confirm the
    # first 2004 trading day and an empty preceding calendar partition.
    "index_dailybasic": date(2004, 1, 2),
    # These three money-flow products are newer upstream datasets. Adjacent
    # trading-day probes establish the first non-empty partition boundaries.
    "moneyflow_cnt_ths": date(2024, 9, 10),
    "moneyflow_ind_dc": date(2023, 9, 12),
    "moneyflow_ths": date(2024, 12, 19),
    # Exact probes are empty through 1999-12-30 and populated on 2000-01-04.
    "sw_daily": date(2000, 1, 4),
    # Both the TDX index catalogue and daily endpoint first return data here.
    "tdx_index": date(2025, 3, 28),
    "tdx_daily": date(2025, 3, 28),
    "stk_limit": date(2007, 1, 4),
    "ths_daily": date(2020, 1, 1),
    "cn_pmi": date(2005, 1, 1),
    "sf_month": date(2002, 1, 1),
    "stock_st": date(2000, 1, 1),
    # Live provider probes return empty on 2023-08-18 and the first final
    # hot-list snapshot on 2023-08-21.  Planning older trading days would only
    # manufacture thousands of authoritative-empty calls.
    "ths_hot": date(2023, 8, 21),
}

# These high-cross-section APIs advertise start/end parameters, but live
# responses prove that range requests either require an exact date or reach a
# non-pageable 2k/4k/6k row cap.  Exact-date leaves are the smallest upstream
# completeness unit and must take precedence over the generic monthly recipe.
EXACT_TRADE_DATE_HISTORY_APIS = frozenset(
    {
        "bak_daily",
        "bak_basic",
        "cb_daily",
        "ci_daily",
        "daily_basic",
        # Although these contracts advertise start/end arguments, live
        # provider validation rejects market-wide range requests unless
        # ``trade_date`` (or ``ts_code``) is supplied.
        "fund_daily",
        "fund_nav",
        "fx_daily",
        "idx_factor_pro",
        # The provider accepts start/end fields in metadata but rejects a
        # market-wide recovery request built from those fields.  Exact
        # trade_date requests are proven pageable and are also the unit used
        # by the routine V2 task.
        "index_daily",
        "index_dailybasic",
        "index_monthly",
        "index_weekly",
        "moneyflow_cnt_ths",
        "moneyflow_ind_dc",
        "moneyflow_ths",
        "stk_factor",
        "stk_factor_pro",
        "stock_st",
        "suspend_d",
        "sw_daily",
        "ths_hot",
    }
)
THS_HOT_MARKETS = (
    "热股",
    "ETF",
    "可转债",
    "行业板块",
    "概念板块",
    "期货",
    "港股",
    "热基",
    "美股",
)
LIBOR_CURRENCIES = ("USD", "EUR", "JPY", "GBP", "CHF")

# Exact-date historical jobs prove that the upstream request scope is exhausted.
# Cross-sectional thresholds additionally detect staggered exchange publication,
# which is a live-data risk rather than a decades-old backfill risk. Initialization
# therefore applies the stricter entity audit to its newest rolling window while
# every older partition still has an individual transport-completeness step.
INITIALIZATION_STRICT_COVERAGE_LOOKBACK_DAYS = 120
# stock_basic cannot reconstruct the company universe represented by very old
# Tushare financial statements.  A verified empty report period is acceptable
# only outside this recent cross-sectional validation window.
FINANCIAL_ENTITY_REFERENCE_MAX_AGE_DAYS = 1825
INITIALIZATION_TRANSPORT_VERIFIED_DATASETS = frozenset(
    {
        "stock_daily",
        "stock_daily_basic",
        "moneyflow",
        "stock_limit",
        "index_daily",
    }
)


@dataclass(frozen=True, slots=True)
class HistoryPartition:
    api_name: str
    start_date: date
    end_date: date
    variant: str | None
    parameters: dict[str, str]

    @property
    def key(self) -> str:
        suffix = f":{self.variant}" if self.variant else ""
        return (
            f"{self.api_name}:{self.start_date:%Y%m%d}:"
            f"{self.end_date:%Y%m%d}{suffix}"
        )


def calendar_windows(
    start: date, end: date, *, monthly: bool
) -> Iterator[tuple[date, date]]:
    cursor = start
    while cursor <= end:
        if monthly:
            next_boundary = (
                date(cursor.year + 1, 1, 1)
                if cursor.month == 12
                else date(cursor.year, cursor.month + 1, 1)
            )
        else:
            next_boundary = date(cursor.year + 1, 1, 1)
        window_end = min(end, next_boundary - timedelta(days=1))
        yield cursor, window_end
        cursor = window_end + timedelta(days=1)


def fixed_day_windows(
    start: date, end: date, *, days: int
) -> Iterator[tuple[date, date]]:
    if days < 1:
        raise ValueError("days must be positive")
    cursor = start
    while cursor <= end:
        window_end = min(end, cursor + timedelta(days=days - 1))
        yield cursor, window_end
        cursor = window_end + timedelta(days=1)


def catalog_history_partitions(
    history_start: date, history_end: date
) -> Iterator[HistoryPartition]:
    recipes = (
        *((name, start, False) for name, start in CATALOG_WINDOW_HISTORY.items()),
        *((name, start, True) for name, start in CATALOG_MONTHLY_WINDOW_HISTORY.items()),
    )
    for api_name, reliable_start, monthly in recipes:
        start = max(history_start, reliable_start)
        if start > history_end:
            continue
        variants = LIBOR_CURRENCIES if api_name == "libor" else (None,)
        for window_start, window_end in calendar_windows(
            start, history_end, monthly=monthly
        ):
            for variant in variants:
                parameters = {
                    "start_date": window_start.strftime("%Y%m%d"),
                    "end_date": window_end.strftime("%Y%m%d"),
                }
                if variant:
                    parameters["curr_type"] = variant
                yield HistoryPartition(
                    api_name=api_name,
                    start_date=window_start,
                    end_date=window_end,
                    variant=variant,
                    parameters=parameters,
                )


def research_history_partitions(
    history_start: date, history_end: date
) -> Iterator[HistoryPartition]:
    recipes = (
        *((name, start, False) for name, start in RESEARCH_DAILY_WINDOW_HISTORY.items()),
        *((name, start, True) for name, start in RESEARCH_MONTHLY_WINDOW_HISTORY.items()),
    )
    for api_name, reliable_start, monthly in recipes:
        start = max(history_start, reliable_start)
        if start > history_end:
            continue
        windows = (
            calendar_windows(start, history_end, monthly=True)
            if monthly
            else (
                (start + timedelta(days=offset), start + timedelta(days=offset))
                for offset in range((history_end - start).days + 1)
            )
        )
        for window_start, window_end in windows:
            yield HistoryPartition(
                api_name=api_name,
                start_date=window_start,
                end_date=window_end,
                variant=None,
                parameters={
                    "start_date": window_start.strftime("%Y%m%d"),
                    "end_date": window_end.strftime("%Y%m%d"),
                },
            )
    for api_name, reliable_start in RESEARCH_SEVEN_DAY_WINDOW_HISTORY.items():
        start = max(history_start, reliable_start)
        if start > history_end:
            continue
        for window_start, window_end in fixed_day_windows(start, history_end, days=7):
            yield HistoryPartition(
                api_name=api_name,
                start_date=window_start,
                end_date=window_end,
                variant=None,
                parameters={
                    "start_date": window_start.strftime("%Y%m%d"),
                    "end_date": window_end.strftime("%Y%m%d"),
                },
            )
    for api_name, reliable_start in RESEARCH_ONE_DAY_WINDOW_HISTORY.items():
        start = max(history_start, reliable_start)
        if start > history_end:
            continue
        for window_start, window_end in fixed_day_windows(start, history_end, days=1):
            yield HistoryPartition(
                api_name=api_name,
                start_date=window_start,
                end_date=window_end,
                variant=None,
                parameters={
                    "start_date": window_start.strftime("%Y%m%d"),
                    "end_date": window_end.strftime("%Y%m%d"),
                },
            )
    for api_name, (reliable_start, variants) in (
        RESEARCH_SOURCE_ADAPTIVE_WINDOW_HISTORY.items()
    ):
        start = max(history_start, reliable_start)
        if start > history_end:
            continue
        for window_start, window_end in calendar_windows(
            start, history_end, monthly=False
        ):
            for variant in variants:
                yield HistoryPartition(
                    api_name=api_name,
                    start_date=window_start,
                    end_date=window_end,
                    variant=variant,
                    parameters={
                        "src": variant,
                        "start_date": window_start.strftime("%Y%m%d"),
                        "end_date": window_end.strftime("%Y%m%d"),
                    },
                )


def generic_policy_history_partitions(
    history_start: date,
    history_end: date,
    *,
    trade_dates: Collection[date],
    excluded_api_names: Collection[str] = (),
) -> Iterator[HistoryPartition]:
    """Build bounded history scopes for every safe catalog policy.

    This is deliberately derived from the machine-readable upstream contract
    rather than another hand-maintained endpoint list.  Broad daily market
    APIs that accept ranges are split by calendar month; low-volume range APIs
    use annual windows; month/report-period APIs use their natural partitions.
    Exact-date-only APIs use the locally persisted trading calendar.  Every
    emitted leaf is still required to exhaust pagination before it is accepted.

    Interfaces with dedicated recipes, strict low-frequency quotas or fan-out
    requirements are excluded by the caller and remain explicit obligations.
    """
    from service.tushare_catalog import TushareInterfaceCatalog
    from service.tushare_policy import TusharePolicyRegistry

    excluded = set(excluded_api_names)
    catalog = TushareInterfaceCatalog()
    policies = TusharePolicyRegistry()
    for contract in catalog.list():
        api_name = contract.api_name
        if not contract.collectable or api_name in excluded:
            continue
        policy = policies.get(api_name)
        if not policy.automatic_safe or policy.parameter_strategy == "snapshot":
            continue
        names = {item["name"] for item in contract.input_parameters}
        strategy = policy.parameter_strategy
        interface_start = max(
            history_start,
            UPSTREAM_HISTORY_STARTS.get(api_name, history_start),
        )
        if interface_start > history_end:
            continue

        if strategy == "trade_date":
            parameter_name = next(
                (
                    name
                    for name in (
                        "trade_date", "date", "cal_date", "ann_date",
                        "nav_date", "ex_date",
                    )
                    if name in names
                ),
                None,
            )
            if api_name in EXACT_TRADE_DATE_HISTORY_APIS and parameter_name:
                for partition_date in trade_dates:
                    if not interface_start <= partition_date <= history_end:
                        continue
                    variants = THS_HOT_MARKETS if api_name == "ths_hot" else (None,)
                    for variant in variants:
                        parameters = {
                            parameter_name: partition_date.strftime("%Y%m%d")
                        }
                        if variant:
                            # ``is_new=N`` contains every intraday snapshot.  A
                            # date/market request can therefore hit the hard
                            # 2,000-row ceiling even though the endpoint has no
                            # rank-time or offset cursor.  The provider's final
                            # 22:30 publication (Y) is the only complete,
                            # reproducible daily historical partition.
                            parameters.update({"market": variant, "is_new": "Y"})
                        yield HistoryPartition(
                            api_name=api_name,
                            start_date=partition_date,
                            end_date=partition_date,
                            # Version the identity so previously queued,
                            # incomplete intraday leaves cannot shadow final
                            # snapshot repairs through their idempotency key.
                            variant=(f"{variant}:final" if variant else None),
                            parameters=parameters,
                        )
                continue
            if {"start_date", "end_date"} <= names:
                for window_start, window_end in calendar_windows(
                    interface_start, history_end, monthly=True
                ):
                    yield HistoryPartition(
                        api_name=api_name,
                        start_date=window_start,
                        end_date=window_end,
                        variant=None,
                        parameters={
                            "start_date": window_start.strftime("%Y%m%d"),
                            "end_date": window_end.strftime("%Y%m%d"),
                        },
                    )
                continue
            if parameter_name:
                for partition_date in trade_dates:
                    if interface_start <= partition_date <= history_end:
                        yield HistoryPartition(
                            api_name=api_name,
                            start_date=partition_date,
                            end_date=partition_date,
                            variant=None,
                            parameters={
                                parameter_name: partition_date.strftime("%Y%m%d")
                            },
                        )
                continue

        if strategy == "date_window" and {"start_date", "end_date"} <= names:
            for window_start, window_end in calendar_windows(
                interface_start, history_end, monthly=False
            ):
                yield HistoryPartition(
                    api_name=api_name,
                    start_date=window_start,
                    end_date=window_end,
                    variant=None,
                    parameters={
                        "start_date": window_start.strftime("%Y%m%d"),
                        "end_date": window_end.strftime("%Y%m%d"),
                    },
                )
            continue

        if strategy == "month":
            for window_start, window_end in calendar_windows(
                interface_start, history_end, monthly=True
            ):
                month = window_start.strftime("%Y%m")
                if {"start_m", "end_m"} <= names:
                    parameters = {"start_m": month, "end_m": month}
                elif {"start_month", "end_month"} <= names:
                    parameters = {"start_month": month, "end_month": month}
                else:
                    parameter_name = next(
                        (name for name in ("month", "m") if name in names), None
                    )
                    if parameter_name is None:
                        continue
                    parameters = {parameter_name: month}
                yield HistoryPartition(
                    api_name=api_name,
                    start_date=window_start,
                    end_date=window_end,
                    variant=None,
                    parameters=parameters,
                )
            continue

        if strategy == "report_period":
            for year in range(interface_start.year, history_end.year + 1):
                for month, day in ((3, 31), (6, 30), (9, 30), (12, 31)):
                    period = date(year, month, day)
                    if not interface_start <= period <= history_end:
                        continue
                    parameter_name = next(
                        (
                            name for name in ("period", "report_date", "end_date")
                            if name in names
                        ),
                        None,
                    )
                    if parameter_name:
                        yield HistoryPartition(
                            api_name=api_name,
                            start_date=period,
                            end_date=period,
                            variant=None,
                            parameters={parameter_name: period.strftime("%Y%m%d")},
                        )
            continue

        if strategy == "week":
            cursor = interface_start - timedelta(days=interface_start.weekday())
            while cursor <= history_end:
                iso = cursor.isocalendar()
                week = f"{iso.year}{iso.week:02d}"
                if {"start_week", "end_week"} <= names:
                    parameters = {"start_week": week, "end_week": week}
                elif "week" in names:
                    parameters = {"week": week}
                else:
                    break
                window_start = max(cursor, interface_start)
                window_end = min(cursor + timedelta(days=6), history_end)
                yield HistoryPartition(
                    api_name=api_name,
                    start_date=window_start,
                    end_date=window_end,
                    variant=None,
                    parameters=parameters,
                )
                cursor += timedelta(days=7)
