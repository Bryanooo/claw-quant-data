#!/usr/bin/env python3
"""Backfill a reproducible, quota-bounded intraday validation window."""

from __future__ import annotations

import argparse
from datetime import date
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from service.data_service.database import Database
from service.intraday.collector import AntIntradayCollector
from service.intraday.repository import IntradayRepository
from service.intraday.service import IntradayObservationService


def _provider_batches(days: list[date]) -> list[list[date]]:
    """Pair only adjacent calendar days, respecting the P_Min1 contract."""

    batches: list[list[date]] = []
    index = 0
    while index < len(days):
        if index + 1 < len(days) and (days[index + 1] - days[index]).days == 1:
            batches.append(days[index:index + 2])
            index += 2
        else:
            batches.append([days[index]])
            index += 1
    return batches


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=30, choices=range(1, 401))
    parser.add_argument("--stocks", type=int, default=None, choices=range(0, 51), help="legacy alias for --random-stocks")
    parser.add_argument("--random-stocks", type=int, default=30, choices=range(0, 51))
    parser.add_argument("--seed", default="intraday-validation-v1")
    parser.add_argument("--force-refresh", action="store_true", help="refetch days that already pass the full validation contract")
    parser.add_argument("--call-interval-seconds", type=float, default=8.0, help="minimum spacing between provider outer calls")
    parser.add_argument("--replay-only", action="store_true", help="recompute from stored minute facts without provider calls")
    args = parser.parse_args()
    database = Database()
    try:
        repository = IntradayRepository(database)
        service = IntradayObservationService(repository)
        days = list(reversed(repository.recent_trade_days(before=date.today(), limit=args.days)))
        stock_count = args.stocks if args.stocks is not None else args.random_stocks
        watchlist = repository.random_stock_samples(
            limit=stock_count,
            seed=args.seed,
            listed_before=days[0],
        ) if stock_count else []
        collector = AntIntradayCollector(
            minimum_call_interval_seconds=max(0.0, args.call_interval_seconds),
        )
        if args.replay_only:
            reports = [
                service.replay_stored_day(day, watchlist=watchlist)
                for day in days
            ]
            provider_batches = 0
        else:
            complete_days = repository.complete_validation_days(
                days=days,
                watch_symbols={row["symbol"] for row in watchlist},
            ) if not args.force_refresh else set()
            pending_days = [day for day in days if day not in complete_days]
            groups = _provider_batches(pending_days)
            reports = [
                report
                for group in groups
                for report in service.backfill_days(
                    group, watchlist=watchlist, collector=collector,
                )
            ]
            provider_batches = len(groups)
        print(json.dumps({
            "days": reports,
            "stocks": [{"symbol": row["symbol"], "name": row["name"]} for row in watchlist],
            "seed": args.seed,
            "provider_batches": provider_batches,
            "skipped_complete_days": len(complete_days) if not args.replay_only else 0,
            "total_usage": collector.usage,
        }, ensure_ascii=False, indent=2))
    finally:
        database.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
