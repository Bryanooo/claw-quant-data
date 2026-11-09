"""Read-only full financial-input audit with bounded exact source-version traces.

Does not calculate/publish factor values or certify a day. Market history and
numeric formula domains are intentionally outside this financial-source audit.
"""
import argparse
from collections import Counter
from datetime import date, timedelta
import json
from pathlib import Path
import sys
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
import pandas as pd
from psycopg2.extras import RealDictCursor

from service.db import get_conn
from service.research.local_factors.financial_dependencies import financial_dependencies, dependency_inputs
from service.research.local_factors.materializer import (
    _load_financial_panel, _INCOME_COLUMNS, _BALANCE_COLUMNS, _CASHFLOW_COLUMNS,
    _INDICATOR_COLUMNS, _FLOW_METRICS,
)

SOURCE_FIELDS = {metric: [(table, column)] for table, columns in (
    ('income', _INCOME_COLUMNS), ('balancesheet', _BALANCE_COLUMNS),
    ('cashflow', _CASHFLOW_COLUMNS), ('fina_indicator', _INDICATOR_COLUMNS),
) for column, metric in columns.items()}
SOURCE_FIELDS['equity_parent'] = [('balancesheet', 'total_hldr_eqy_inc_min_int'),
                                 ('balancesheet', 'minority_int')]


def required_periods(bucket, metric, lineage):
    if bucket == 'five_year_mean':
        return lineage.get('five_year_mean_expected_periods', [])
    base = {'ttm': 'current', 'ttm_previous': 'previous', 'ttm_year_ago': 'year_ago'}.get(bucket, bucket)
    end = lineage.get(base)
    if not end:
        return []
    end = pd.Timestamp(end)
    if metric in _FLOW_METRICS and bucket.startswith('ttm') and end.month != 12:
        return [str(end.date()), f'{end.year-1}-12-31', str((end-pd.DateOffset(years=1)).date())]
    if metric in _FLOW_METRICS and bucket in {'current', 'previous', 'year_ago', 'previous_year_ago'} and end.month != 3:
        return [str(end.date()), str((end-pd.offsets.QuarterEnd(1)).date())]
    return [str(end.date())]


