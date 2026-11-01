#!/usr/bin/env python3
"""Backfill local factors for a trading-date range with safe resume."""

from __future__ import annotations

import argparse
from datetime import date
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from service.research.local_factors.batch import (
    enqueue_factor_batch,
    materialize_factor_batch,
    trading_dates,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", type=date.fromisoformat, required=True)
    parser.add_argument("--end", type=date.fromisoformat, required=True)
    parser.add_argument("--workers", type=int, default=1, choices=range(1, 5))
    parser.add_argument("--force", action="store_true")
    parser.add_argument(
        "--direct",
        action="store_true",
        help=(
            "development-only direct materialization; default queues V2 "
            "executions that also audit and publish dataset state"
        ),
    )
    args = parser.parse_args()
    dates = trading_dates(args.start, args.end)
    def emit(event):
        print(json.dumps(event, ensure_ascii=False, default=str), flush=True)

    if args.direct:
        result = materialize_factor_batch(
            dates, workers=args.workers, force=args.force, progress=emit,
        )
    else:
        if args.force:
            parser.error("--force is only valid with --direct")
        result = enqueue_factor_batch(dates)
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 1 if result.get("failed_dates") or result.get("partial_dates") else 0


if __name__ == "__main__":
    raise SystemExit(main())
