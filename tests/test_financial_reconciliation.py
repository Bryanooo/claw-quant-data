from datetime import date
from decimal import Decimal

import pytest

from service.financial_reconciliation import (
    BALANCE_ROUTE, FLOW_ROUTE, ebitda_bridge, numeric_status, reconcile,
)


@pytest.mark.parametrize('a,b,unit,expected', [
    (None,None,None,'both_missing'), (10,None,'人民币元','provider_missing'),
    (None,10,'人民币元','local_missing_candidate'), (10,10,None,'unit_unverified'),
    (10,10,'港元','unit_unverified'), (0,0,'人民币元','value_agreement'),
    (10,10.01,'人民币元','value_agreement'), (10,10.02,'人民币元','value_mismatch'),
    (10**12,10**12+100,'人民币元','value_mismatch'),
    (float('nan'),1,'人民币元','invalid_number'),
    (1,float('inf'),'人民币元','invalid_number'),
])
def test_numeric_contract(a,b,unit,expected):
    assert numeric_status(a,b,unit)==expected


def evidence():
    fields = ['symbol','report_period','report_period_end','disclosure_date','total_assets']
    return {'status':'SUCCESS','results':[
        {'url':BALANCE_ROUTE,'meta':{'fields':fields,'unit':{'total_assets':'人民币元'}},
         'data':[['300750.SZ','2025-12-31','2025-12-31','2026-10-21',100]]},
        {'url':FLOW_ROUTE,'meta':{'fields':[]},'data':[]}]}


def compare(response):
    return reconcile(response,{'balancesheet':[dict(ts_code='300750.SZ',end_date='20251231',
        ann_date='20260310',report_type=1,total_assets=100)]},symbols=['300750.SZ'],
        periods=['2025-12-31'],cutoff=date(2026,10,8))


def test_equal_latest_values_do_not_certify_historical_availability():
    rows=compare(evidence())['results']
    asset=next(r for r in rows if r['field']=='total_assets')
    assert asset['status']=='value_agreement'
    assert asset['version_status']=='after_cutoff'
    assert not asset['pit_certified']
    assert sum(r['status']=='provider_row_missing' for r in rows)==7


@pytest.mark.parametrize('column,value', [(0,'AAPL.US'),(1,'2026-03-31'),(2,'2025-12-30')])
def test_wrong_security_period_or_actual_end_is_rejected(column,value):
    response=evidence();response['results'][0]['data'][0][column]=value
    with pytest.raises(ValueError): compare(response)


def test_duplicates_cannot_be_resolved_by_response_order():
    response=evidence()
    response['results'][0]['data']*=2
    assert compare(response)['counts']['duplicate_identity']==5


@pytest.mark.parametrize('status',['FAILED','PARTIAL','RUNNING'])
def test_successful_envelope_cannot_hide_failed_route(status):
    from service.source_connectors.financial_data import FinancialDataProtocolError
    response=evidence();response['results'][0]['status']=status
    with pytest.raises(FinancialDataProtocolError): compare(response)


def test_ebitda_components_and_semantics():
    identity=dict(ts_code='300750.SZ',end_date='20251231',ann_date='20260310',
                  f_ann_date='20260310',report_type=1)
    inc=dict(identity,total_profit=89526545000,fin_exp_int_exp=2734017000,fin_exp_int_inc=10594657000)
    cf=dict(identity,depr_fa_coga_dpba=24322780000,amort_intang_assets=512000000,
            lt_amort_deferred_exp=1764508000,use_right_asset_dep=337367000)
    result=ebitda_bridge(inc,cf)
    assert result['depreciation_amortization']==Decimal('26936655000')
    assert result['ebitda_net_interest']==Decimal('108602560000')
    assert result['ebitda_gross_interest']==Decimal('119197217000')
    assert result['status']=='diagnostic_not_official_formula'
    cf['use_right_asset_dep']=None
    assert ebitda_bridge(inc,cf)=={'status':'missing_components','missing':['use_right_asset_dep']}
    cf['f_ann_date']='20261021'
    assert ebitda_bridge(inc,cf)['status']=='statement_identity_mismatch'


