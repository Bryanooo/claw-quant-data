"""Read-only cutoff audit of original-filing recovery; not full factor acceptance."""
import argparse
from collections import Counter
from datetime import date, datetime, timezone
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from service.db import get_conn
from service.financial_filing_facts import recover_rows
from psycopg2.extras import RealDictCursor


def audit(symbol, cutoffs):
    output=[]
    with get_conn() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
        cur.execute('SELECT * FROM financial_filing_fact WHERE ts_code=%s AND revoked_at IS NULL', (symbol,))
        facts=[dict(r) for r in cur.fetchall()]
        for cutoff in cutoffs:
            for table in ('income','balancesheet','cashflow'):
                subset=[f for f in facts if f['statement_table']==table]
                if not subset:
                    continue
                fields=sorted({f['field_name'] for f in subset})
                cur.execute(f'SELECT ts_code,end_date,ann_date,report_type, '
                            f'greatest(ann_date,f_ann_date) AS _disclosure,{",".join(fields)} '
                            f'FROM {table}_as_of(%s,ARRAY[%s],%s,%s)',
                            (cutoff,symbol,min(f['end_date'] for f in subset),max(f['end_date'] for f in subset)))
                original=[dict(r) for r in cur.fetchall()]
                recovered,evidence=recover_rows(original,subset,table=table,fields=fields,cutoff=cutoff)
                output.append(dict(cutoff=cutoff,table=table,before=original,after=recovered,
                    counts=dict(Counter(e['status'] for e in evidence)),evidence=evidence))
    return dict(generated_at=datetime.now(timezone.utc),symbol=symbol,
                policy='field_level_cutoff_evidence_not_full_statement_or_factor_acceptance',results=output)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--symbol',required=True)
    parser.add_argument('--cutoffs',nargs='+',type=date.fromisoformat,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    report=audit(args.symbol,args.cutoffs)
    args.output.write_text(json.dumps(report,default=str,ensure_ascii=False,indent=2)+'\n')
    for result in report['results']:
        print(result['cutoff'],result['table'],result['counts'])
