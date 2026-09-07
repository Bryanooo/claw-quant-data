#!/usr/bin/env python3
"""Queue resumable history baselines without changing the daily run mode."""

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
from service.db import query
from service.history_baselines import catalog_history_partitions


REPAIR_PREFIX = "catalog-history-repair-v1-"


def queue_repairs(start: date, end: date) -> dict[str, int]:
    repository = JobRepository()
    counts: dict[str, int] = {}
    for partition in catalog_history_partitions(start, end):
        parameters = {
            "api_name": partition.api_name,
            "parameters": partition.parameters,
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
            idempotency_key=f"{REPAIR_PREFIX}{partition.key}"[:128],
            api_name=partition.api_name,
            cadence="repair",
            period_key=partition.key,
            expected_for=partition.end_date,
            handler_type=handler.handler_type,
            handler_key=handler.handler_key,
            handler_version=handler.handler_version,
            code_revision=handler.code_revision,
            priority=20,
            resource_class="backfill",
        )
        counts[partition.api_name] = counts.get(partition.api_name, 0) + int(created)
    return counts


def audit_repairs(start: date, end: date) -> dict[str, object]:
    """Prove that every expected repair partition finished with evidence."""
    expected = {partition.key for partition in catalog_history_partitions(start, end)}
    rows = query(
        """
        SELECT period_key, status, completion_status, completion_evidence
        FROM sys_collection_job
        WHERE idempotency_key LIKE %s
        """,
        (f"{REPAIR_PREFIX}%",),
    )
    observed = {row["period_key"]: row for row in rows if row["period_key"] in expected}
    missing = sorted(expected - observed.keys())
    active = sorted(
        key for key, row in observed.items()
        if row["status"] in {"queued", "running", "retrying"}
    )
    failed = sorted(
        key for key, row in observed.items() if row["status"] == "failed"
    )
    unverified = sorted(
        key for key, row in observed.items()
        if row["status"] == "success"
        and (
            row["completion_status"] not in {"complete", "empty"}
            or not (row.get("completion_evidence") or {}).get("verified", False)
        )
    )
    return {
        "expected": len(expected),
        "observed": len(observed),
        "missing": missing,
        "active": active,
        "failed": failed,
        "unverified": unverified,
        "complete": not (missing or active or failed or unverified),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-date", required=True, type=date.fromisoformat)
    parser.add_argument("--end-date", required=True, type=date.fromisoformat)
    parser.add_argument(
        "--audit-only",
        action="store_true",
        help="verify all expected repair partitions without creating jobs",
    )
    args = parser.parse_args()
    if args.start_date > args.end_date:
        parser.error("--start-date must not be later than --end-date")
    if args.audit_only:
        result = audit_repairs(args.start_date, args.end_date)
        print(
            f"expected={result['expected']} observed={result['observed']} "
            f"missing={len(result['missing'])} active={len(result['active'])} "
            f"failed={len(result['failed'])} unverified={len(result['unverified'])}"
        )
        for field in ("missing", "active", "failed", "unverified"):
            if result[field]:
                print(f"{field}: {', '.join(result[field][:20])}")
        return 0 if result["complete"] else 1
    counts = queue_repairs(args.start_date, args.end_date)
    for api_name, count in counts.items():
        print(f"{api_name}: queued {count}")
    print(f"total: queued {sum(counts.values())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
