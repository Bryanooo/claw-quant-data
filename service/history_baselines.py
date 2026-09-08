"""Shared, bounded history partitions for initialization and live recovery."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Iterator


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
