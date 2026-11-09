from copy import deepcopy
import hashlib

import pytest

from service.financial_component_reconciliation import CORE_FIELDS, reconcile_components


def example(extra='investment_property_daa'):
    raw = b'%PDF-1.4 test-only original'
    digest = hashlib.sha256(raw).hexdigest()
    doc = dict(symbol='002594.SZ', period='2026-06-30', published_on='2026-08-29',
               artifact_id=1, sha256=digest, source_id='cninfo', url='https://example.invalid/original.pdf',
               scope='consolidated', unit='人民币元')
    doc['extracted_facts'] = [dict(field=f, current=v, page=1, label=f, unit=doc['unit'])
                              for f, v in zip(CORE_FIELDS + (extra,), (100, 10, 20, 30, 7))]
    identity = dict(ts_code=doc['symbol'], end_date=doc['period'], ann_date=doc['published_on'],
                    f_ann_date=doc['published_on'])
    cf = dict(identity, report_type=1, **dict(zip(CORE_FIELDS, (100, 10, 20, 30))))
    indicator = dict(identity, ebit=50, daa=167, ebitda=217)
    if extra == 'other_noncurrent_amortization':
        cf[CORE_FIELDS[0]] = 107
        indicator.update(daa=160, ebitda=210)
    artifact = dict(artifact_id=1, content_hash=digest, inline_content=raw, content_type='application/pdf',
                    source_id=doc['source_id'], source_url=doc['url'])
    return doc, cf, indicator, artifact


@pytest.mark.parametrize('extra,reason', [
    ('investment_property_daa', 'separate_investment_property_daa'),
    ('other_noncurrent_amortization', 'provider_fixed_depreciation_includes_other_noncurrent_amortization'),
])
def test_exact_original_component_bridge_is_not_factor_acceptance(extra, reason):
    args = example(extra)
    before = deepcopy(args)
    result = reconcile_components(*args)
    assert result['status'] == 'explained_component_difference'
    assert result['reason'] == reason
    assert result['unexplained_residual'] == 0
    assert not result['factor_acceptance'] and not result['pit_certified']
    assert args == before


@pytest.mark.parametrize('target,key,value,reason', [
    (0, 'unit', '美元', 'unit_unverified'),
    (0, 'scope', 'parent', 'scope_unverified'),
    (1, 'ts_code', '000001.SZ', 'cashflow_identity_mismatch'),
    (1, 'end_date', '2025-06-30', 'cashflow_identity_mismatch'),
    (1, 'f_ann_date', '2026-10-30', 'cashflow_disclosure_mismatch'),
    (1, 'report_type', 4, 'cashflow_scope_mismatch'),
    (2, 'ann_date', '2026-10-30', 'indicator_disclosure_mismatch'),
    (1, 'use_right_asset_dep', None, 'missing_component'),
    (2, 'daa', None, 'missing_component'),
    (2, 'ebitda', 999, 'indicator_internal_identity_mismatch'),
    (3, 'inline_content', b'%PDF-changed', 'original_artifact_mismatch'),
    (3, 'source_url', 'https://wrong.invalid/', 'original_artifact_mismatch'),
])
def test_invalid_or_mixed_evidence_fails_closed(target, key, value, reason):
    args = example()
    args[target][key] = value
    result = reconcile_components(*args)
    assert result['status'] == 'unresolved'
    assert result['reason'] == reason


def test_cancelled_component_differences_cannot_hide_behind_total_agreement():
    args = example()
    args[1][CORE_FIELDS[0]] += 1
    args[1][CORE_FIELDS[1]] -= 1
    assert reconcile_components(*args)['status'] == 'unresolved'


def test_comparative_value_is_never_used_and_missing_extra_is_not_zero():
    args = example()
    args[0]['extracted_facts'][-1].update(current=None, comparative=7)
    assert reconcile_components(*args)['status'] == 'unresolved'


def test_duplicate_field_is_not_last_value_wins():
    args = example()
    args[0]['extracted_facts'].append(args[0]['extracted_facts'][0])
    assert reconcile_components(*args)['reason'] == 'duplicate_or_unknown_component'


def test_interest_sign_requires_original_components_not_just_fitted_residual():
    from service.financial_component_reconciliation import reconcile_interest_sign
    doc, income, indicator, artifact = example()
    income.update(total_profit=100, fin_exp_int_exp=20, fin_exp_int_inc=3)
    indicator['ebit'] = 123
    doc['extracted_facts'] = [dict(field=f, current=v, page=1, label=f, unit=doc['unit'])
                              for f, v in [('total_profit', 100), ('fin_exp_int_exp', 20), ('fin_exp_int_inc', -3)]]
    result = reconcile_interest_sign(doc, income, indicator, artifact)
    assert result['status'] == 'explained_sign_discrepancy'
    assert result['raw_ebit_residual'] == 6
    assert not result['provider_definition_verified'] and not result['factor_acceptance']
    doc['extracted_facts'][0]['current'] = 101
    assert reconcile_interest_sign(doc, income, indicator, artifact)['status'] == 'unresolved'


def test_diagnostic_snapshot_is_repeatable_read_readonly_and_always_closed(monkeypatch):
    from scripts import diagnose_ebitda_bridge as script
    events = []

    class Cursor:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def execute(self, sql, params=None): events.append(sql)
        def fetchall(self): return [{'observed_at': 'now', 'database_snapshot': 'frozen'}]

    class Connection:
        def set_session(self, **kwargs): events.append(kwargs)
        def cursor(self, **kwargs): return Cursor()
        def rollback(self): events.append('rollback')
        def close(self): events.append('close')

    monkeypatch.setattr(script, 'get_conn', Connection)
    monkeypatch.setattr(script, '_diagnose', lambda *args: {'periods': []})
    assert script.diagnose([])['database_snapshot'] == 'frozen'
    assert events[0] == dict(isolation_level='REPEATABLE READ', readonly=True)
    assert events[-2:] == ['rollback', 'close']
    def fail(*args): raise RuntimeError('failed read')
    monkeypatch.setattr(script, '_diagnose', fail)
    with pytest.raises(RuntimeError): script.diagnose([])
    assert events[-2:] == ['rollback', 'close']


def test_original_explanation_does_not_hide_an_unexplained_other_component():
    from datetime import date
    from scripts.diagnose_ebitda_bridge import _diagnose
    doc, cf, indicator, artifact = example()
    income = dict(cf, total_profit=40, fin_exp_int_exp=13, fin_exp_int_inc=3)
    def query(sql, params=None):
        if 'source_raw_artifact' in sql: return [artifact]
        if 'FROM income' in sql: return [income]
        if 'FROM cashflow' in sql: return [cf]
        if 'FROM fina_indicator' in sql: return [indicator]
        raise AssertionError(sql)
    report = _diagnose([date(2026,6,30)], None, query, [doc])
    assert report['periods'][0]['counts']['same_disclosure_residual_explained_by_reviewed_filing'] == 1
    indicator.update(ebit=51, ebitda=218)
    report = _diagnose([date(2026,6,30)], None, query, [doc])
    assert report['periods'][0]['rows'][0]['reviewed_component_explanation']['status'].startswith('explained_')
    assert not report['periods'][0]['rows'][0]['reviewed_residual_explained']
    assert report['periods'][0]['counts']['same_disclosure_residual_still_unexplained'] == 1
