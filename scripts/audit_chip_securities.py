"""Bounded, resumable security/date scan; writes exact missing codes, not a success certificate."""
import argparse
from datetime import date, datetime, timedelta, timezone
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import psycopg2
import psycopg2.extras
from service.config import DB_CONFIG
from service.data_coverage.chip_securities import audit_security_dates, summarize_day


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--start', type=date.fromisoformat, required=True)
    parser.add_argument('--end', type=date.fromisoformat, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--resume', action='store_true', help='Reuse completed month files; use a new directory for a fresh audit')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    current = args.end
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SET statement_timeout='120s'")
            cur.execute("SET max_parallel_workers_per_gather=0")
            while current >= args.start:
                start = max(args.start, current.replace(day=1))
                path = args.output / f'{start}_{current}.json'
                if args.resume and path.exists():
                    current = start - timedelta(days=1)
                    continue
                try:
                    raw_rows = audit_security_dates(cur, start, current)
                except psycopg2.errors.QueryCanceled:
                    # A cold historical month must not monopolize the DB or
                    # discard prior months. Retry smaller read-only slices.
                    conn.rollback()
                    cur.execute("SET statement_timeout='120s'")
                    cur.execute("SET max_parallel_workers_per_gather=0")
                    raw_rows = []
                    day = start
                    while day <= current:
                        raw_rows.extend(audit_security_dates(cur, day, day))
                        conn.commit()
                        day += timedelta(days=1)
                rows = [summarize_day(row) for row in raw_rows]
                result = {'start': str(start), 'end': str(current),
                          'audited_at': datetime.now(timezone.utc).isoformat(),
                          'acceptance': 'security_presence_only_not_full_acceptance',
                          'missing_security_dates': sum(len(row['missing_codes']) for row in rows),
                          'days': rows}
                temporary = path.with_suffix('.tmp')
                temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2))
                temporary.replace(path)
                conn.commit()
                print(json.dumps({k:v for k,v in result.items() if k != 'days'}), flush=True)
                current = start - timedelta(days=1)


if __name__ == '__main__':
    main()
