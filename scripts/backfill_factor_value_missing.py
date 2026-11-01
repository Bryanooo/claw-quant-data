"""Backfill missing (trade_date, factor_name) cells for the factor_value dataset.

The factor_value fan-out universe is discovered from distinct factor names
already stored in ``tushare_norm_factor_value`` (see
``service.acquisition_runtime.fanout``). Tushare declares 101 Alpha101 factors,
while its expanded HTML table currently renders only 31 selected rows. This
script uses the same reviewed 272-factor target as V2 and seeds all numbered
Alpha101 members; actual provider responses remain the completion evidence.

1. Validate the 171 discovered non-Alpha factors and seed the declared
   Alpha101 identifiers 1..101, yielding a 272-factor governed target.
2. Target dates are the trading days inside the stored coverage window, taken
   from the ``daily`` table (so fully missing trading days are included).
3. For every missing (trade_date, factor_name) cell, fetch the full universe
   for that factor/day through the governed contract pipeline
   (``CatalogRawCollector``: raw layer + typed normalization + audit trail).
4. The script is idempotent: existing cells are skipped, so it can be rerun
   on consecutive quota days until the gap is closed.

Provider quota (verified 2026-10-22): factor_value allows exactly 1,000 calls
per Shanghai calendar day.  The script therefore stops after ``--max-calls``
requests (default 950, headroom for operator probes) or when the provider
returns its daily-quota error, whichever comes first.
"""

from __future__ import annotations

import argparse
import re
import sys
import time

sys.path.insert(0, ".")

from collectors.tushare_raw import CatalogRawCollector  # noqa: E402
from service.acquisition_runtime.factor_value_contract import (  # noqa: E402
    governed_factor_names,
)
from service.db import query  # noqa: E402
from service.tushare_rate_limit import TushareRateSlotDeferredError  # noqa: E402

QUOTA_ERROR_PATTERN = re.compile(r"频率超限|频率限制|每天最多|访问接口.*超限")
API_NAME = "factor_value"


def contract_fields(api_name: str) -> str:
    rows = query(
        """
        SELECT base_params ->> 'fields' AS fields
        FROM sys_tushare_collection_checkpoint
        WHERE api_name = %s AND base_params ->> 'fields' IS NOT NULL
        ORDER BY updated_at DESC
        LIMIT 1
        """,
        (api_name,),
    )
    if rows:
        return rows[0]["fields"]
    # factor_value daily tasks do not record checkpoints; fall back to the
    # documented contract output fields (docs/tushare/contracts.json doc 490).
    return "factor_name,ts_code,trade_date,factor_value"


def stored_names() -> set[str]:
    rows = query(
        "SELECT DISTINCT factor_name FROM tushare_norm_factor_value "
        "WHERE factor_name IS NOT NULL AND factor_name<>''",
        as_dict=True,
    )
    return {str(r["factor_name"]) for r in rows}


def target_dates() -> list[str]:
    """Trading days (YYYYMMDD) spanning the stored coverage window."""
    rows = query(
        """
        SELECT DISTINCT to_char(d.trade_date, 'YYYYMMDD') AS d
        FROM daily d
        WHERE d.trade_date >= (SELECT min(trade_date) FROM tushare_norm_factor_value)
          AND d.trade_date <= (SELECT max(trade_date) FROM tushare_norm_factor_value)
        ORDER BY 1
        """,
        as_dict=True,
    )
    return [str(r["d"]) for r in rows]


def existing_cells() -> set[tuple[str, str]]:
    rows = query(
        "SELECT DISTINCT to_char(trade_date, 'YYYYMMDD') AS d, factor_name "
        "FROM tushare_norm_factor_value WHERE factor_name IS NOT NULL AND factor_name<>''",
        as_dict=True,
    )
    return {(str(r["d"]), str(r["factor_name"])) for r in rows}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-calls", type=int, default=650)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    names = governed_factor_names(stored_names())
    dates = target_dates()
    done = existing_cells()
    cells = [
        (d, f)
        for d in dates
        for f in names
        if (d, f) not in done
    ]
    print(f"[backfill] universe: {len(names)} factors x {len(dates)} trading days; "
          f"existing cells: {len(done)}; missing cells: {len(cells)}")

    if args.dry_run:
        per_date: dict[str, int] = {}
        for d, _f in cells:
            per_date[d] = per_date.get(d, 0) + 1
        for d in sorted(per_date):
            print(f"  {d}: {per_date[d]} missing factors")
        return
    if not cells:
        print("[backfill] nothing to do")
        return

    fields = contract_fields(API_NAME)
    collector = CatalogRawCollector(API_NAME)
    stored = empty = 0
    for index, (trade_date, factor_name) in enumerate(cells, start=1):
        if index > args.max_calls:
            print(f"[backfill] reached --max-calls={args.max_calls}; "
                  f"{len(cells) - args.max_calls} cells left for the next quota day",
                  flush=True)
            break
        frame = None
        for attempt in range(1, 4):
            try:
                frame = collector.fetch(
                    factor_name=factor_name, trade_date=trade_date, fields=fields
                )
                break
            except TushareRateSlotDeferredError as exc:
                print(f"[backfill] shared daily quota exhausted at call {index}: "
                      f"slot reopens in {exc.retry_after_seconds}s; "
                      f"{len(cells) - index + 1} cells left, rerun later/next day",
                      flush=True)
                print(f"[backfill] done: stored={stored} empty_at_source={empty}")
                return
            except Exception as exc:  # network hiccup or provider quota wall
                if QUOTA_ERROR_PATTERN.search(str(exc)):
                    print(f"[backfill] DAILY QUOTA reached at call {index} "
                          f"({len(cells) - index + 1} cells left); rerun tomorrow",
                          flush=True)
                    print(f"[backfill] done: stored={stored} empty_at_source={empty}")
                    return
                if attempt == 3:
                    raise
                time.sleep(2 * attempt)
        if frame is None or len(frame) == 0:
            empty += 1
            print(f"[backfill] {index}/{len(cells)} {factor_name}@{trade_date}: EMPTY at source",
                  flush=True)
            continue
        stored += collector.store(frame)
        if index % 25 == 0 or index == len(cells):
            print(f"[backfill] progress {index}/{len(cells)} stored_rows={stored} "
                  f"empty={empty}", flush=True)
        time.sleep(0.15)
    print(f"[backfill] done: stored={stored} empty_at_source={empty}")


if __name__ == "__main__":
    main()
