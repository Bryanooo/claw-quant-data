"""Targeted per-stock backfill for stk_factor day partitions missed by
offset pagination.

Background: the bulk day fetch (`trade_date=YYYYMMDD`, offset pagination)
reports N rows but tushare's snapshot for a day can contain duplicated
identities, so only ~4900/5570 distinct ts_codes land in the canonical table
while the traded universe (stock_daily) is larger.  A direct per-stock probe
returns the missing rows, so we re-collect only the missing ts_codes through
the same contract-driven collector (normalization + evidence included).

Usage (inside the api container):
    python scripts/backfill_stk_factor_missing.py --trade-date 20261022
"""

from __future__ import annotations

import argparse
import sys
import time

sys.path.insert(0, "/app")

from collectors.tushare_raw import CatalogRawCollector  # noqa: E402
from service.db import query  # noqa: E402


def _norm_table(api_name: str) -> str:
    from service.tushare_normalization import normalized_table_name

    return normalized_table_name(api_name)


def missing_codes(api_name: str, trade_date: str) -> list[str]:
    norm_table = _norm_table(api_name)
    rows = query(
        f"""
        SELECT d.ts_code
        FROM daily d
        LEFT JOIN {norm_table} f
               ON f.ts_code = d.ts_code AND f.trade_date = %s
        WHERE d.trade_date = %s AND f.ts_code IS NULL
        ORDER BY d.ts_code
        """,
        (f"{trade_date[:4]}-{trade_date[4:6]}-{trade_date[6:]}",) * 2,
    )
    return [r["ts_code"] for r in rows]


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
    if not rows:
        raise SystemExit(f"no checkpoint fields found for {api_name}")
    return rows[0]["fields"]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-name", default="stk_factor")
    parser.add_argument("--trade-date", required=True, help="YYYYMMDD")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    codes = missing_codes(args.api_name, args.trade_date)
    print(f"[backfill] {args.api_name} {args.trade_date}: {len(codes)} missing ts_codes")
    if not codes or args.dry_run:
        return

    fields = contract_fields(args.api_name)
    collector = CatalogRawCollector(args.api_name)
    stored = 0
    empty = 0
    failed: list[str] = []
    for index, code in enumerate(codes, start=1):
        frame = None
        for attempt in range(1, 5):
            try:
                frame = collector.fetch(ts_code=code, trade_date=args.trade_date, fields=fields)
                break
            except Exception as exc:  # transient provider/network errors
                if attempt == 4:
                    failed.append(code)
                    print(f"[backfill] {index}/{len(codes)} {code}: FAILED after {attempt} attempts: {exc}", flush=True)
                    frame = None
                    break
                time.sleep(min(30, 2 ** attempt * 3))
        if frame is None:
            continue
        if len(frame) == 0:
            empty += 1
            print(f"[backfill] {index}/{len(codes)} {code}: EMPTY at source")
            continue
        stored += collector.store(frame)
        if index % 50 == 0 or index == len(codes):
            print(f"[backfill] progress {index}/{len(codes)} stored={stored} empty={empty} failed={len(failed)}", flush=True)
    print(f"[backfill] done: stored={stored} empty_at_source={empty} failed={len(failed)}")
    if failed:
        print("[backfill] failed codes:", " ".join(failed))


if __name__ == "__main__":
    main()
