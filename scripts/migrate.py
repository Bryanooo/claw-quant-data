#!/usr/bin/env python3
"""Apply ordered, checksum-protected PostgreSQL schema migrations."""

from __future__ import annotations

import hashlib
from pathlib import Path
import sys

SCRIPT_PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_PROJECT_ROOT))

import psycopg2

from service.config import DB_CONFIG, PROJECT_ROOT


MIGRATIONS_DIR = PROJECT_ROOT / "sql" / "migrations"
LOCK_ID = 1_924_202_608


def _checksum(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def migrate() -> list[str]:
    paths = sorted(MIGRATIONS_DIR.glob("[0-9][0-9][0-9]_*.sql"))
    if not paths:
        raise RuntimeError(f"no migrations found in {MIGRATIONS_DIR}")

    applied_now: list[str] = []
    connection = psycopg2.connect(**DB_CONFIG)
    try:
        connection.autocommit = True
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_lock(%s)", (LOCK_ID,))
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS sys_schema_migration (
                    version VARCHAR(255) PRIMARY KEY,
                    checksum CHAR(64) NOT NULL,
                    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )

        for path in paths:
            version = path.stem
            checksum = _checksum(path)
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT checksum FROM sys_schema_migration WHERE version = %s",
                    (version,),
                )
                row = cursor.fetchone()
            if row:
                if row[0].strip() != checksum:
                    raise RuntimeError(
                        f"migration {version} changed after it was applied; "
                        "create a new migration instead"
                    )
                continue

            connection.autocommit = False
            try:
                with connection.cursor() as cursor:
                    cursor.execute(path.read_text(encoding="utf-8"))
                    cursor.execute(
                        "INSERT INTO sys_schema_migration(version, checksum) VALUES (%s, %s)",
                        (version, checksum),
                    )
                connection.commit()
                applied_now.append(version)
            except Exception:
                connection.rollback()
                raise
            finally:
                connection.autocommit = True
    finally:
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_advisory_unlock(%s)", (LOCK_ID,))
        finally:
            connection.close()
    return applied_now


if __name__ == "__main__":
    applied = migrate()
    if applied:
        print("Applied migrations: " + ", ".join(applied))
    else:
        print("Schema is already current")
