#!/usr/bin/env python3
"""Read-only factor readiness gate: row coverage and stored audit evidence.

Does not equate execution success, source-field presence or provider correlation
with full readiness. Does not recompute numerical formulas or certify input
freshness. --details emits every unresolved security/factor pair.
"""
from __future__ import annotations

import argparse
from datetime import date
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from service.db import get_conn
from service.research.local_factors.catalog import FACTOR_SCHEMA_VERSION
from service.research.local_factors.materializer import FORMULA_DIGEST


def stored_quality_ready(days: list[dict]) -> bool:
    return bool(days) and all(
        d['expected_securities'] > 0
        and d['present_securities'] == d['expected_securities']
        and d['unready_securities'] == 0
        for d in days
    )


def financial_input_freshness(execution_id: int) -> dict:
    """Compare committed compute evidence with current PIT statement inputs.

    This intentionally does not certify market inputs or provider agreement.
    Missing execution evidence fails closed, rather than accepting timestamps.
    """
    from service.research.local_factors.materializer import (
        _statement_rows, frame_digest, _INCOME_COLUMNS, _BALANCE_COLUMNS,
        _CASHFLOW_COLUMNS, _INDICATOR_COLUMNS,
    )
    sources = (('income', _INCOME_COLUMNS), ('balancesheet', _BALANCE_COLUMNS),
               ('cashflow', _CASHFLOW_COLUMNS), ('fina_indicator', _INDICATOR_COLUMNS))
    connection = get_conn()
    try:
        connection.set_session(readonly=True, isolation_level='REPEATABLE READ')
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL statement_timeout='60s'")
            cursor.execute("""SELECT payload FROM orchestration_v2.task_execution_event
                WHERE task_execution_id=%s AND event_type='node.transform.completed'
                ORDER BY event_id DESC LIMIT 1""", (execution_id,))
            row = cursor.fetchone()
            if not row or not row[0].get('financial_input_digests'):
                return {'execution_id': execution_id, 'status': 'missing_compute_evidence'}
            evidence = row[0]
            target = date.fromisoformat(evidence['snapshot_date'])
            cursor.execute("""SELECT cal_date FROM trade_cal WHERE exchange='SSE'
                AND is_open=1 AND cal_date<=%s ORDER BY cal_date DESC OFFSET 63 LIMIT 1""",
                           (target,))
            lag = cursor.fetchone()
        checks = []
        for label, day, recorded in (
            ('current', target, evidence.get('financial_input_digests', [])),
            ('lag63', lag[0] if lag else None,
             (evidence.get('lag63_input') or {}).get('financial_input_digests', [])),
        ):
            if day is None:
                checks.append({'bucket': label, 'status': 'missing_calendar_evidence'})
                continue
            for index, (table, columns) in enumerate(sources):
                actual = frame_digest(_statement_rows(connection, table, columns, day))
                expected = recorded[index] if len(recorded) > index else None
                checks.append({'bucket': label, 'source': table, 'asof': day,
                               'status': 'matching' if expected == actual else
                                         'missing_digest' if expected is None else 'stale',
                               'recorded_digest': expected, 'current_digest': actual})
        return {'execution_id': execution_id, 'date': target, 'checks': checks,
                'status': 'matching' if all(c['status']=='matching' for c in checks)
                          else 'not_verified'}
    finally:
        connection.close()


def comparative_statement_gaps(asof: date) -> list[dict]:
    """Distinguish absent prior reports from reports unavailable at the cutoff.

    This diagnoses row availability only, not non-null financial fields. Four
    prior quarters cover the immediate comparable-period investigation.
    """
    sources = []
    for table in ('income', 'balancesheet', 'cashflow', 'fina_indicator'):
        availability = 'ann_date' if table == 'fina_indicator' else 'greatest(ann_date,f_ann_date)'
        report_filter = '' if table == 'fina_indicator' else "AND report_type IN ('1','4')"
        sources.append(f"SELECT '{table}' src,ts_code,end_date,{availability} available_at "
                       f"FROM {table} WHERE TRUE {report_filter}")
    connection = get_conn()
    try:
        connection.set_session(readonly=True)
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL statement_timeout='60s'")
            cursor.execute('WITH statements AS (' + ' UNION ALL '.join(sources) + """),
                latest AS (
                  SELECT s.ts_code,max(end_date) period FROM statements s
                  JOIN daily d ON d.ts_code=s.ts_code AND d.trade_date=%s
                  WHERE s.available_at<=%s GROUP BY 1
                ), expected AS (
                  SELECT l.ts_code,(date_trunc('quarter',l.period)-make_interval(months=>n*3)
                      +interval '3 months - 1 day')::date period
                  FROM latest l CROSS JOIN generate_series(1,4) n
                ), missing AS (
                  SELECT v.src,l.period,l.ts_code,
                    CASE WHEN EXISTS(SELECT 1 FROM statements s WHERE s.src=v.src
                        AND s.ts_code=l.ts_code AND s.end_date=l.period)
                      THEN 'report_exists_but_not_available_at_cutoff'
                      ELSE 'no_report_in_local_source_table' END reason
                  FROM expected l CROSS JOIN
                    (VALUES('income'),('balancesheet'),('cashflow'),('fina_indicator')) v(src)
                  WHERE NOT EXISTS(SELECT 1 FROM statements s WHERE s.src=v.src
                      AND s.ts_code=l.ts_code AND s.end_date=l.period AND s.available_at<=%s)
                ) SELECT src,period,reason,count(*),array_agg(ts_code ORDER BY ts_code)
                  FROM missing GROUP BY 1,2,3 ORDER BY 1,2,3
            """, (asof,asof,asof))
            return [dict(zip(('source','period','reason','count','codes'), r))
                    for r in cursor.fetchall()]
    finally:
        connection.close()


