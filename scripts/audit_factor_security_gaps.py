"""Export exact missing date/security pairs from current partial factor partitions. No provider calls."""
import argparse
from collections import defaultdict
from datetime import date, datetime, timezone
import gzip
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from psycopg2 import sql
from service.db import get_conn
from service.orchestration_v2.gap_repair import current_problem_partitions


def diagnose(end, *, start=None):
    problems = current_problem_partitions(start_date=start,end_date=end)
    result = {}
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        cur.execute("SET LOCAL statement_timeout='120s'")
        for dataset, table in [('stk_factor','tushare_norm_stk_factor'), ('stk_factor_pro','canonical_stk_factor_pro')]:
            days = sorted(d for d,s in problems.get(dataset, {}).items() if s=='partial')
            # Compare identities, not counts. Extra provider securities cannot
            # compensate for a missing name from the daily traded universe.
            by_code = defaultdict(list)
            statement = sql.SQL("""SELECT d.ts_code,d.trade_date FROM daily d
                    JOIN stock_basic s USING(ts_code)
                    WHERE d.trade_date=ANY(%s) AND NULLIF(s.list_date,'') IS NOT NULL
                    AND d.trade_date>=to_date(s.list_date,'YYYYMMDD')
                    AND (NULLIF(s.delist_date,'') IS NULL OR d.trade_date<=to_date(s.delist_date,'YYYYMMDD'))
                    EXCEPT SELECT f.ts_code,f.trade_date FROM {} f WHERE f.trade_date=ANY(%s)
                    ORDER BY 2,1""").format(sql.Identifier(table))
            for i in range(0,len(days),8):
                chunk=days[i:i+8]
                cur.execute(statement,(chunk,chunk))
                for code, day in cur.fetchall():
                    by_code[code].append(day.isoformat())
            result[dataset] = dict(audited_partial_dates=len(days),
                missing_pairs=sum(map(len,by_code.values())),securities=len(by_code),
                dates_with_missing=len({d for ds in by_code.values() for d in ds}),
                dates_by_security=dict(sorted(by_code.items(),key=lambda x:(-len(x[1]),x[0]))))
    return dict(start=start.isoformat() if start else None,as_of=end.isoformat(),generated_at=datetime.now(timezone.utc).isoformat(),
                universe='daily.ts_code on the same date; local gap is not proof of provider absence',
                datasets=result)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--start',type=date.fromisoformat)
    p.add_argument('--end',type=date.fromisoformat,required=True)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    if args.start and args.start>args.end:
        p.error('--start cannot exceed --end')
    data=diagnose(args.end,start=args.start)
    with gzip.open(args.output,'wt',encoding='utf-8') as fp:
        json.dump(data,fp,ensure_ascii=False)
    for key, item in data['datasets'].items():
        print(key,{k:v for k,v in item.items() if k!='dates_by_security'},
              [(c,len(ds)) for c,ds in list(item['dates_by_security'].items())[:12]])
