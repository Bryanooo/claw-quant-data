from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_backup_is_atomic_checksummed_and_excludes_rebuildable_raw_payloads():
    script = (ROOT / "scripts/backup.sh").read_text()

    assert ".partial" in script
    assert "pg_restore --list" in script
    assert "shasum -a 256" in script
    assert "tushare_raw_record" in script


def test_restore_requires_current_v2_schema_and_nonempty_core_evidence():
    script = (ROOT / "scripts/restore.sh").read_text()

    assert "079_normalize_v2_verified_empty_states" in script
    assert 'table_schema=\'orchestration_v2\'' in script
    assert "EXISTS (SELECT 1 FROM daily)" in script
    assert "EXISTS (SELECT 1 FROM orchestration_v2.task_execution_event)" in script
    assert 'table_name IN (\n     \'sys_collection_job\'' in script
