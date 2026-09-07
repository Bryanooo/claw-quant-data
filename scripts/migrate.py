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
CHECKSUM_MANIFEST = MIGRATIONS_DIR / "checksums.sha256"
LOCK_ID = 1_924_202_608

# Release f149831 normalized trailing whitespace in five already-applied
# migrations.  The SQL statements did not change, but byte-level checksums did.
# Keep the original migration bytes in the repository and accept only these
# exact, known formatting-only hashes for installations created by that brief
# release.  Any other mutation remains a hard failure.
FORMAT_ONLY_CHECKSUM_ALIASES = {
    "003_tushare_raw_record": {
        "458fd9dba6a20ad6d5777bdad8e1893cc46aaa0fd7221508671926777f6ed2a7":
            "b834ff2906036a55ea71bbae02ff28be634380a5ab4d177ac8effd8c8aa37985",
    },
    "004_tushare_collection_checkpoint": {
        "d9b81d58d7e6c5d7f56be6ff065c2411530a2722978ac24d78b681ae21c524a2":
            "4cb5220c639d189e5d7889172478fbee9076cb48d43a4ae99922be2e779bd899",
    },
    "016_collection_job_priority": {
        "4b42d0eb50e19b0673506948f9aad130a91c1d5e0ea5b82e75e86e6f38165cf1":
            "a1a96cc949665809c786632ff3716335330e03dc487998cb45b84ba768d99b3a",
    },
    "017_collection_job_batches": {
        "5e427d0b67e7b83138172be87043ded3a734da0bf58dbd1bfa35b4cc3e5d1b4e":
            "fcc2a99ff111e6527c9110e43442a63b6b1a73b15f047b44fdaffe69fb6593c6",
    },
    "024_specialized_job_handler": {
        "f1820901ad5e93b9f46e9f9151624549222f8761617ebb9178c5a081b74a3831":
            "f5af597f1461914817865da87b1dd3a05489040a315d27a43c123a5cb42c4931",
    },
}


def _checksum(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _checksum_is_compatible(version: str, stored: str, current: str) -> bool:
    if stored == current:
        return True
    compatible_current = FORMAT_ONLY_CHECKSUM_ALIASES.get(version, {}).get(stored)
    return compatible_current == current


def _load_checksum_manifest(path: Path = CHECKSUM_MANIFEST) -> dict[str, str]:
    entries: dict[str, str] = {}
    for line_number, raw_line in enumerate(
        path.read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) != 2 or len(parts[0]) != 64:
            raise RuntimeError(
                f"invalid migration checksum manifest line {line_number}"
            )
        checksum, filename = parts
        if filename in entries:
            raise RuntimeError(f"duplicate migration checksum entry: {filename}")
        entries[filename] = checksum
    return entries


def _validate_migration_files(paths: list[Path]) -> None:
    expected = _load_checksum_manifest()
    actual_names = {path.name for path in paths}
    expected_names = set(expected)
    if actual_names != expected_names:
        missing = sorted(expected_names - actual_names)
        unregistered = sorted(actual_names - expected_names)
        raise RuntimeError(
            "migration checksum manifest mismatch; "
            f"missing={missing}, unregistered={unregistered}"
        )
    changed = [
        path.name
        for path in paths
        if _checksum(path) != expected[path.name]
    ]
    if changed:
        raise RuntimeError(
            "published migration files changed: " + ", ".join(changed)
        )


def migrate() -> list[str]:
    paths = sorted(MIGRATIONS_DIR.glob("[0-9][0-9][0-9]_*.sql"))
    if not paths:
        raise RuntimeError(f"no migrations found in {MIGRATIONS_DIR}")
    _validate_migration_files(paths)

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
                stored_checksum = row[0].strip()
                if not _checksum_is_compatible(version, stored_checksum, checksum):
                    raise RuntimeError(
                        f"migration {version} changed after it was applied; "
                        "create a new migration instead"
                    )
                if stored_checksum != checksum:
                    print(
                        f"Accepted known formatting-only checksum for {version}",
                        file=sys.stderr,
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