def test_collectors_request_real_source_fields_and_keep_definitions_separate():
    from collectors.stock.finance.cashflow import CashflowCollector
    from collectors.stock.finance.income import IncomeCollector
    assert 'financian_exp' not in CashflowCollector.CORE_FIELDS
    assert {'finan_exp','amort_intang_assets','lt_amort_deferred_exp','use_right_asset_dep'} <= set(CashflowCollector.CORE_FIELDS)
    assert {'fin_exp_int_exp','fin_exp_int_inc'} <= set(IncomeCollector.CORE_FIELDS)


def test_indicator_diagnostics_preserve_version_and_component_residuals():
    from scripts.diagnose_ebitda_bridge import indicator_evidence
    bridge = dict(status='diagnostic_not_official_formula', ebit_net_interest=Decimal(10),
                  depreciation_amortization=Decimal(4))
    result = indicator_evidence({'ann_date': '20260401', 'f_ann_date': '20260402'},
                                {'ann_date': '20260901', 'ebit': 11, 'daa': 6, 'ebitda': 17}, bridge)
    assert result['indicator_version_status'] == 'disclosure_mismatch'
    assert result['indicator_ebit_minus_bridge'] == 1
    assert result['indicator_daa_minus_bridge'] == 2
    assert result['indicator_internal_identity_residual'] == 0
    assert not result['pit_certified']
    assert indicator_evidence({}, {}, bridge)['indicator_version_status'] == 'publication_unknown'


def test_filing_verification_keeps_total_separate_and_requires_archived_hash(monkeypatch):
    from scripts import verify_financial_filing_facts as verifier
    statements = []
    def query(sql, params):
        statements.append(sql)
        return ([{'content_hash': 'reviewed'}] if 'source_raw_artifact' in sql else
                [{'value': 42, 'ann_date': date(2026, 10, 21), 'f_ann_date': date(2026, 10, 21)}])
    monkeypatch.setattr(verifier, 'query', query)
    doc = dict(artifact_id=2, sha256='reviewed', symbol='300750.SZ', period='2026-09-30',
               url='https://example.invalid/original.pdf', published_on='2026-10-21',
               extracted_facts=[dict(field='reported_fixed_assets_line', page=6, current='42')])
    result = verifier.verify([doc])
    assert 'SELECT fix_assets_total AS value' in statements[1]
    assert result['counts'] == {'value_agreement': 1}
    assert not result['results'][0]['pit_certified']
    with pytest.raises(ValueError, match='retained'):
        verifier.verify([dict(doc, sha256='different')])


def test_filing_rows_keep_units_and_fail_closed_for_ambiguous_or_blank_columns():
    from service.financial_filing_evidence import extract_two_column_row
    row='无形资产摊销 512,000 470,401\n'
    assert extract_two_column_row(row,'无形资产摊销',unit='人民币千元')['current']==512000000
    for invalid in (row*2, '无形资产摊销 512,000\n', '无形资产摊销 -- 470,401\n',
                    '无形资产摊销 51,20,00 470,401\n'):
        with pytest.raises(ValueError):
            extract_two_column_row(invalid,'无形资产摊销',unit='人民币千元')
    with pytest.raises(ValueError):
        extract_two_column_row(row,'无形资产摊销',unit='美元')


def test_multiline_label_does_not_take_parent_or_similar_label():
    from service.financial_filing_evidence import extract_two_column_row
    text='固定资产折旧、油气资产折\n耗、生产性生物资产折旧 24,322,780 22,437,872\n固定资产 146,400,592 112,589,053\n'
    fact=extract_two_column_row(text,'固定资产折旧、油气资产折耗、生产性生物资产折旧',unit='人民币千元')
    assert fact['current']==24322780000
