#!/usr/bin/env python3
"""Persist the compiled field-level lineage into the control plane.

The compiler in :mod:`service.data_service.dependencies` stays the only
writer; this script mirrors its output so the mapping can be queried and
diffed.  Rows that the compiler no longer emits are removed, which is what
turns a silent schema drift into a visible deletion.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from service.data_service.dependencies import field_lineage
from service.db import get_conn


def compiled_rows() -> list[tuple]:
    rows: list[tuple] = []
    for table in field_lineage():
        for field in table.get("fields") or []:
            interfaces = field.get("from_interfaces") or table.get("interfaces") or []
            for interface_key in interfaces:
                rows.append((
                    table.get("source") or "tushare",
                    table["table"],
                    field["name"],
                    interface_key,
                    field.get("type"),
                    field.get("description"),
                ))
    return rows


def sync(*, apply: bool) -> dict:
    rows = compiled_rows()
    desired = {(row[0], row[1], row[2], row[3]) for row in rows}
    with get_conn() as connection, connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT source_id, table_name, field_name, interface_key
            FROM orchestration_v2.field_lineage
            """
        )
        existing = {tuple(item) for item in cursor.fetchall()}
        stale = sorted(existing - desired)
        added = sorted(desired - existing)
        result = {
            "compiled": len(rows),
            "existing": len(existing),
            "added": len(added),
            "removed": len(stale),
            "applied": apply,
        }
        if not apply:
            return result
        cursor.executemany(
            """
            INSERT INTO orchestration_v2.field_lineage (
                source_id, table_name, field_name, interface_key,
                field_type, description, synced_at
            ) VALUES (%s, %s, %s, %s, %s, %s, NOW())
            ON CONFLICT (source_id, table_name, field_name, interface_key)
            DO UPDATE SET field_type = EXCLUDED.field_type,
                          description = EXCLUDED.description,
                          synced_at = NOW()
            """,
            rows,
        )
        if stale:
            cursor.executemany(
                """
                DELETE FROM orchestration_v2.field_lineage
                WHERE source_id=%s AND table_name=%s
                  AND field_name=%s AND interface_key=%s
                """,
                stale,
            )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true",
                        help="write changes; without it the run is a dry run")
    arguments = parser.parse_args()
    try:
        print(sync(apply=arguments.apply))
    except Exception as error:  # pragma: no cover - operational guard
        print(f"field lineage sync failed: {error}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
