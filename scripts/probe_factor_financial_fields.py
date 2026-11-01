"""Bounded read-only provider evidence for financial factor input blockers.

Never writes business tables, substitutes fields, or marks factors ready.
Duplicate pages and exhausted pagination budgets fail closed.
"""
from datetime import date
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from collectors.tushare_raw import CatalogRawCollector


def probe(api, field, period, *, page_size=1000, max_pages=10):
    collector = CatalogRawCollector(api)
    records, signatures = [], set()
    for page in range(max_pages):
        # Standard endpoints require ts_code. The period-wide read-only VIP
        # endpoint is the same endpoint used by our finance collectors.
        frame = collector.pro.query(api + '_vip', period=period, limit=page_size, offset=page*page_size,
            fields=f'ts_code,ann_date,f_ann_date,end_date,report_type,{field}')
        required = {'ts_code', 'end_date', field}
        if len(frame) and not required.issubset(frame.columns):
            raise ValueError('provider omitted requested contract fields')
        if len(frame) and set(frame.end_date.astype(str)) != {period}:
            raise ValueError('provider returned a different report period')
        rows = json.loads(frame.to_json(orient='records'))
        signature = hashlib.sha256(json.dumps(rows, sort_keys=True).encode()).hexdigest()
        if rows and signature in signatures:
            raise ValueError('provider repeated a page; completeness not established')
        signatures.add(signature)
        records.extend(rows)
        if len(rows) < page_size:
            return {'api': api + '_vip', 'field': field, 'period': period,
                    'pages': page+1, 'pagination_exhausted': True,
                    'rows': len(records), 'nonnull_rows': sum(r[field] is not None for r in records),
                    'records': records}
    raise ValueError('page budget exhausted; completeness not established')


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--period', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    date.fromisoformat(f'{args.period[:4]}-{args.period[4:6]}-{args.period[6:]}')
    report = {'scope': 'provider response evidence; not factor acceptance', 'probes': []}
    for api, field in [('balancesheet', 'fix_assets'), ('income', 'ebitda')]:
        result = probe(api, field, args.period)
        report['probes'].append(result)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
        print({k:v for k,v in result.items() if k != 'records'}, flush=True)
