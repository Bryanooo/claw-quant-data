"""Explain D&A residuals from reviewed original filings, never publish factors.

An explanation needs every base component, an original-byte archive, aligned
disclosure dates, and exact arithmetic. It is not a provider definition or a
certification of the entire financial row. No zero-fill or fitted correction.
"""
import hashlib
from decimal import Decimal

from service.financial_reconciliation import day, number
from service.financial_filing_evidence import UNITS

CORE_FIELDS = (
    'depr_fa_coga_dpba', 'use_right_asset_dep',
    'amort_intang_assets', 'lt_amort_deferred_exp',
)
EXTRA_FIELDS = ('investment_property_daa', 'other_noncurrent_amortization')
TOLERANCE = Decimal('0.01')


def artifact_matches(document, artifact):
    raw = bytes(artifact.get('inline_content') or b'')
    return (raw.startswith(b'%PDF-') and artifact.get('artifact_id') == document['artifact_id']
            and artifact.get('content_type') == 'application/pdf'
            and artifact.get('source_id') == document['source_id']
            and artifact.get('source_url') == document['url']
            and artifact.get('content_hash') == document['sha256']
            and hashlib.sha256(raw).hexdigest() == document['sha256'])


def reconcile_interest_sign(document, income, indicator, artifact):
    """Explain a signed-filing/normalized-provider discrepancy, not which EBIT is official."""
    result = dict(symbol=document['symbol'], period=document['period'], status='unresolved',
                  artifact_id=document['artifact_id'], sha256=document['sha256'],
                  source_url=document['url'], pit_certified=False, factor_acceptance=False)
    if not artifact_matches(document, artifact):
        return dict(result, reason='original_artifact_mismatch')
    if document.get('scope') != 'consolidated' or document.get('unit') not in UNITS:
        return dict(result, reason='scope_or_unit_unverified')
    for row in (income, indicator):
        dates = [day(row[k]) for k in ('ann_date', 'f_ann_date') if row.get(k)]
        if (row.get('ts_code') != document['symbol'] or day(row.get('end_date')) != day(document['period'])
                or not dates or max(dates) != day(document['published_on'])):
            return dict(result, reason='identity_or_disclosure_mismatch')
    if str(income.get('report_type')) != '1':
        return dict(result, reason='income_scope_mismatch')
    fields = ('total_profit', 'fin_exp_int_exp', 'fin_exp_int_inc')
    facts = document.get('extracted_facts', [])
    if (len(facts) != len(fields) or {f['field'] for f in facts} != set(fields)
            or any(f.get('unit') != document['unit'] or not f.get('page') or not f.get('label') for f in facts)):
        return dict(result, reason='component_evidence_missing')
    original = {f['field']: number(f['current']) for f in facts}
    if any(original[f] is None or income.get(f) is None for f in fields) or indicator.get('ebit') is None:
        return dict(result, reason='missing_component')
    vendor = {f: number(income[f]) for f in fields}
    signed = original['total_profit'] + original['fin_exp_int_exp'] - original['fin_exp_int_inc']
    normalized = vendor['total_profit'] + vendor['fin_exp_int_exp'] - vendor['fin_exp_int_inc']
    result.update(filing_components=original, provider_components=vendor, reviewed_rows=facts,
                  signed_filing_arithmetic=signed, normalized_provider_arithmetic=normalized,
                  indicator_ebit=indicator['ebit'], raw_ebit_residual=number(indicator['ebit'])-normalized)
    if (original['fin_exp_int_inc'] < 0 < vendor['fin_exp_int_inc']
            and abs(original['fin_exp_int_inc'] + vendor['fin_exp_int_inc']) <= TOLERANCE
            and all(abs(original[f]-vendor[f]) <= TOLERANCE for f in fields[:2])
            and abs(number(indicator['ebit'])-signed) <= TOLERANCE):
        return dict(result, status='explained_sign_discrepancy',
                    reason='indicator_matches_signed_filing_but_income_field_has_opposite_sign',
                    unexplained_residual=number(indicator['ebit'])-signed,
                    provider_definition_verified=False)
    return dict(result, reason='no_verified_sign_bridge')


