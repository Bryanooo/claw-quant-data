"""Compare reviewed original-filing facts with stored source fields, read-only.

Mappings are deliberately limited to reviewed meanings; the main balance-sheet
fixed-assets line maps to the total, never silently to the net component.
Matching numbers do not certify other fields or historical factor availability.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from service.db import query
from service.financial_reconciliation import numeric_status
from service.financial_filing_facts import FACT_FIELDS

MAPPINGS = FACT_FIELDS


def verify(documents):
    results = []
    for doc in documents:
        artifact = query('SELECT content_hash FROM source_raw_artifact WHERE artifact_id=%s',
                         (doc['artifact_id'],))
        if not artifact or artifact[0]['content_hash'] != doc['sha256']:
            raise ValueError('original filing is not retained with the reviewed hash')
        for fact in doc['extracted_facts']:
            table, column = MAPPINGS[fact['field']]
            rows = query(f'SELECT {column} AS value, ann_date, f_ann_date FROM {table} '
                         'WHERE ts_code=%s AND end_date=%s AND report_type=1',
                         (doc['symbol'], doc['period']))
            if len(rows) > 1:
                raise ValueError('ambiguous financial source identity')
            stored = rows[0] if rows else {}
            results.append(dict(
                symbol=doc['symbol'], period=doc['period'], table=table, field=column,
                artifact_id=doc['artifact_id'], sha256=doc['sha256'], page=fact['page'],
                source_url=doc['url'], filing_publication=doc['published_on'],
                filing_value_yuan=fact['current'], local_value=stored.get('value'),
                local_ann_date=stored.get('ann_date'), local_f_ann_date=stored.get('f_ann_date'),
                status=numeric_status(stored.get('value'), fact['current'], '人民币元'),
                pit_certified=False,
            ))
    return dict(generated_at=datetime.now(timezone.utc),
                policy='reviewed_fact_comparison_no_source_write_no_full_row_PIT_promotion',
                counts=dict(Counter(r['status'] for r in results)), results=results)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--facts', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = verify(json.loads(args.facts.read_text())['documents'])
    args.output.write_text(json.dumps(report, default=str, ensure_ascii=False, indent=2)+'\n')
    print(report['counts'])
    if any(r['status'] != 'value_agreement' for r in report['results']):
        raise SystemExit(1)
