"""Trace exact source fields used by financial factors without relaxing PIT rules."""
import argparse
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from service.db import query


def compare_archived_probe(probe, cutoff):
    """Match exact statement identities and values; a current value is not a PIT proof."""
    from collections import Counter, defaultdict
    from decimal import Decimal
    table, field = {('balancesheet_vip','fix_assets'):('balancesheet','fix_assets'),
                    ('income_vip','ebitda'):('income','ebitda')}[(probe['api'],probe['field'])]
    records = probe['records']
    if not probe['pagination_exhausted'] or len(records) != probe['rows']:
        raise ValueError('incomplete provider evidence')
    period = date.fromisoformat(probe['period'])
    stored = query(f"""SELECT ts_code,kind,to_char((row_data).ann_date,'YYYYMMDD') AS ann,
                  to_char((row_data).f_ann_date,'YYYYMMDD') AS f_ann,available_on,
                  (row_data).{field} AS value FROM {table}_revision
                  WHERE end_date=%s AND (row_data).{field} IS NOT NULL""",(period,))
    versions = defaultdict(list)
    for r in stored:
        versions[(r['ts_code'],r['kind'],r['ann'],r['f_ann'],r['value'])].append(r['available_on'])
    def identity(row):
        return (row['ts_code'],int(row['report_type']),row.get('ann_date'),row.get('f_ann_date'))
    returned = defaultdict(set)
    for row in records:
        returned[identity(row)].add(row[field])
    counts, unmatched = Counter(), []
    for row in records:
        if row[field] is None:
            counts['provider_null_rows'] += 1
            continue
        key=(*identity(row),Decimal(str(row[field])))
        days=versions.get(key)
        if days is None:
            counts['exact_revision_not_matched'] += 1
            unmatched.append(dict(row,conflicting_provider_values=len(returned[identity(row)])>1))
        elif min(days) > cutoff:
            counts['exact_revision_only_after_cutoff'] += 1
        else:
            counts['exact_revision_archived_by_cutoff'] += 1
    return dict(field=field,period=str(period),as_of=str(cutoff),rows=len(records),
                counts=dict(counts),unmatched=unmatched)


def explain(visible, revisions):
    if visible:
        return 'visible_value' if visible[0]['value'] is not None else 'visible_version_field_null'
    return 'no_eligible_version_as_of' if revisions else 'no_archived_consolidated_version'


def trace(code, as_of, end):
    if end > as_of or (end.month,end.day) not in ((3,31),(6,30),(9,30),(12,31)):
        raise ValueError('period must be a closed quarter on or before the evaluation date')
    periods = [end] if end.month==12 else [end,date(end.year-1,12,31),end.replace(year=end.year-1)]
    result = {}
    for table, field, required in [('income','ebitda',periods),('income','revenue',periods),
                                    ('balancesheet','fix_assets',[end])]:
        for period in required:
            visible=query(f'SELECT report_type,{field} AS value FROM {table}_as_of(%s,%s,%s,%s)',
                          (as_of,[code],period,period))
            versions=query(f"""SELECT kind,published_on,available_on,(row_data).{field} AS value
                FROM {table}_revision WHERE ts_code=%s AND end_date=%s AND kind IN (1,4,5)
                ORDER BY available_on,published_on,kind""",(code,period))
            result[f'{field}:{period}']={'reason':explain(visible,versions),'visible':visible,
                                          'archived_not_necessarily_visible':versions}
    return {'code':code,'as_of':as_of,'period':end,'inputs':result}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--code',required=True)
    p.add_argument('--as-of',required=True,type=date.fromisoformat)
    p.add_argument('--period',required=True,type=date.fromisoformat)
    args=p.parse_args()
    print(json.dumps(trace(args.code,args.as_of,args.period),default=str,ensure_ascii=False,indent=2))
