"""Explain cross-provider financial formula differences; never publish factors."""
import argparse
from collections import Counter
from datetime import date
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from psycopg2.extras import RealDictCursor
from service.db import get_conn
from service.financial_reconciliation import day, ebitda_bridge, number
from service.financial_component_reconciliation import reconcile_components, reconcile_interest_sign


def indicator_evidence(income, indicator, bridge):
    """Keep formula residuals separate from mismatched publication versions."""
    statement_dates = [day(income.get(k)) for k in ('ann_date', 'f_ann_date') if income.get(k)]
    statement_date = max(statement_dates) if statement_dates else None
    indicator_date = day(indicator.get('ann_date'))
    status = (
        'publication_unknown' if statement_date is None or indicator_date is None else
        'disclosure_mismatch' if statement_date != indicator_date else
        'same_disclosure_not_revision_proof'
    )
    evidence = dict(statement_disclosure=statement_date, indicator_disclosure=indicator_date,
                    indicator_version_status=status, pit_certified=False)
    if bridge['status'] == 'diagnostic_not_official_formula':
        for field, target in [('ebit', 'ebit_net_interest'), ('daa', 'depreciation_amortization')]:
            if indicator.get(field) is not None:
                evidence['indicator_' + field + '_minus_bridge'] = number(indicator[field]) - bridge[target]
        if all(indicator.get(k) is not None for k in ('ebit', 'daa', 'ebitda')):
            evidence['indicator_internal_identity_residual'] = (
                number(indicator['ebitda']) - number(indicator['ebit']) - number(indicator['daa']))
        # Triage only: equality is not evidence of the provider's formula.
        # Original filing signs and scope still require separate verification.
        if indicator.get('ebit') is not None:
            ebit = number(indicator['ebit'])
            if all(income.get(k) is not None for k in ('total_profit', 'fin_exp_int_exp', 'fin_exp_int_inc')):
                candidate = (number(income['total_profit']) + number(income['fin_exp_int_exp'])
                             + number(income['fin_exp_int_inc']))
                evidence['interest_sign_hypothesis_residual'] = ebit - candidate
                evidence['interest_sign_hypothesis_matches'] = (
                    abs(ebit-candidate) <= number('0.01') and
                    abs(ebit-bridge['ebit_net_interest']) > 1)
            if income.get('total_profit') is not None and income.get('fin_exp') is not None:
                evidence['total_finance_expense_hypothesis_residual'] = (
                    ebit - number(income['total_profit']) - number(income['fin_exp']))
    return evidence


def diagnose(periods, universe_date=None, documents=()):
    """Freeze all source versions together; refreshes must not create false residuals."""
    conn = get_conn()
    try:
        conn.set_session(isolation_level='REPEATABLE READ', readonly=True)
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SET LOCAL statement_timeout = '120s'")

            def query(sql, params=None):
                cur.execute(sql, params)
                return [dict(row) for row in cur.fetchall()]

            snapshot = query('SELECT transaction_timestamp() AS observed_at, '
                             'txid_current_snapshot()::text AS database_snapshot')[0]
            return dict(_diagnose(periods, universe_date, query, documents), **snapshot)
    finally:
        conn.rollback()
        conn.close()


