"""Read-only, one-snapshot replay of reviewed original-filing D&A evidence."""
import argparse
from collections import Counter
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from psycopg2.extras import RealDictCursor
from service.db import get_conn
from service.financial_component_reconciliation import reconcile_components, reconcile_interest_sign


def audit(documents):
    conn = get_conn()
    try:
        conn.set_session(isolation_level='REPEATABLE READ', readonly=True)
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SET LOCAL statement_timeout = '60s'")
            cur.execute('SELECT transaction_timestamp() AS observed_at, '
                        'txid_current_snapshot()::text AS database_snapshot')
            report = dict(cur.fetchone())
            rows = []
            for doc in documents:
                sources = {}
                statement = 'income' if doc.get('diagnostic') == 'interest_sign' else 'cashflow'
                for table in (statement, 'fina_indicator'):
                    scope = ' AND report_type=1' if table == statement else ''
                    cur.execute(f'SELECT * FROM {table} WHERE ts_code=%s AND end_date=%s{scope}',
                                (doc['symbol'], doc['period']))
                    matches = cur.fetchall()
                    if len(matches) > 1:
                        raise ValueError(f'ambiguous source rows: {table} {doc["symbol"]}')
                    sources[table] = dict(matches[0]) if matches else {}
                cur.execute('SELECT * FROM source_raw_artifact WHERE artifact_id=%s', (doc['artifact_id'],))
                artifact = dict(cur.fetchone() or {})
                reconcile = reconcile_interest_sign if statement == 'income' else reconcile_components
                rows.append(reconcile(doc, sources[statement], sources['fina_indicator'], artifact))
            report.update(rows=rows, counts=dict(Counter(r['status'] for r in rows)),
                          policy='diagnostic_only_no_source_overwrite_no_formula_change_no_acceptance')
            return report
    finally:
        conn.rollback()
        conn.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--facts', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = audit(json.loads(args.facts.read_text())['documents'])
    args.output.write_text(json.dumps(result, default=str, ensure_ascii=False, indent=2)+'\n')
    print(result['observed_at'], result['counts'])
