"""Import reviewed original-filing facts. Dry run by default; never rewrites vendor rows."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from service.db import get_conn
from service.financial_filing_facts import prepare_facts, persist_facts

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--facts', type=Path, required=True)
    parser.add_argument('--reviewer', required=True)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    facts = prepare_facts(json.loads(args.facts.read_text())['documents'], reviewer=args.reviewer)
    with get_conn() as conn:
        inserted = persist_facts(conn, facts)
        if not args.apply:
            conn.rollback()
    print(json.dumps(dict(reviewed_facts=len(facts), inserted=inserted,
                          committed=args.apply, supplier_rows_modified=0)))
