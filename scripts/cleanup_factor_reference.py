#!/usr/bin/env python3
"""Bounded reference-only retention. Never deletes local factors or audit logs.

Preserves all locally calculated/validated dates, month-end reference dates,
and a frozen deterministic 128-security reference panel on the selected date.
Deletion requires a successful sample execution and disabled legacy dispatch.
Default is dry-run. Ordinary DELETE frees reusable database space, not OS bytes.
"""
import argparse
from datetime import date
import json
from pathlib import Path
import sys
import time
from psycopg2.extras import RealDictCursor

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from service.db import get_conn
from service.orchestration_v2.repository import OrchestrationV2Repository


def clean(day: date, *, apply: bool = False, max_rows: int = 10000,
          batch_size: int = 500, seconds: int = 60) -> dict:
    if day >= date(2026,10,8):
        raise ValueError('October research dates are protected')
    if not 1 <= batch_size <= 1000 or not 1 <= max_rows <= 100000:
        raise ValueError('bounded cleanup limits exceeded')
    conn=get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SET statement_timeout='20s'")
            cur.execute("SET lock_timeout='500ms'")
            cur.execute("SELECT pg_try_advisory_lock(20261031,272)")
            if not cur.fetchone()[0]:
                raise RuntimeError('another reference cleanup is running')
            cur.execute("""SELECT EXISTS(SELECT 1 FROM orchestration_v2.task_execution
                WHERE task_key='factor_reference_sample' AND status='success'),
                EXISTS(SELECT 1 FROM orchestration_v2.task_definition WHERE task_key='factor_value'
                    AND lifecycle_status='active' AND definition->'schedule'->>'mode'='disabled')""")
            if not all(cur.fetchone()):
                raise RuntimeError('reference cutover has not passed verification')
            cur.execute("""SELECT
                EXISTS(SELECT 1 FROM local_factor_validation WHERE trade_date=%s) OR
                EXISTS(SELECT 1 FROM local_factor_snapshot WHERE trade_date=%s) OR
                %s::date=(SELECT max(cal_date) FROM trade_cal WHERE exchange='SSE'
                    AND is_open=1 AND date_trunc('month',cal_date)=date_trunc('month',%s::date))""",
                (day,day,day,day))
            if cur.fetchone()[0] is not False:
                return {'date':str(day),'protected':True,'deleted':0}
            cur.execute("""SELECT max(task_execution_id) FROM orchestration_v2.task_execution
                WHERE task_key='factor_reference_sample' AND status='success'""")
            audit_execution = cur.fetchone()[0]
            cur.execute('CREATE TEMP TABLE reference_keep_codes(ts_code text PRIMARY KEY) ON COMMIT PRESERVE ROWS')
            cur.execute("""INSERT INTO reference_keep_codes
                SELECT ts_code FROM (
                  SELECT ts_code,row_number() OVER(ORDER BY
                    md5('factor-reference-fixed-v1:'||ts_code),ts_code) fixed_rank
                  FROM (SELECT b.ts_code FROM stock_basic b WHERE EXISTS (
                        SELECT 1 FROM tushare_norm_factor_value r
                        WHERE r.trade_date=%s AND r.ts_code=b.ts_code)) u
                ) ranked ORDER BY CASE WHEN fixed_rank<=32 THEN 0 ELSE 1 END,
                  CASE WHEN fixed_rank<=32 THEN fixed_rank END,
                  md5(%s||':'||ts_code),ts_code LIMIT 128""",(day,str(day)))
            cur.execute('SELECT ts_code FROM reference_keep_codes ORDER BY ts_code')
            codes=[r[0] for r in cur.fetchall()]
            # Freeze existing reference workflow samples too, including pending
            # investigations; no dependence on which schema version is current.
            cur.execute("""INSERT INTO reference_keep_codes SELECT DISTINCT jsonb_array_elements_text(
                frozen_scope->'reference_securities') FROM orchestration_v2.task_execution
                WHERE task_key='factor_reference_sample' AND observation_end=%s
                ON CONFLICT DO NOTHING""",(day,))
        conn.commit()
        result={'date':str(day),'apply':apply,'sample_codes':codes,'deleted':0,
                'retention':'local/validation dates + month ends + 128 stocks + execution samples'}
        if not apply:
            return result
        started=time.monotonic()
        while result['deleted'] < max_rows and time.monotonic()-started < seconds:
            with conn.cursor() as cur:
                # Recheck newly created investigations inside each statement.
                cur.execute("""WITH victims AS (
                  SELECT r.ctid FROM tushare_norm_factor_value r WHERE r.trade_date=%s
                    AND NOT EXISTS(SELECT 1 FROM reference_keep_codes k WHERE k.ts_code=r.ts_code)
                    AND EXISTS(SELECT 1 FROM stock_basic b WHERE b.ts_code=r.ts_code)
                    AND NOT EXISTS(SELECT 1 FROM local_factor_snapshot WHERE trade_date=%s)
                    AND NOT EXISTS(SELECT 1 FROM local_factor_validation WHERE trade_date=%s)
                  LIMIT %s FOR UPDATE SKIP LOCKED
                ) DELETE FROM tushare_norm_factor_value r USING victims v WHERE r.ctid=v.ctid""",
                (day,day,day,min(batch_size,max_rows-result['deleted'])))
                deleted=cur.rowcount
            if deleted:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    OrchestrationV2Repository._append_event(cur, audit_execution,
                        event_type='reference.retention.pruned', node_key=None,
                        attempt_number=None, event_key=None,
                        payload={'date':str(day),'deleted':deleted,
                                 'retention':result['retention'],
                                 'sample_codes':codes}, evidence_references=[])
            conn.commit()
            result['deleted']+=deleted
            if not deleted:
                result['selected_date_pruned']=True
                break
            time.sleep(0.5)
        return result
    finally:
        conn.close()


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--date',type=date.fromisoformat,required=True)
    p.add_argument('--apply',action='store_true')
    p.add_argument('--max-rows',type=int,default=10000)
    p.add_argument('--seconds',type=int,default=60)
    a=p.parse_args()
    print(json.dumps(clean(a.date,apply=a.apply,max_rows=a.max_rows,seconds=a.seconds)))
