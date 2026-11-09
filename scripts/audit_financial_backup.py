"""Inspect selected financial COPY streams in an existing backup; execute no SQL.

Candidate evidence only. Never uses row created_at or the report announcement
as the time a backup proves observation. Import requires checksum verification
and preserved backup completion evidence; this command does not import data.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import subprocess


def financial_copy_rows(lines, table):
    if table not in {'income','balancesheet','cashflow','fina_indicator'}:
        raise ValueError('unsupported backup table')
    columns = None
    complete = False
    for line in lines:
        if line.startswith('COPY '):
            match = re.fullmatch(r'COPY public\.'+table+r' \(([a-z_, ]+)\) FROM stdin;\n?', line)
            if not match or columns is not None:
                raise ValueError('unexpected COPY statement')
            columns = match[1].split(', ')
            if len(columns) != len(set(columns)) or not {'ts_code','end_date'} <= set(columns):
                raise ValueError('invalid backup identity columns')
        elif columns is not None and not complete:
            if line.rstrip('\n') == r'\.':
                complete = True
                continue
            values = line.rstrip('\n').split('\t')
            if len(values) != len(columns):
                raise ValueError('truncated or malformed COPY row')
            # Financial fields used here are numeric/date/identifier values;
            # reject unexpected COPY escapes rather than interpreting SQL.
            if any('\\' in v and v != r'\N' for v in values):
                raise ValueError('unexpected escaped financial value')
            yield dict(zip(columns, (None if v == r'\N' else v for v in values)))
    if columns is None or not complete:
        raise ValueError('missing or incomplete financial COPY stream')


def inspect(backup, periods, symbols):
    backup = backup.resolve()
    if backup.parent.name != 'backups' or not re.fullmatch(r'claw-quant-\d{8}-\d{6}\.dump',backup.name):
        raise ValueError('explicit regular project backup required')
    before = backup.stat()
    expected = Path(str(backup)+'.sha256').read_text().split()[0]
    command = ['docker','compose','exec','-T','backup','env','TZ=UTC','pg_restore']
    location = '/backups/'+backup.name
    header = subprocess.check_output(command+['--list',location],text=True)
    created = re.search(r'Archive created at (.+)',header).group(1).strip()
    results = {}
    for table in ('income','balancesheet','cashflow','fina_indicator'):
        proc = subprocess.Popen(command+['--data-only','--schema=public','--table='+table,'--file=-',location],
                                stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        rows = Counter()
        fields = {p:Counter() for p in periods}
        examples = []
        seen = set()
        try:
            for row in financial_copy_rows(proc.stdout,table):
                period = row['end_date']
                if period not in periods or (table != 'fina_indicator' and row.get('report_type') != '1'):
                    continue
                identity = (row['ts_code'],period)
                if identity in seen:
                    raise ValueError('duplicate consolidated backup identity')
                seen.add(identity)
                rows[period] += 1
                fields[period].update(k for k,v in row.items() if v is not None and k != 'created_at')
                if row['ts_code'] in symbols:
                    examples.append(row)
            error = proc.stderr.read()
            if proc.wait() != 0:
                raise RuntimeError('pg_restore inspection failed: '+error[:300])
        finally:
            if proc.poll() is None:
                proc.terminate()
                proc.wait(timeout=10)
        results[table] = dict(rows_by_period=dict(rows),nonnull_fields_by_period=fields,examples=examples)
    after = backup.stat()
    if (before.st_size,before.st_mtime_ns) != (after.st_size,after.st_mtime_ns):
        raise ValueError('backup changed during inspection')
    return dict(backup=str(backup),expected_sha256=expected,archive_created_at=created,
        file_mtime_utc=datetime.fromtimestamp(before.st_mtime,timezone.utc).isoformat(),size_bytes=before.st_size,
        tables=results,policy='candidate_evidence_only_no_database_write_no_announcement_backdating',
        checksum_policy='Expected sidecar digest recorded; separately verify full archive before importing evidence.')


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--backup',type=Path,required=True)
    p.add_argument('--periods',nargs='+',required=True)
    p.add_argument('--symbols',nargs='+',default=['300750.SZ','000001.SZ','600621.SH'])
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    result=inspect(args.backup,set(args.periods),set(args.symbols))
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print({k:v['rows_by_period'] for k,v in result['tables'].items()})
