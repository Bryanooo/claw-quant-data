from scripts.migrate import (
    FORMAT_ONLY_CHECKSUM_ALIASES,
    _checksum_is_compatible,
    _load_checksum_manifest,
    _validate_migration_files,
)
from service.config import PROJECT_ROOT


def test_migration_checksum_accepts_current_hash():
    assert _checksum_is_compatible("001_reliability", "same", "same") is True


def test_migration_checksum_accepts_only_explicit_formatting_aliases():
    version = "003_tushare_raw_record"
    known_alias = next(iter(FORMAT_ONLY_CHECKSUM_ALIASES[version]))
    canonical = FORMAT_ONLY_CHECKSUM_ALIASES[version][known_alias]

    assert _checksum_is_compatible(version, known_alias, canonical) is True
    assert _checksum_is_compatible(version, known_alias, "modified") is False
    assert _checksum_is_compatible(version, "unknown", canonical) is False
    assert _checksum_is_compatible("999_unknown", known_alias, canonical) is False


def test_published_migration_files_match_immutable_manifest():
    migration_directory = PROJECT_ROOT / "sql" / "migrations"
    paths = sorted(migration_directory.glob("[0-9][0-9][0-9]_*.sql"))

    _validate_migration_files(paths)

    assert len(_load_checksum_manifest()) == len(paths) == 42
