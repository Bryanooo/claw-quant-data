"""Read-only, exact financial input availability inventory; not applicability.

An absent row or null field here is not evidence of permanent upstream absence.
This scans all local securities per requested period, recording latest-source
availability separately from the point-in-time revision gate.
"""
import argparse
from datetime import date, datetime, timezone
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from service.db import get_conn
from psycopg2.extras import RealDictCursor

FIELDS = {
    'income': ('ebit','ebitda','fin_exp_int_exp','fin_exp_int_inc'),
    'cashflow': ('finan_exp','depr_fa_coga_dpba','amort_intang_assets','lt_amort_deferred_exp','use_right_asset_dep'),
    'balancesheet': ('fix_assets','fix_assets_total','fixed_assets_disp'),
    'fina_indicator': ('ebit','ebitda','daa','fixed_assets'),
}


def audit(periods, cutoff):
    result=[]
    with get_conn() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
        cur.execute("SET LOCAL statement_timeout='120s'")
        for table,fields in FIELDS.items():
            selected=','.join(fields)
            condition='' if table=='fina_indicator' else 'AND report_type=1'
            for period in periods:
                cur.execute(f'SELECT ts_code,{selected} FROM {table} WHERE end_date=%s {condition}',(period,))
                current={r['ts_code']:dict(r) for r in cur.fetchall()}
                cur.execute(f'SELECT ts_code,{selected} FROM {table}_as_of(%s,NULL,%s,%s)',(cutoff,period,period))
                visible={r['ts_code']:dict(r) for r in cur.fetchall()}
                item=dict(table=table,period=period,latest_rows=len(current),pit_rows=len(visible),
                          latest_without_pit_version=sorted(set(current)-set(visible)), fields={})
                for field in fields:
                    item['fields'][field]={
                        'latest_nonnull':sum(r[field] is not None for r in current.values()),
                        'pit_nonnull':sum(r[field] is not None for r in visible.values()),
                        'latest_null_securities':sorted(s for s,r in current.items() if r[field] is None),
                        'pit_null_securities':sorted(s for s,r in visible.items() if r[field] is None),
                    }
                result.append(item)
    return dict(generated_at=datetime.now(timezone.utc),cutoff=cutoff,periods=periods,
                status='diagnostic_not_factor_acceptance',
                universe='local financial rows, not an all-listed-company expectation contract',tables=result)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--periods',nargs='+',type=date.fromisoformat,required=True)
    p.add_argument('--as-of',type=date.fromisoformat,required=True)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    data=audit(args.periods,args.as_of)
    args.output.write_text(json.dumps(data,default=str,ensure_ascii=False,indent=2)+'\n')
    for item in data['tables']:
        print(item['table'],item['period'],'latest',item['latest_rows'],'PIT',item['pit_rows'],
              {k:v['latest_nonnull'] for k,v in item['fields'].items()})
