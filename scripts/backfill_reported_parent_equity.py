"""Enrich an unchanged consolidated disclosure using the normal revision archive.

Use --period YYYYMMDD (repeatable). Default rolls back the database transaction.
Only promote the newly collected field when every previously collected field
matches the current statement and the candidate direct amounts agree.
"""
import argparse
import json
from contextlib import closing
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from psycopg2 import sql
from psycopg2.extras import execute_values
from collectors.stock.finance.balancesheet import BalancesheetCollector
from collectors.stock.finance.base import _to_val
from service.db import get_conn

FIELD = 'total_hldr_eqy_exc_min_int'


def backfill(collector, period, apply):
    frame = collector.fetch(period=period, report_type='1')
    if not collector.partition_completion_evidence()['verified'] or frame.empty:
        raise ValueError('incomplete consolidated statement response')
    columns = collector.CORE_FIELDS
    values = [tuple(collector._database_safe_value(_to_val(v), k) for k,v in zip(columns,row))
              for row in frame[columns].itertuples(index=False,name=None)]
    with closing(get_conn()) as conn, conn, conn.cursor() as cur:
        cur.execute("SELECT pg_advisory_xact_lock(hashtext('finance_revision'),hashtext('balancesheet'))")
        cur.execute("CREATE TEMP TABLE fetched (LIKE balancesheet INCLUDING DEFAULTS) ON COMMIT DROP")
        insert = sql.SQL('INSERT INTO fetched ({}) VALUES %s').format(
            sql.SQL(',').join(map(sql.Identifier,columns)))
        execute_values(cur, insert, values, page_size=1000)
        cur.execute("""CREATE TEMP TABLE exact_versions ON COMMIT DROP AS
            SELECT f.* FROM fetched f JOIN balancesheet b USING(ts_code,end_date,report_type)
            WHERE b.total_hldr_eqy_exc_min_int IS NULL AND f.total_hldr_eqy_exc_min_int IS NOT NULL
            AND to_jsonb(f)-'created_at'-'total_hldr_eqy_exc_min_int'
                =to_jsonb(b)-'created_at'-'total_hldr_eqy_exc_min_int'""")
        cur.execute("""CREATE TEMP TABLE enrichment (LIKE balancesheet INCLUDING DEFAULTS) ON COMMIT DROP;
            INSERT INTO enrichment SELECT DISTINCT ON(ts_code,end_date,report_type) *
            FROM exact_versions WHERE (ts_code,end_date,report_type) IN
               (SELECT ts_code,end_date,report_type FROM exact_versions GROUP BY 1,2,3
                HAVING COUNT(DISTINCT total_hldr_eqy_exc_min_int)=1)""")
        cur.execute("""SELECT COUNT(*),COUNT(*) FILTER(WHERE minority_int IS NULL),
            COUNT(*) FILTER(WHERE minority_int IS NOT NULL AND ABS(total_hldr_eqy_inc_min_int -
                                  minority_int - total_hldr_eqy_exc_min_int) > 0.01)
            FROM enrichment""")
        matched, sparse, conflicts = cur.fetchone()
        cur.execute("SELECT archive_financial_batch('balancesheet','pg_temp.enrichment',false)")
        cur.execute("""SELECT count(*) FROM enrichment e JOIN balancesheet b USING(ts_code,end_date,report_type)
            WHERE to_jsonb(e)-'created_at' IS DISTINCT FROM to_jsonb(b)-'created_at'""")
        if cur.fetchone()[0]:
            raise ValueError('latest version differed after enrichment')
        if not apply:
            conn.rollback()
    return dict(period=period,rows_returned=len(frame),matched=matched,
                previously_missing_minority=sparse,accounting_conflicts=conflicts,applied=apply)


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--period',action='append',required=True)
    parser.add_argument('--apply',action='store_true')
    args=parser.parse_args()
    collector=BalancesheetCollector()
    for period in args.period:
        print(json.dumps(backfill(collector,period,args.apply)),flush=True)
