import os
import hashlib
import shlex
import shutil
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]


def run_loop(tmp_path, *, fail_dump=False, low_space=False, corrupt_latest=False, prune_only=False):
    backups = tmp_path / "backups"
    backups.mkdir()
    binaries = tmp_path / "bin"
    binaries.mkdir()
    for number in range(3):
        path = backups / f"claw-quant-2000010{number + 1}-000000.dump"
        path.write_text("previous archive")
        path.with_suffix(".dump.sha256").write_text(hashlib.sha256(path.read_bytes()).hexdigest() + "  " + path.name + "\n")
    if corrupt_latest:
        (backups / "claw-quant-20000103-000000.dump.sha256").write_text("invalid checksum")
    (backups / ".last-success").write_text("0")

    checksum_tool = shutil.which("shasum") or shutil.which("sha256sum")
    assert checksum_tool, "SHA-256 verification tool required"
    checksum_command = "exec " + shlex.quote(checksum_tool)
    if Path(checksum_tool).name == "shasum":
        checksum_command += " -a 256"

    commands = {
        "df": "printf 'Filesystem Blocks Used Available Capacity Mounted\\nfs 999999999 1 "
        + ("1" if low_space else "999999998") + " 1%% /\\n'",
        "pg_restore": "exit 0",
        "psql": "exit 0",
        "sha256sum": checksum_command + ' "$@"',
        "sleep": 'if [ "$1" = 30 ]; then /bin/sleep 0.02; else exit 73; fi',
        "pg_dump": 'for arg in "$@"; do case "$arg" in --file=*) file="${arg#--file=}" ;; esac; done\n'
        'printf "new archive" > "$file"\n' + ("exit 1" if fail_dump else "exit 0"),
    }
    for name, body in commands.items():
        path = binaries / name
        path.write_text("#!/bin/sh\n" + body + "\n")
        path.chmod(0o755)
    result = subprocess.run(
        ["sh", str(ROOT / "scripts/backup_loop.sh"), *(["--prune-only"] if prune_only else [])],
        env={**os.environ, "PATH": str(binaries) + ":" + os.environ["PATH"],
             "BACKUP_DIR": str(backups), "PGDATABASE": "test",
             "BACKUP_FREE_RESERVE_KIB": "5"},
        capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == (0 if prune_only else 73), result.stderr
    return backups, result


def test_failed_backup_preserves_all_completed_archives(tmp_path):
    backups, result = run_loop(tmp_path, fail_dump=True)
    assert len(list(backups.glob("*.dump"))) == 3
    assert (backups / ".last-success").read_text() == "0"
    assert not list(backups.glob("*.partial"))
    assert "backup failed" in result.stderr


def test_success_keeps_two_completed_archives_and_a_checksummed_new_snapshot(tmp_path):
    backups, result = run_loop(tmp_path)
    archives = sorted(backups.glob("*.dump"))
    assert len(archives) == 2
    assert archives[0].name == "claw-quant-20000103-000000.dump"
    assert archives[1].read_text() == "new archive"
    assert archives[1].name in archives[1].with_suffix(".dump.sha256").read_text()
    assert int((backups / ".last-success").read_text()) > 0
    assert not list(backups.glob("*.partial"))
    assert "backup completed" in result.stdout


def test_insufficient_space_preserves_existing_snapshots(tmp_path):
    backups, result = run_loop(tmp_path, low_space=True)
    assert len(list(backups.glob("*.dump"))) == 3
    assert not list(backups.glob("*.partial"))
    assert "backup deferred" in result.stderr


def test_corrupt_recent_archive_cannot_replace_the_last_valid_fallback(tmp_path):
    backups, result = run_loop(tmp_path, corrupt_latest=True)
    assert (backups / "claw-quant-20000102-000000.dump").exists()
    assert (backups / "claw-quant-20000103-000000.dump").exists()
    assert not (backups / "claw-quant-20000101-000000.dump").exists()
    assert "invalid checksum" in result.stderr


def test_explicit_rotation_checks_existing_archives_without_starting_a_dump(tmp_path):
    backups,result=run_loop(tmp_path,prune_only=True)
    assert [p.name for p in sorted(backups.glob('*.dump'))]==[
        'claw-quant-20000102-000000.dump','claw-quant-20000103-000000.dump']
    assert (backups/'.last-success').read_text()=='0'


def test_policy_cannot_reduce_valid_backup_floor_to_one(tmp_path):
    result=subprocess.run(['sh',str(ROOT/'scripts/backup_loop.sh'),'--prune-only'],
        env={**os.environ,'BACKUP_DIR':str(tmp_path),'BACKUP_RETENTION_COUNT':'1'},capture_output=True,text=True)
    assert result.returncode==1
    assert 'at least two' in result.stderr