def audit(start: date, end: date, *, details: bool = False) -> dict:
    connection = get_conn()
    try:
        connection.set_session(readonly=True, isolation_level='REPEATABLE READ')
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL statement_timeout='60s'")
            cursor.execute("""
                SELECT c.cal_date,
                       count(d.ts_code) expected_securities,
                       count(s.ts_code) present_securities,
                       count(*) FILTER (WHERE d.ts_code IS NOT NULL AND
                         (s.ts_code IS NULL OR s.audit_status IS DISTINCT FROM 'ready'
                          OR s.technical_audit_status IS DISTINCT FROM 'ready'
                          OR s.formula_digest IS DISTINCT FROM %s)) unready_securities,
                       max(s.computed_at) last_computed_at
                FROM trade_cal c
                LEFT JOIN daily d ON d.trade_date=c.cal_date
                LEFT JOIN local_factor_snapshot s ON s.trade_date=d.trade_date
                  AND s.ts_code=d.ts_code AND s.schema_version=%s
                WHERE c.exchange='SSE' AND c.is_open=1
                  AND c.cal_date BETWEEN %s AND %s
                GROUP BY c.cal_date ORDER BY c.cal_date
            """, (FORMULA_DIGEST, FACTOR_SCHEMA_VERSION, start, end))
            columns = [c.name for c in cursor.description]
            days = [dict(zip(columns, row)) for row in cursor.fetchall()]
            cursor.execute("""
                SELECT s.trade_date, p.key, p.value, count(*),
                       (array_agg(s.ts_code ORDER BY s.ts_code))[1:5]
                FROM local_factor_snapshot s
                JOIN daily d USING(trade_date,ts_code)
                CROSS JOIN LATERAL jsonb_each_text(s.audit_evidence->'unresolved') p
                WHERE s.schema_version=%s AND s.trade_date BETWEEN %s AND %s
                GROUP BY 1,2,3 ORDER BY 1,count(*) DESC,2,3
            """, (FACTOR_SCHEMA_VERSION, start, end))
            problems = [dict(zip(('date','factor','reason','count','examples'), row))
                        for row in cursor.fetchall()]
            result = {'schema_version': FACTOR_SCHEMA_VERSION, 'days': days,
                      'unresolved': problems,
                      'stored_quality_ready': stored_quality_ready(days),
                      'external_numerical_equivalence': 'not_certified_by_this_audit'}
            result['input_freshness'] = 'requires_source_digest_validation'
            if details:
                cursor.execute("""
                    SELECT s.trade_date,s.ts_code,p.key,p.value
                    FROM local_factor_snapshot s JOIN daily d USING(trade_date,ts_code)
                    CROSS JOIN LATERAL jsonb_each_text(s.audit_evidence->'unresolved') p
                    WHERE s.schema_version=%s AND s.trade_date BETWEEN %s AND %s
                    ORDER BY 1,2,3
                """, (FACTOR_SCHEMA_VERSION,start,end))
                result['security_details'] = [dict(zip(('date','code','factor','reason'), r))
                                               for r in cursor.fetchall()]
            return result
    finally:
        connection.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--start', type=date.fromisoformat, default=date(2026,10,8))
    parser.add_argument('--end', type=date.fromisoformat, default=date(2026,10,30))
    parser.add_argument('--details', action='store_true')
    parser.add_argument('--comparatives', action='store_true',
                        help='Include missing prior-quarter statements as of --end')
    parser.add_argument('--execution-id', type=int, action='append', default=[],
                        help='Check current and lag63 financial input fingerprints')
    args = parser.parse_args()
    if args.end < args.start:
        parser.error('end must not precede start')
    result = audit(args.start, args.end, details=args.details)
    if args.comparatives:
        result['comparative_statement_gaps'] = comparative_statement_gaps(args.end)
    if args.execution_id:
        result['financial_input_checks'] = [financial_input_freshness(i)
                                            for i in args.execution_id]
    print(json.dumps(result, ensure_ascii=False, default=str))
    return 0 if result['stored_quality_ready'] and all(
        item['status']=='matching' for item in result.get('financial_input_checks', [])
    ) else 1


if __name__ == '__main__':
    raise SystemExit(main())
