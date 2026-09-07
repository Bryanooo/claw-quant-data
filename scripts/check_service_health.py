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
    args = parser.parse_args()

    threshold = int(os.getenv("SERVICE_HEARTBEAT_MAX_AGE_SECONDS", "90"))
    rows = query(
        """
        SELECT EXTRACT(EPOCH FROM (NOW() - MAX(last_seen_at))) AS age_seconds
        FROM sys_service_heartbeat
        WHERE component = %s
        """,
        (args.component,),
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
