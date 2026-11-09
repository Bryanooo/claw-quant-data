"""Read-only full-history balance field audit, not a security-universe certificate.

No provider requests, repairs or synthetic values. Every invalid stored identity
is exported so a provider investigation can target exact dates/securities.
"""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from psycopg2.extras import RealDictCursor

from service.db import get_conn
from service.margin_quality import balance_issues, valid_balance_sql


def audit():
    datasets = {}
    with get_conn() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        cur.execute("SET LOCAL statement_timeout='120s'")
        for table, entity in (("margin", "exchange_id"), ("margin_detail", "ts_code")):
            # Table/column identifiers are code-owned constants, never CLI input.
            cur.execute(f"""SELECT count(*) rows, count(DISTINCT trade_date) dates,
                min(trade_date) first_date,max(trade_date) last_date FROM {table}""")
            summary = dict(cur.fetchone())
            cur.execute(f"""SELECT trade_date,{entity},rzye,rqye,rzrqye
                FROM {table} WHERE NOT ({valid_balance_sql()})
                ORDER BY trade_date,{entity}""")
            invalid = [dict(row, issues=balance_issues(row)) for row in cur.fetchall()]
            datasets[table] = dict(
                **summary,
                invalid_rows=len(invalid),
                invalid_dates=len({r["trade_date"] for r in invalid}),
                status="invalid_balances" if invalid else "balance_fields_valid",
                invalid_identities=invalid,
            )
    return dict(
        generated_at=datetime.now(timezone.utc).isoformat(),
        scope="stored balance fields only; not exhaustive security/date coverage",
        invariant="finite, non-negative rzye/rqye/rzrqye; abs(rzrqye-rzye-rqye)<=0.01 yuan",
        datasets=datasets,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit()
    args.output.write_text(
        json.dumps(result, default=str, ensure_ascii=False, indent=2) + "\n"
    )
    print(
        json.dumps(
            {
                k: {x: y for x, y in v.items() if x != "invalid_identities"}
                for k, v in result["datasets"].items()
            },
            default=str,
        )
    )
