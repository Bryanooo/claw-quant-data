"""Recover bounded financial backup observations; dry run unless --apply.

Never restore SQL or latest vendor tables. Hash verification is mandatory on
every invocation; original selected payloads are retained inside PostgreSQL.
"""
import argparse
from datetime import date, datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.audit_financial_backup import financial_copy_rows
from service.db import get_conn
from service.financial_backup_recovery import recover_batch, register_source


def verify_backup(path):
    path = path.resolve()
    expected_parent = Path(__file__).resolve().parents[1] / 'backups'
    if path.parent != expected_parent or not path.is_file() or not re.fullmatch(
        r'claw-quant-\d{8}-\d{6}\.dump', path.name
    ):
        raise ValueError('explicit project backup file required')
    before = path.stat()
    sidecar = Path(str(path)+'.sha256').read_text().split()
    if len(sidecar) != 2 or sidecar[1].lstrip('*') != path.name:
        raise ValueError('backup checksum identity mismatch')
    digest = hashlib.sha256()
    with path.open('rb') as source:
        for chunk in iter(lambda: source.read(8*1024*1024), b''):
            digest.update(chunk)
    if digest.hexdigest() != sidecar[0]:
        raise ValueError('backup checksum mismatch')
    if before != path.stat():
        # atime is allowed to move during a read, other evidence must be fixed.
        after = path.stat()
        if (before.st_ino,before.st_size,before.st_mtime_ns) != (after.st_ino,after.st_size,after.st_mtime_ns):
            raise ValueError('backup changed during verification')
    return path, digest.hexdigest(), before


def recover(backup, periods, symbols, apply=False):
    path,digest,before = verify_backup(backup)
    print('Full archive checksum verified; reading selected financial rows.', flush=True)
    command = ['docker','compose','exec','-T','backup','env','TZ=UTC','pg_restore']
    location = '/backups/'+path.name
    header = subprocess.check_output(command+['--list',location],text=True)
    match = re.search(r'Archive created at (\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})',header)
    if not match:
        raise ValueError('missing archive timestamp')
    created = datetime.strptime(match[1],'%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc)
    completed = datetime.fromtimestamp(before.st_mtime,timezone.utc)
    conn = get_conn()
    result = dict(backup=path.name,sha256=digest,checksum_verified=True,
                  completed_at=completed.isoformat(),applied=apply,tables={})
    try:
        with conn.cursor() as cur:
            cur.execute("SET LOCAL lock_timeout='5s'; SET LOCAL statement_timeout='120s'")
        available = register_source(conn,digest=digest,name=path.name,size=before.st_size,
                                    created=created,completed=completed)
        result['available_on'] = available.isoformat()
        for table in ('income','balancesheet','cashflow','fina_indicator'):
            count = changed = 0
            seen = set()
            batch = []
            # File-backed stderr prevents pipe deadlock without retaining it in memory.
            with tempfile.TemporaryFile(mode='w+t') as errors:
                proc = subprocess.Popen(command+['--data-only','--schema=public','--table='+table,'--file=-',location],
                                        stdout=subprocess.PIPE,stderr=errors,text=True)
                try:
                    for row in financial_copy_rows(proc.stdout,table):
                        if row['end_date'] not in periods or (symbols and row['ts_code'] not in symbols):
                            continue
                        if table != 'fina_indicator' and row.get('report_type') != '1':
                            continue
                        identity = row['ts_code'],row['end_date']
                        if identity in seen:
                            raise ValueError('duplicate backup identity across batches')
                        seen.add(identity)
                        count += 1
                        batch.append(row)
                        if len(batch) == 500:
                            changed += recover_batch(conn,table,digest,batch)
                            batch = []
                    changed += recover_batch(conn,table,digest,batch)
                    if proc.wait() != 0:
                        errors.seek(0)
                        raise RuntimeError('backup extraction failed: '+errors.read(300))
                finally:
                    proc.stdout.close()
                    if proc.poll() is None:
                        proc.terminate()
                        proc.wait(timeout=10)
            result['tables'][table] = dict(selected=count,revisions_inserted_or_earlier_proven=changed)
            print(table,result['tables'][table],flush=True)
        after = path.stat()
        if (before.st_ino,before.st_size,before.st_mtime_ns) != (after.st_ino,after.st_size,after.st_mtime_ns):
            raise ValueError('backup changed during extraction')
        if apply:
            conn.commit()
        else:
            conn.rollback()
        return result
    finally:
        conn.rollback()
        conn.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--backup',type=Path,required=True)
    parser.add_argument('--periods',nargs='+',type=date.fromisoformat,required=True)
    parser.add_argument('--symbols',nargs='+')
    parser.add_argument('--apply',action='store_true')
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args()
    result = recover(args.backup,{str(d) for d in args.periods},set(args.symbols or []),args.apply)
    args.output.write_text(json.dumps(result,indent=2)+'\n')
