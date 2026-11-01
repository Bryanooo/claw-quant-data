"""Compact oversized ``sys_data_coverage_audit.evidence`` rows.

Audit evidence used to carry a per-day ``security_dates`` breakdown. For
``cyq_chips`` that is ~8.7k trading days and 15M missing-code entries per row,
so one audit row reached 54 MB and every partition/audit join had to re-detoast
it (see the ``MATERIALIZED audit_rev`` fix in ``orchestration_v2/gap_repair``).

``save_audit()`` now stores a rollup instead. This script rewrites the rows that
were written before that change, using the very same ``compact_audit_evidence``
function so historical and new rows share one shape.

The per-day detail of audited partitions is preserved in
``sys_data_coverage_partition.evidence``. Rows are dumped to a gzip backup
before being touched, so the original payload is always recoverable.

Usage::

    python scripts/compact_coverage_audit_evidence.py            # dry run
    python scripts/compact_coverage_audit_evidence.py --apply
    python scripts/compact_coverage_audit_evidence.py --apply --vacuum-full
"""

from __future__ import annotations

import argparse
import gzip
import json
import pathlib
import sys
from datetime import datetime, timezone

import psycopg2
import psycopg2.extras

from service.config import DB_CONFIG
from service.data_coverage.repository import compact_audit_evidence

DEFAULT_MIN_BYTES = 1_048_576
DEFAULT_BACKUP_DIR = pathlib.Path.home() / "data" / "claw-backups" / "coverage-audit-evidence"


def fetch_rows(cursor, min_bytes: int, audit_ids: list[int]) -> list[tuple]:
    if audit_ids:
        cursor.execute(
            """
            SELECT audit_id, dataset_name, evidence, pg_column_size(evidence)
            FROM sys_data_coverage_audit
            WHERE audit_id = ANY(%s)
            ORDER BY audit_id
            """,
            (audit_ids,),
        )
    else:
        cursor.execute(
            """
            SELECT audit_id, dataset_name, evidence, pg_column_size(evidence)
            FROM sys_data_coverage_audit
            WHERE pg_column_size(evidence) >= %s
              AND NOT (evidence ? 'security_dates_summary')
            ORDER BY pg_column_size(evidence) DESC
            """,
            (min_bytes,),
        )
    return cursor.fetchall()


def write_backup(rows: list[dict], backup_dir: pathlib.Path) -> pathlib.Path:
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = backup_dir / f"coverage-audit-evidence-{stamp}.jsonl.gz"
    expected = 0
    written = 0
    with gzip.open(path, "wt", encoding="utf-8") as handle:
        for row in rows:
            payload = json.dumps(
                {
                    "audit_id": row["audit_id"],
                    "dataset_name": row["dataset_name"],
                    "pg_column_size": row["pg_column_size"],
                    "evidence": row["evidence"],
                },
                ensure_ascii=False,
            )
            handle.write(payload)
            handle.write("\n")
            written += len(payload)
            expected += row["pg_column_size"]
    # A row is a dict-like cursor record; unpacking it yields column *names*, so
    # guard against a silently empty backup before the rows get overwritten.
    if written < expected * 0.5:
        raise RuntimeError(
            f"backup looks truncated: {written} bytes serialized for {expected} bytes of evidence"
        )
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="write the compacted rows")
    parser.add_argument("--audit-id", type=int, action="append", default=[], help="limit to specific audit ids")
    parser.add_argument("--min-bytes", type=int, default=DEFAULT_MIN_BYTES, help="only rewrite rows at least this big")
    parser.add_argument("--backup-dir", type=pathlib.Path, default=DEFAULT_BACKUP_DIR)
    parser.add_argument("--vacuum-full", action="store_true", help="VACUUM FULL the audit table afterwards")
    args = parser.parse_args(argv)

    connection = psycopg2.connect(**DB_CONFIG)
    connection.autocommit = False
    with connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
        rows = fetch_rows(cursor, args.min_bytes, args.audit_id)

    if not rows:
        print("nothing to compact")
        connection.close()
        return 0

    total_before = sum(row["pg_column_size"] for row in rows)
    print(f"{len(rows)} row(s), {total_before / 1048576:.1f} MB of evidence")

    compacted: list[tuple] = []
    for row in rows:
        before = row["evidence"]
        after = compact_audit_evidence(before)
        summary = after.get("security_dates_summary", {})
        print(
            f"  audit {row['audit_id']} {row['dataset_name']}: "
            f"{row['pg_column_size'] / 1048576:.1f} MB -> "
            f"{len(json.dumps(after, ensure_ascii=False).encode()) / 1024:.0f} KB "
            f"(days={summary.get('audited_days')} missing_days={summary.get('missing_days')} "
            f"missing_rows={summary.get('missing_security_rows')})"
        )
        compacted.append((row["audit_id"], after))

    if not args.apply:
        print("dry run; pass --apply to rewrite")
        connection.close()
        return 0

    backup_path = write_backup(rows, args.backup_dir)
    print(f"backup: {backup_path}")

    with connection, connection.cursor() as cursor:
        for audit_id, evidence in compacted:
            cursor.execute(
                "UPDATE sys_data_coverage_audit SET evidence = %s WHERE audit_id = %s",
                (psycopg2.extras.Json(evidence), audit_id),
            )
    print(f"updated {len(compacted)} row(s)")

    if args.vacuum_full:
        connection.autocommit = True
        with connection.cursor() as cursor:
            cursor.execute("VACUUM (FULL, ANALYZE) sys_data_coverage_audit")
        print("vacuum full done")

    connection.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
