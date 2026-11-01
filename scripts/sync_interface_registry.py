#!/usr/bin/env python3
"""Persist the compiled interface inventory into the control plane.

The compiler in :mod:`service.data_service.dependencies` stays the only writer;
this script mirrors its output so the interface list can be queried, diffed and
audited straight from the database.  Rows the compiler no longer emits are
removed, which turns a silent catalog drift into a visible deletion.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from service.data_service.dependencies import interface_inventory, interface_detail
from service.db import get_conn


def compiled_rows() -> list[dict]:
    rows: list[dict] = []
    for item in interface_inventory():
        # Persist the fully-resolved detail (list row + field parameters and
        # descriptions) so both the list and the detail console read from DB.
        detail = interface_detail(item["source"], item["key"]) or item
        rows.append({
            "source_id": item["source"],
            "interface_key": item["key"],
            "title": item.get("title"),
            "category": item.get("category"),
            "asset_class": item.get("asset_class"),
            "status": item.get("status") or "not_scheduled",
            "cadence": item.get("cadence"),
            "field_count": item.get("field_count"),
            "payload": json.dumps(detail, ensure_ascii=False, default=str),
        })
    return rows


def sync(*, apply: bool) -> dict:
    rows = compiled_rows()
    desired = {(row["source_id"], row["interface_key"]) for row in rows}
    with get_conn() as connection, connection.cursor() as cursor:
        cursor.execute(
            "SELECT source_id, interface_key FROM orchestration_v2.interface_registry"
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
            INSERT INTO orchestration_v2.interface_registry (
                source_id, interface_key, title, category, asset_class, status,
                cadence, field_count, payload, synced_at
            ) VALUES (
                %(source_id)s, %(interface_key)s, %(title)s, %(category)s,
                %(asset_class)s, %(status)s, %(cadence)s, %(field_count)s,
                %(payload)s::jsonb, NOW()
            )
            ON CONFLICT (source_id, interface_key)
            DO UPDATE SET
                title = EXCLUDED.title,
                category = EXCLUDED.category,
                asset_class = EXCLUDED.asset_class,
                status = EXCLUDED.status,
                cadence = EXCLUDED.cadence,
                field_count = EXCLUDED.field_count,
                payload = EXCLUDED.payload,
                synced_at = NOW()
            """,
            rows,
        )
        if stale:
            cursor.executemany(
                "DELETE FROM orchestration_v2.interface_registry "
                "WHERE source_id=%s AND interface_key=%s",
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
        print(f"interface registry sync failed: {error}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
