"""Read-only, independent SQL reconstruction of governed FF3 daily outputs.

Does not call the production Python formula or write readiness states.
Run with --start YYYY-MM-DD --end YYYY-MM-DD; exits nonzero on any mismatch.
"""
import argparse
import json
import math
from datetime import date
from pathlib import Path
import sys

import psycopg2.extras

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from service.db import get_conn


VERIFY_SQL = r"""
WITH cutoff AS (
 SELECT cal_date FROM trade_cal WHERE exchange='SSE' AND is_open=1 AND cal_date<=%(day)s
 ORDER BY cal_date DESC OFFSET 59 LIMIT 1
), universe AS (
 SELECT s.ts_code FROM stock_basic s CROSS JOIN cutoff c
 WHERE s.ts_code ~ '\.(SH|SZ)$' AND nullif(s.list_date,'') IS NOT NULL
 AND s.list_date<=to_char(c.cal_date,'YYYYMMDD')
 AND (nullif(s.delist_date,'') IS NULL OR s.delist_date>to_char(%(day)s::date,'YYYYMMDD'))
 AND NOT EXISTS (SELECT 1 FROM stock_st st WHERE st.ts_code=s.ts_code
   AND st.trade_date=%(day)s)
), equity AS (
 SELECT DISTINCT ON(ts_code) ts_code,total_hldr_eqy_inc_min_int AS book
 FROM balancesheet_as_of(%(day)s,NULL,NULL,%(day)s)
 WHERE total_hldr_eqy_inc_min_int IS NOT NULL ORDER BY ts_code,end_date DESC,ann_date DESC
), returns AS (
 SELECT d.ts_code,d.pct_chg::float8/100 AS r FROM daily d JOIN universe u USING(ts_code)
 WHERE d.trade_date=%(day)s AND d.pct_chg IS NOT NULL
), inputs AS (
 SELECT r.*,c.total_mv::float8 AS cap,e.book::float8 AS book
 FROM returns r JOIN tushare_current_daily_basic c USING(ts_code)
 LEFT JOIN equity e USING(ts_code) WHERE c.trade_date=%(day)s AND c.total_mv IS NOT NULL
), ranked AS (
 SELECT *,book/cap AS bm,row_number() OVER(ORDER BY cap,ts_code) AS size_rank,
 count(*) OVER() AS n FROM inputs WHERE book>0 AND cap>0
), boundaries AS (
 SELECT array_agg(bm ORDER BY bm) AS values,count(*)::int AS n FROM ranked
), grouped AS (
 SELECT r.*,CASE WHEN size_rank<=r.n/2 THEN 'small' ELSE 'big' END AS size_group,
 CASE WHEN bm<=b.values[greatest(1,floor(b.n*0.3)::int)] THEN 'low'
      WHEN bm>=b.values[least(b.n,floor(b.n*0.7)::int+1)] THEN 'high' ELSE 'mid' END AS value_group
 FROM ranked r CROSS JOIN boundaries b
), portfolios AS (
 SELECT size_group,value_group,sum(r*cap)/sum(cap) AS v,count(*) AS n
 FROM grouped GROUP BY size_group,value_group
)
SELECT (SELECT count(*) FROM returns) AS source_count,
 (SELECT count(*) FROM inputs) AS eligible_count,
 (SELECT count(*) FROM ranked) AS book_count,
 (SELECT count(*) FROM grouped WHERE size_group='small') AS small_count,
 (SELECT count(*) FROM grouped WHERE size_group='big') AS big_count,
 (SELECT sum(r*cap)/sum(cap) FROM inputs) AS mkt,
 avg(v) FILTER(WHERE size_group='small')-avg(v) FILTER(WHERE size_group='big') AS smb,
 avg(v) FILTER(WHERE value_group='high')-avg(v) FILTER(WHERE value_group='low') AS hml,
 count(*) AS portfolios FROM portfolios
"""


def verify(start, end):
    conn = get_conn()
    conn.set_session(readonly=True, isolation_level='REPEATABLE READ')
    results = []
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SET LOCAL statement_timeout='120s'")
            cur.execute("SELECT cal_date FROM trade_cal WHERE exchange='SSE' AND is_open=1 "
                        "AND cal_date BETWEEN %s AND %s ORDER BY cal_date", (start,end))
            days = [r['cal_date'] for r in cur.fetchall()]
            for day in days:
                cur.execute(VERIFY_SQL, {'day': day})
                expected = dict(cur.fetchone())
                cur.execute('SELECT * FROM fama_french_daily WHERE trade_date=%s', (day,))
                actual = cur.fetchone()
                differences = {key: abs(float(actual[key])-expected[key])
                               if actual and actual[key] is not None and expected[key] is not None
                               else None for key in ('mkt','smb','hml')}
                passed = bool(actual and actual['status']=='ready'
                    and actual['formula_version']=='ff3-sh-sz-v3' and float(actual['risk_free'])==0
                    and expected['source_count']==expected['eligible_count']
                    and expected['portfolios']==6 and expected['book_count']>=20
                    and all(actual[k]==expected[k] for k in ('eligible_count','small_count','big_count'))
                    and actual['book_value_eligible_count']==expected['book_count']
                    and all(v is not None and math.isfinite(v) and v<1e-12 for v in differences.values()))
                results.append({'date':day.isoformat(),'passed':passed,
                                'execution_id':actual['source_execution_id'] if actual else None,
                                'expected':expected,'absolute_differences':differences})
        return results
    finally:
        conn.rollback()
        conn.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--start',type=date.fromisoformat,required=True)
    parser.add_argument('--end',type=date.fromisoformat,required=True)
    args = parser.parse_args()
    results = verify(args.start,args.end)
    print(json.dumps(results,ensure_ascii=False,default=str))
    raise SystemExit(0 if results and all(r['passed'] for r in results) else 1)