def _diagnose(periods, universe_date, query, documents=()):
    reviewed = {}
    for doc in documents:
        key = (doc['symbol'], day(doc['period']))
        if key in reviewed:
            raise ValueError('ambiguous reviewed evidence for security and period')
        reviewed[key] = doc
    traded_codes = ({r['ts_code'] for r in query('SELECT ts_code FROM daily WHERE trade_date=%s', (universe_date,))}
                    if universe_date else None)
    reports=[]
    for period in periods:
        tables={table:{r['ts_code']:r for r in query(
            f'SELECT * FROM {table} WHERE end_date=%s'+('' if table=='fina_indicator' else ' AND report_type=1'),(period,))}
            for table in ('income','cashflow','fina_indicator')}
        rows=[]
        for code,inc in sorted(tables['income'].items()):
            cf=tables['cashflow'].get(code,{})
            result=ebitda_bridge(inc,cf)
            result.update(symbol=code,period=period)
            if traded_codes is not None:
                result['observed_in_daily_on_universe_date'] = code in traded_codes
            indicator=tables['fina_indicator'].get(code,{})
            result.update(indicator_evidence(inc, indicator, result))
            if result['status']=='diagnostic_not_official_formula' and all(inc.get(k) is not None for k in ('ebit','ebitda')):
                result['income_ebitda_minus_ebit_and_component_daa'] = (
                    number(inc['ebitda'])-number(inc['ebit'])-result['depreciation_amortization'])
            for label,value in [('income_ebitda',inc.get('ebitda')),('indicator_ebitda',indicator.get('ebitda'))]:
                result[label]=value
                if value is not None and result['status']=='diagnostic_not_official_formula':
                    result[label+'_minus_net_interest_bridge']=number(value)-result['ebitda_net_interest']
                    result[label+'_minus_gross_interest_bridge']=number(value)-result['ebitda_gross_interest']
            doc = reviewed.get((code, day(period)))
            if doc:
                artifacts = query('SELECT * FROM source_raw_artifact WHERE artifact_id=%s', (doc['artifact_id'],))
                interest = doc.get('diagnostic') == 'interest_sign'
                reconcile = reconcile_interest_sign if interest else reconcile_components
                explanation = reconcile(doc, inc if interest else cf, indicator, artifacts[0] if artifacts else {})
                result['reviewed_component_explanation'] = explanation
                # Explain this residual only, never financial product readiness.
                other = result.get('indicator_daa_minus_bridge' if interest else 'indicator_ebit_minus_bridge')
                internal = result.get('indicator_internal_identity_residual')
                result['reviewed_residual_explained'] = bool(
                    explanation['status'].startswith('explained_')
                    and result['indicator_version_status'] == 'same_disclosure_not_revision_proof'
                    and other is not None and abs(other) <= number('0.01')
                    and internal is not None and abs(internal) <= number('0.01'))
            rows.append(result)
        counts=Counter(r['status'] for r in rows)
        counts.update('indicator_version_' + r['indicator_version_status'] for r in rows)
        for label in ('income_ebitda','indicator_ebitda'):
            key=label+'_minus_net_interest_bridge'
            counts[label+'_net_interest_equal']=sum(key in r and abs(r[key])<=1 for r in rows)
            counts[label+'_net_interest_compared']=sum(key in r for r in rows)
        residual_key='indicator_ebitda_minus_net_interest_bridge'
        residuals=[r for r in rows if residual_key in r and abs(r[residual_key])>1]
        counts.update('indicator_residual_' + r['indicator_version_status'] for r in residuals)
        counts['same_disclosure_residual_explained_by_reviewed_filing'] = sum(
            r.get('reviewed_residual_explained', False) for r in residuals)
        counts['same_disclosure_residual_still_unexplained'] = sum(
            r['indicator_version_status']=='same_disclosure_not_revision_proof'
            and not r.get('reviewed_residual_explained', False) for r in residuals)
        if traded_codes is not None:
            counts['indicator_residual_in_observed_daily_universe'] = sum(
                r['observed_in_daily_on_universe_date'] for r in residuals)
            counts['same_disclosure_residual_in_observed_daily_universe'] = sum(
                r['observed_in_daily_on_universe_date'] and
                r['indicator_version_status']=='same_disclosure_not_revision_proof' for r in residuals)
        reports.append(dict(period=period,counts=dict(counts),rows=rows))
    return {'policy':'formula_hypotheses_not_provider_definition_or_PIT_proof',
            'observed_daily_universe_date':universe_date,
            'universe_note':'Exact daily rows on the chosen date, not all listed/security-master eligibility; untraded residuals remain in the report.',
            'periods':reports}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--periods',nargs='+',type=date.fromisoformat,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--universe-date',type=date.fromisoformat)
    p.add_argument('--filing-facts', nargs='*', type=Path, default=[])
    args=p.parse_args()
    documents=[doc for path in args.filing_facts for doc in json.loads(path.read_text())['documents']]
    report=diagnose(args.periods,args.universe_date,documents)
    args.output.write_text(json.dumps(report,default=str,ensure_ascii=False,indent=2)+'\n')
    for period in report['periods']: print(period['period'],period['counts'])
