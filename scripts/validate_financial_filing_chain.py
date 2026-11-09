"""Read-only single-security filing-to-factor regression, never snapshot acceptance.

Compare the actual materializer's quarterly/TTM inputs with independent Decimal
arithmetic over verified current-column originals. Missing evidence stays missing.
Market/rank/five-year factor validation is outside this bounded diagnostic.
"""
import argparse
from datetime import date, datetime, timezone
from decimal import Decimal
import json
from pathlib import Path
import sys
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
import pandas as pd
from psycopg2.extras import RealDictCursor

from service.db import get_conn
from service.research.local_factors.materializer import _load_financial_panel
from service.research.local_factors.financial import FinancialFactorEvaluator
from service.research.local_factors.financial_dependencies import dependency_inputs, financial_dependencies


def original_value(facts, table, field, period, cutoff):
    versions = [f for f in facts if f['statement_table'] == table and
                str(f['end_date']) == str(period) and not f.get('revoked_at') and
                f['available_on'] <= cutoff and f['published_on'] < cutoff]
    if not versions:
        return None
    latest = max(f['published_on'] for f in versions)
    values = {Decimal(str(f['value_yuan'])) for f in versions
              if f['published_on'] == latest and f['field_name'] == field}
    return next(iter(values)) if len(values) == 1 else None


def expected_flow(facts, table, field, end, cutoff, bucket):
    end = date.fromisoformat(str(end))
    if bucket == 'current':
        terms = [(end, 1)]
        if end.month != 3:
            terms.append(((pd.Timestamp(end)-pd.offsets.QuarterEnd(1)).date(), -1))
    elif bucket == 'ttm':
        terms = [(end, 1)]
        if end.month != 12:
            terms += [(date(end.year-1, 12, 31), 1), (end.replace(year=end.year-1), -1)]
    else:
        raise ValueError('only current-quarter and TTM flows supported')
    values = [original_value(facts, table, field, period, cutoff) for period, _ in terms]
    if any(value is None for value in values):
        return None
    return sum((value*sign for value, (_, sign) in zip(values, terms)), Decimal(0))


def validate(symbol, cutoffs):
    if not 1 <= len(cutoffs) <= 4:
        raise ValueError('bounded regression permits 1..4 cutoffs')
    results = []
    with get_conn() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
        cur.execute("SET LOCAL statement_timeout='120s'")
        cur.execute('SELECT * FROM financial_filing_fact WHERE ts_code=%s AND revoked_at IS NULL', (symbol,))
        facts = list(cur.fetchall())
        for cutoff in cutoffs:
            cur.execute('SELECT d.close,b.total_mv FROM daily d LEFT JOIN LATERAL '
                        '(SELECT total_mv FROM tushare_norm_daily_basic b WHERE '
                        'b.ts_code=d.ts_code AND b.trade_date=d.trade_date '
                        'ORDER BY _last_seen_at DESC,_record_hash DESC LIMIT 1) b ON true '
                        'WHERE d.ts_code=%s AND d.trade_date=%s', (symbol, cutoff))
            row = cur.fetchone()
            if not row:
                raise ValueError('no daily observation on cutoff')
            codes = pd.Index([symbol])
            market = SimpleNamespace(alpha101=SimpleNamespace(close=pd.DataFrame(
                {symbol: [float(row['close'])]}, index=[cutoff])), total_mv=pd.DataFrame(
                {symbol: [float(row['total_mv']) if row['total_mv'] is not None else np.nan]}, index=[cutoff]))
            panel, diag = _load_financial_panel(conn, cutoff, codes, market, include_period_lineage=True,
                                               scope_statements_to_securities=True)
            end = diag['period_lineage'].get(symbol, {}).get('current')
            checks = []
            for table, field, metric in [('income','revenue','revenue'),
                                         ('income','n_income_attr_p','net_profit_parent'),
                                         ('cashflow','n_cashflow_act','operating_cashflow')]:
                for bucket in ('current','ttm'):
                    expected = expected_flow(facts,table,field,end,cutoff,bucket) if end else None
                    actual = panel.values(bucket,metric).get(symbol)
                    valid = actual is not None and np.isfinite(actual)
                    status = ('insufficient_original_evidence' if expected is None else
                              'passed' if valid and abs(Decimal(str(actual))-expected) <= Decimal('0.01') else 'mismatch')
                    checks.append(dict(input=bucket+'.'+metric,period=end,expected_yuan=expected,
                                       actual_yuan=float(actual) if valid else None,status=status))
            inputs = dependency_inputs(panel)
            evaluated = FinancialFactorEvaluator(panel).evaluate_latest()
            missing = {name: ['.'.join(key) for key in sorted(spec.required)
                             if not np.isfinite(inputs[key].get(symbol, np.nan))]
                       for name,spec in financial_dependencies().items()}
            results.append(dict(cutoff=cutoff,period_lineage=diag['period_lineage'].get(symbol),
                checks=checks,financial_factor_count=len(evaluated),
                finite_factor_outputs=sum(bool(np.isfinite(v.get(symbol, np.nan))) for v in evaluated.values()),
                missing_required_inputs={k:v for k,v in missing.items() if v},
                source_evidence=diag['official_filing_evidence']))
    return dict(generated_at=datetime.now(timezone.utc),symbol=symbol,results=results,
                policy='six_exact_flow_checks_only; finite_outputs_are_NOT_certified_factors; no_writes')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--symbol',required=True)
    parser.add_argument('--cutoffs',nargs='+',type=date.fromisoformat,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args()
    result = validate(args.symbol,args.cutoffs)
    args.output.write_text(json.dumps(result,default=str,ensure_ascii=False,indent=2)+'\n')
    for item in result['results']:
        print(item['cutoff'], item['period_lineage']['current'],
              {s:sum(c['status']==s for c in item['checks']) for s in ('passed','mismatch','insufficient_original_evidence')},
              'finite_factor_outputs',item['finite_factor_outputs'])
    sys.exit(1 if any(c['status']=='mismatch' for r in result['results'] for c in r['checks']) else 0)