def reconcile_components(document, cashflow, indicator, artifact):
    """Use only the reviewed current-period column; do not mutate any input."""
    result = {
        'symbol': document['symbol'], 'period': document['period'],
        'artifact_id': document['artifact_id'], 'sha256': document['sha256'],
        'source_url': document['url'], 'status': 'unresolved',
        'pit_certified': False, 'factor_acceptance': False,
    }
    if not artifact_matches(document, artifact):
        return dict(result, reason='original_artifact_mismatch')
    if document.get('scope') != 'consolidated':
        return dict(result, reason='scope_unverified')
    if document.get('unit') not in UNITS:
        return dict(result, reason='unit_unverified')
    for name, row in [('cashflow', cashflow), ('indicator', indicator)]:
        if (row.get('ts_code') != document['symbol']
                or day(row.get('end_date')) != day(document['period'])):
            return dict(result, reason=name + '_identity_mismatch')
        dates = [day(row.get(k)) for k in ('ann_date', 'f_ann_date') if row.get(k)]
        if not dates or max(dates) != day(document['published_on']):
            return dict(result, reason=name + '_disclosure_mismatch')
    if str(cashflow.get('report_type')) != '1':
        return dict(result, reason='cashflow_scope_mismatch')
    facts = document.get('extracted_facts', [])
    values = {}
    for fact in facts:
        field = fact['field']
        if field in values or field not in CORE_FIELDS + EXTRA_FIELDS:
            return dict(result, reason='duplicate_or_unknown_component')
        if fact.get('unit') != document.get('unit') or not fact.get('page') or not fact.get('label'):
            return dict(result, reason='component_evidence_missing')
        values[field] = number(fact.get('current'))
    if (any(values.get(k) is None or cashflow.get(k) is None for k in CORE_FIELDS)
            or any(indicator.get(k) is None for k in ('ebit', 'daa', 'ebitda'))):
        return dict(result, reason='missing_component')
    internal = number(indicator['ebitda']) - number(indicator['ebit']) - number(indicator['daa'])
    if abs(internal) > TOLERANCE:
        return dict(result, reason='indicator_internal_identity_mismatch', internal_residual=internal)
    deltas = {k: number(cashflow[k]) - values[k] for k in CORE_FIELDS}
    provider_sum = sum(number(cashflow[k]) for k in CORE_FIELDS)
    original_sum = sum(values[k] for k in CORE_FIELDS)
    residual = number(indicator['daa']) - provider_sum
    result.update(provider_components={k: cashflow[k] for k in CORE_FIELDS},
                  filing_components=values, component_deltas=deltas,
                  indicator_daa=indicator['daa'], original_core_sum=original_sum,
                  raw_daa_residual=residual, internal_identity_residual=internal,
                  reviewed_rows=facts)
    extra = values.get('investment_property_daa')
    other = values.get('other_noncurrent_amortization')
    if (extra is not None and other is None and abs(extra) > TOLERANCE
            and all(abs(v) <= TOLERANCE for v in deltas.values())
            and abs(residual - extra) <= TOLERANCE):
        return dict(result, status='explained_component_difference',
                    reason='separate_investment_property_daa', unexplained_residual=residual-extra)
    if (other is not None and extra is None and abs(other) > TOLERANCE
            and abs(deltas[CORE_FIELDS[0]] - other) <= TOLERANCE
            and all(abs(deltas[k]) <= TOLERANCE for k in CORE_FIELDS[1:])
            and abs(number(indicator['daa']) - original_sum) <= TOLERANCE):
        return dict(result, status='explained_component_difference',
                    reason='provider_fixed_depreciation_includes_other_noncurrent_amortization',
                    unexplained_residual=number(indicator['daa'])-original_sum)
    return dict(result, reason='no_verified_component_bridge')
