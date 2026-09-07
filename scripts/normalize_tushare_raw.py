#!/usr/bin/env python3
"""Replay lossless raw Tushare records into their typed standard tables."""

from __future__ import annotations

import argparse
from collections import defaultdict
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import psycopg2.extras

from service.db import get_conn
from service.tushare_normalization import (
    NORMALIZATION_CONTRACTS,
    TushareNormalizer,
)


def replay(api_name: str, batch_size: int, normalizer: TushareNormalizer) -> dict:
    after_request = ""
    after_record = ""
    totals = {
        "api_name": api_name,
        "raw_rows": 0,
        "normalized_rows": 0,
        "quarantined_rows": 0,
        "unknown_fields": set(),
        "missing_fields": set(),
    }
    while True:
        connection = get_conn()
        try:
            with connection.cursor(
                cursor_factory=psycopg2.extras.RealDictCursor
            ) as cursor:
                cursor.execute(
                    """
                    SELECT request_hash, record_hash, payload, source_doc_id, collected_at
                    FROM tushare_raw_record
                    WHERE api_name=%s
                      AND (request_hash, record_hash) > (%s, %s)
                    ORDER BY request_hash, record_hash
                    LIMIT %s
                    """,
                    (api_name, after_request, after_record, batch_size),
                )
                rows = [dict(row) for row in cursor.fetchall()]
        finally:
            connection.close()
        if not rows:
            break

        groups: dict[str, list[dict]] = defaultdict(list)
        for row in rows:
            groups[row["request_hash"]].append(row)
        for request_hash, group in groups.items():
            result = normalizer.normalize(
                api_name,
                request_hash,
                [(row["record_hash"], row["payload"]) for row in group],
                source_doc_id=group[0]["source_doc_id"],
                collected_at=max(row["collected_at"] for row in group),
            )
            totals["raw_rows"] += result.raw_rows
            totals["normalized_rows"] += result.normalized_rows
            totals["quarantined_rows"] += result.quarantined_rows
            totals["unknown_fields"].update(result.unknown_fields)
            totals["missing_fields"].update(result.missing_fields)
        after_request = rows[-1]["request_hash"]
        after_record = rows[-1]["record_hash"]

    totals["unknown_fields"] = sorted(totals["unknown_fields"])
    totals["missing_fields"] = sorted(totals["missing_fields"])
    return totals


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api", action="append", default=[])
    parser.add_argument("--batch-size", type=int, default=1000)
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    if args.batch_size < 1 or args.batch_size > 5000:
        raise SystemExit("--batch-size must be between 1 and 5000")

    available = {contract.api_name for contract in NORMALIZATION_CONTRACTS.list()}
    selected = set(args.api) if args.api and "all" not in args.api else available
    unknown = selected - available
    if unknown:
        raise SystemExit("unknown generic interfaces: " + ", ".join(sorted(unknown)))

    normalizer = TushareNormalizer()
    results = []
    for api_name in sorted(selected):
        result = replay(api_name, args.batch_size, normalizer)
        results.append(result)
        print(json.dumps(result, ensure_ascii=False), flush=True)
    summary = {
        "interfaces": len(results),
        "raw_rows": sum(item["raw_rows"] for item in results),
        "normalized_rows": sum(item["normalized_rows"] for item in results),
        "quarantined_rows": sum(item["quarantined_rows"] for item in results),
    }
    print(json.dumps({"summary": summary}, ensure_ascii=False))
    if args.strict and summary["quarantined_rows"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
