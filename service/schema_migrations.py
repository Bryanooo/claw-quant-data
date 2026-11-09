"""Schema expectations shared by the migration runner and health probes."""

from functools import cache
from pathlib import Path

from psycopg2.errors import UndefinedTable

from service.config import PROJECT_ROOT

MIGRATIONS_DIR = PROJECT_ROOT / "sql" / "migrations"
CHECKSUM_MANIFEST = MIGRATIONS_DIR / "checksums.sha256"


def load_checksum_manifest(path: Path = CHECKSUM_MANIFEST) -> dict[str, str]:
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


@cache
def required_migrations() -> frozenset[str]:
    versions = frozenset(Path(name).stem for name in load_checksum_manifest())
    if not versions:
        raise RuntimeError("empty migration manifest")
    return versions


def missing_migrations(fetch_all) -> list[str]:
    expected = required_migrations()
    try:
        rows = fetch_all("SELECT version FROM public.sys_schema_migration")
    except UndefinedTable:
        return sorted(expected)
    return sorted(expected.difference(row["version"] for row in rows))
