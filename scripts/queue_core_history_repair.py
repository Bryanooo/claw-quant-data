#!/usr/bin/env python3
"""Queue durable repairs for missing core A-share trading-day partitions."""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from service.collection_jobs.repository import JobRepository
from service.collection_jobs.registry import TASKS
from service.data_coverage.registry import SSE_TRADING_DAILY_DATASETS
from service.data_service.registry import DATASETS
from service.db import query


CORE_DATASETS = {
    "stock_daily": ("daily", "trade_date"),
    "stock_daily_basic": ("tushare_current_daily_basic", "trade_date"),
    "moneyflow": ("moneyflow", "trade_date"),
    "stock_limit": ("stk_limit", "trade_date"),
}


def incomplete_index_daily_dates(start: date, end: date) -> list[date]:
    """Find missing or implausibly small full-market index partitions."""
    rows = query(
        """
        WITH expected AS (
            SELECT calendar.cal_date,
                   (SELECT count(*) FROM index_basic AS reference
                    WHERE NULLIF(reference.list_date, '') IS NULL
                       OR to_date(reference.list_date, 'YYYYMMDD') <= calendar.cal_date
                   ) AS expected_entities
            FROM trade_cal AS calendar
            WHERE calendar.exchange='SSE' AND calendar.is_open=1
              AND calendar.cal_date BETWEEN %s AND %s
        ), actual AS (
            SELECT trade_date::date AS trade_date, count(DISTINCT ts_code) AS entities
            FROM index_daily
            WHERE trade_date::date BETWEEN %s AND %s
            GROUP BY trade_date::date
        )
        SELECT expected.cal_date
        FROM expected
        LEFT JOIN actual ON actual.trade_date=expected.cal_date
        WHERE actual.entities IS NULL
           OR (expected.expected_entities > 0
               AND actual.entities < expected.expected_entities * 0.90)
        ORDER BY expected.cal_date
        """,
        (start, end, start, end),
    )
    return [row["cal_date"] for row in rows]


def missing_dates(table: str, date_column: str, start: date, end: date) -> list[date]:
    # Identifiers come exclusively from CORE_DATASETS; command-line input can
    # never influence SQL identifiers.
    rows = query(
        f"""
        SELECT calendar.cal_date
        FROM trade_cal AS calendar
        WHERE calendar.exchange='SSE' AND calendar.is_open=1
          AND calendar.cal_date BETWEEN %s AND %s
          AND NOT EXISTS (
            SELECT 1 FROM {table} AS target
            WHERE target.{date_column}::date=calendar.cal_date
          )
        ORDER BY calendar.cal_date
        """,
        (start, end),
    )
    return [row["cal_date"] for row in rows]


def queue_repairs(start: date, end: date) -> dict[str, int]:
    repository = JobRepository()
    result: dict[str, int] = {}
    for task_name, (table, date_column) in CORE_DATASETS.items():
        created_count = 0
        for partition_date in missing_dates(table, date_column, start, end):
            parameters = {"trade_date": partition_date.strftime("%Y%m%d")}
            handler = TASKS.handler_metadata(task_name, parameters)
            _, created = repository.create(
                task_name,
                parameters,
                max_attempts=3,
                idempotency_key=(
                    f"core-history-repair-v2-{task_name}-{partition_date:%Y%m%d}"
                ),
                cadence="repair",
                period_key=partition_date.isoformat(),
                expected_for=partition_date,
                handler_type=handler.handler_type,
                handler_key=handler.handler_key,
                handler_version=handler.handler_version,
                code_revision=handler.code_revision,
                priority=30,
                resource_class="backfill",
            )
            created_count += int(created)
        result[task_name] = created_count
    created_count = 0
    for partition_date in incomplete_index_daily_dates(start, end):
        parameters = {
            "api_name": "index_daily",
            "parameters": {"trade_date": partition_date.strftime("%Y%m%d")},
            "complete": True,
            "page_size": 1000,
            "max_pages": 100,
            "resume": True,
        }
        handler = TASKS.handler_metadata("tushare_interface", parameters)
        _, created = repository.create(
            "tushare_interface",
            parameters,
            max_attempts=3,
            idempotency_key=(
                f"core-history-repair-v3-index_daily-{partition_date:%Y%m%d}"
            ),
            api_name="index_daily",
            cadence="repair",
            period_key=partition_date.isoformat(),
            expected_for=partition_date,
            handler_type=handler.handler_type,
            handler_key=handler.handler_key,
            handler_version=handler.handler_version,
            code_revision=handler.code_revision,
            priority=25,
            resource_class="backfill",
        )
        created_count += int(created)
    result["index_daily"] = created_count
    return result


def queue_audited_daily_repairs(start: date, end: date) -> dict[str, int]:
    """Queue the same proven SSE-daily partitions used by the coverage auditor."""
    repository = JobRepository()
    result: dict[str, int] = {}
    for api_name in SSE_TRADING_DAILY_DATASETS:
        dataset = DATASETS.get(api_name)
        created_count = 0
        for partition_date in missing_dates(
            dataset.table,
            dataset.date_column or "trade_date",
            start,
            end,
        ):
            parameters = {
                "api_name": api_name,
                "parameters": {"trade_date": partition_date.strftime("%Y%m%d")},
                "complete": True,
                "resume": True,
            }
            handler = TASKS.handler_metadata("tushare_interface", parameters)
            _, created = repository.create(
                "tushare_interface",
                parameters,
                max_attempts=3,
                idempotency_key=(
                    f"audited-history-repair-v1-{api_name}-{partition_date:%Y%m%d}"
                )[:128],
                api_name=api_name,
                cadence="repair",
                period_key=partition_date.isoformat(),
                expected_for=partition_date,
                handler_type=handler.handler_type,
                handler_key=handler.handler_key,
                handler_version=handler.handler_version,
                code_revision=handler.code_revision,
                priority=25,
                resource_class="backfill",
            )
            created_count += int(created)
        result[api_name] = created_count
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-date", required=True, type=date.fromisoformat)
    parser.add_argument("--end-date", required=True, type=date.fromisoformat)
    parser.add_argument(
        "--include-audited-daily",
        action="store_true",
        help="also repair every explicitly audited SSE-daily interface",
    )
    args = parser.parse_args()
    if args.start_date > args.end_date:
        parser.error("--start-date must not be later than --end-date")
    counts = queue_repairs(args.start_date, args.end_date)
    if args.include_audited_daily:
        counts.update(queue_audited_daily_repairs(args.start_date, args.end_date))
    for task_name, count in counts.items():
        print(f"{task_name}: queued {count}")
    print(f"total: queued {sum(counts.values())}")


if __name__ == "__main__":
    main()
