from scripts.trace_factor_financial_inputs import explain
from service.data_coverage.registry import COVERAGE_RULES
from service.data_service.registry import DATASETS


def test_financial_probe_detects_conflicting_null_without_imputing(monkeypatch):
    from datetime import date
    from scripts.trace_factor_financial_inputs import compare_archived_probe
    base = dict(ts_code='600621.SH', report_type='1',ann_date='20261030',f_ann_date='20261030')
    monkeypatch.setattr('scripts.trace_factor_financial_inputs.query', lambda *args: [])
    result=compare_archived_probe(dict(api='balancesheet_vip',field='fix_assets',period='20260930',
        pagination_exhausted=True,rows=2,records=[dict(base,fix_assets=None),dict(base,fix_assets=9)]),
        date(2026,10,30))
    assert result['counts']=={'provider_null_rows':1,'exact_revision_not_matched':1}
    assert result['unmatched'][0]['conflicting_provider_values'] is True


def test_pit_block_is_not_a_supplier_null():
    assert explain([], [{'available_on':'2026-11-03','value':123}])=='no_eligible_version_as_of'
    assert explain([{'value':None}],[])=='visible_version_field_null'
    assert explain([{'value':0}],[])=='visible_value'
    assert explain([],[])=='no_archived_consolidated_version'


def test_pro_read_and_strict_audit_use_same_identity():
    assert DATASETS.get('stk_factor_pro').read_table == COVERAGE_RULES.get('stk_factor_pro').table == 'canonical_stk_factor_pro'
    assert COVERAGE_RULES.get('stk_factor_pro').min_entity_ratio == 1