def audit(target, example_limit=2):
    if not 1 <= example_limit <= 5:
        raise ValueError('source tracing must stay bounded to 1..5 examples per input')
    conn = get_conn()
    try:
        conn.set_session(isolation_level='REPEATABLE READ', readonly=True)
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SET LOCAL statement_timeout='120s'")
            cur.execute('SELECT transaction_timestamp() AS observed_at, txid_current_snapshot()::text AS snapshot')
            stamp = dict(cur.fetchone())
            cur.execute("""SELECT d.ts_code,d.close,b.total_mv FROM daily d
                LEFT JOIN LATERAL (SELECT total_mv FROM tushare_norm_daily_basic b
                  WHERE b.ts_code=d.ts_code AND b.trade_date=d.trade_date
                  ORDER BY _last_seen_at DESC,_record_hash DESC LIMIT 1) b ON true
                WHERE d.trade_date=%s ORDER BY d.ts_code""", (target,))
            market_rows = pd.DataFrame(cur.fetchall())
            if market_rows.empty:
                raise ValueError('no daily securities on requested date')
            market_rows = market_rows.set_index('ts_code').astype(float)
            codes = market_rows.index
            market = SimpleNamespace(
                alpha101=SimpleNamespace(close=market_rows[['close']].T),
                total_mv=market_rows[['total_mv']].T,
            )
            panel, diagnostics = _load_financial_panel(conn, target, codes, market, include_period_lineage=True)
            inputs = dependency_inputs(panel)
            cur.execute("""SELECT ts_code,audit_evidence->'unresolved' AS unresolved,source_execution_id,computed_at
                FROM local_factor_snapshot WHERE trade_date=%s AND schema_version IN
                (SELECT schema_version FROM local_factor_schema WHERE lifecycle_status='active')""", (target,))
            stored = list(cur.fetchall())
            old = Counter(k for r in stored for k in (r['unresolved'] or {}))
            evidence = {}

            def trace(table, code, period, cutoff):
                key = f'{table}:{code}:{period}:{cutoff}'
                if key in evidence:
                    return key
                fields = sorted({f for pairs in SOURCE_FIELDS.values() for t, f in pairs if t == table})
                cur.execute(f'SELECT * FROM {table}_as_of(%s,ARRAY[%s],%s,%s)', (cutoff, code, period, period))
                visible = [dict(r) for r in cur.fetchall()]
                if len(visible) > 1:
                    raise ValueError('ambiguous consolidated financial identity')
                cur.execute(f"""SELECT kind,published_on,available_on,first_seen_at,
                    {','.join('(row_data).'+f+' AS '+f for f in fields)}
                    FROM {table}_revision WHERE ts_code=%s AND end_date=%s
                    AND kind IN (0,1,4,5) ORDER BY available_on,published_on,kind""", (code, period))
                revisions = [dict(r) for r in cur.fetchall()]
                reasons = {}
                for f in fields:
                    if visible:
                        reasons[f] = 'visible_field_nonnull' if visible[0].get(f) is not None else 'visible_version_field_null'
                    elif revisions:
                        reasons[f] = ('archived_nonnull_only_after_cutoff' if any(r[f] is not None for r in revisions)
                                      else 'no_eligible_version_and_archived_field_null')
                    else:
                        reasons[f] = 'no_archived_consolidated_version'
                evidence[key] = dict(table=table,symbol=code,period=period,cutoff=cutoff,field_reasons=reasons,
                    visible=[{k:r.get(k) for k in ['ann_date','f_ann_date','report_type',*fields]} for r in visible],
                    revisions=revisions)
                return key

            input_reports = {}
            for (bucket, metric), values in sorted(inputs.items()):
                # Market proxies above support panel assembly only. Never use
                # their one-day mean to certify historical market dependencies.
                if bucket == 'market' or metric == 'market_cap':
                    input_reports[f'{bucket}.{metric}'] = dict(status='not_audited_market_dependency')
                    continue
                missing = [c for c in codes if values.get(c) is None or not np.isfinite(values[c])]
                examples = []
                for code in missing[:example_limit]:
                    lineage = diagnostics.get('period_lineage', {}).get(code, {})
                    cutoff = target
                    dependencies = [(bucket, metric)]
                    if (bucket, metric) == ('special', 'roe_ttm_lag63d'):
                        lag = diagnostics.get('lag63_input', {})
                        cutoff = date.fromisoformat(lag['as_of']) if lag.get('as_of') else None
                        lineage = lag.get('period_lineage', {}).get(code, {})
                        dependencies = [('ttm', 'net_profit_parent'), ('current', 'equity')]
                    refs = []
                    expected = []
                    for b, m in dependencies:
                        periods = required_periods(b, m, lineage)
                        expected.extend(periods)
                        for table, _ in SOURCE_FIELDS.get(m, []):
                            for period in periods:
                                if cutoff:
                                    refs.append(trace(table, code, period, cutoff))
                    examples.append(dict(symbol=code,expected_periods=sorted(set(expected)),
                        source_evidence_refs=sorted(set(refs)),
                        note='no_eligible_anchor_or_non_statement_input' if not refs else
                             'source_versions_only; reviewed_filing_overlay_is_separate'))
                input_reports[f'{bucket}.{metric}'] = dict(status='financial_input_observed',missing_count=len(missing),
                    missing_symbols=missing,source_fields=SOURCE_FIELDS.get(metric, []),examples=examples)
            factors = []
            for name, dependency in sorted(financial_dependencies().items()):
                missing_inputs = {'.'.join(key):input_reports['.'.join(key)]['missing_count']
                                  for key in sorted(dependency.required)
                                  if input_reports['.'.join(key)].get('missing_count', 0)}
                factors.append(dict(name=name,required_inputs=['.'.join(k) for k in sorted(dependency.required)],
                    optional_zero_fill_conventions=['.'.join(k) for k in sorted(dependency.optional)],
                    current_missing_financial_inputs=missing_inputs,stored_unresolved_securities=old[name]))
            return dict(**stamp,trade_date=target,securities=len(codes),factors=factors,inputs=input_reports,
                source_evidence=evidence,period_lineage=diagnostics.get('period_lineage',{}),
                official_filing_evidence=diagnostics.get('official_filing_evidence',[]),
                prior_executions=sorted({r['source_execution_id'] for r in stored if r['source_execution_id']}),
                summary=dict(financial_factors=len(factors),stored_unresolved_factors=sum(old[f['name']]>0 for f in factors),
                    factors_with_current_missing_financial_inputs=sum(bool(f['current_missing_financial_inputs']) for f in factors),
                    sampled_source_identities=len(evidence)),
                policy='read_only_input_diagnosis_not_factor_recalculation_or_acceptance; source examples bounded; all securities counted; market histories not audited')
    finally:
        conn.rollback()
        conn.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--date',required=True,type=date.fromisoformat)
    parser.add_argument('--examples',type=int,default=2)
    parser.add_argument('--output',required=True,type=Path)
    args = parser.parse_args()
    result = audit(args.date, args.examples)
    args.output.write_text(json.dumps(result,default=str,ensure_ascii=False,indent=2)+'\n')
    print(result['summary'])
