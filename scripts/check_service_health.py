#!/usr/bin/env python3
"""Container health probe for long-running non-HTTP services."""

import argparse
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from service.db import query


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--component",
        choices=(
            "scheduler", "worker", "worker-fanout", "worker-backfill", "auditor"
        ),
        required=True,
    )
    parser.add_argument("--resource-class")
    args = parser.parse_args()

    threshold = int(os.getenv("SERVICE_HEARTBEAT_MAX_AGE_SECONDS", "90"))
    resource_filter = (
        "AND details->'resource_classes' ? %s" if args.resource_class else ""
    )
    parameters = (
        (args.component, args.resource_class)
        if args.resource_class
        else (args.component,)
    )
    rows = query(
        f"""
        SELECT EXTRACT(EPOCH FROM (NOW() - MAX(last_seen_at))) AS age_seconds
        FROM sys_service_heartbeat
        WHERE component = %s
        {resource_filter}
        """,
        parameters,
    )
    age = rows[0]["age_seconds"] if rows else None
    if age is None or float(age) > threshold:
        raise RuntimeError(
            f"{args.component}: heartbeat missing or stale "
            f"(age={age}, threshold={threshold}s)"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
