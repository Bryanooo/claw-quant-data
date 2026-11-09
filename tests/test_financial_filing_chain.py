from datetime import date
from decimal import Decimal

from scripts.validate_financial_filing_chain import expected_flow, original_value


def row(period, value, **kwargs):
    return dict(statement_table='income',field_name='revenue',end_date=date.fromisoformat(period),
                value_yuan=Decimal(value),published_on=date(2026,7,25),available_on=date(2026,7,26),
                **kwargs)


def test_decimal_ttm_and_single_quarter_require_exact_periods_and_cutoff():
    facts = [row('2026-06-30','200'),row('2026-03-31','80'),
             row('2025-12-31','300'),row('2025-06-30','100')]
    args = ('income','revenue','2026-06-30',date(2026,10,8))
    assert expected_flow(facts,*args,'ttm') == 400
    assert expected_flow(facts,*args,'current') == 120
    assert expected_flow(facts[:-1],*args,'ttm') is None
    assert expected_flow(facts,'income','revenue','2026-06-30',date(2026,7,25),'ttm') is None


def test_original_reference_cannot_mix_versions_or_resurrect_revoked_value():
    old = row('2026-06-30','200')
    new = dict(old,field_name='oper_cost',published_on=date(2026,8,1),available_on=date(2026,8,2))
    args = ('income','revenue','2026-06-30',date(2026,10,8))
    assert original_value([old,new],*args) is None
    assert original_value([dict(old,revoked_at=date(2026,8,1))],*args) is None
    assert original_value([old,dict(old,value_yuan=201)],*args) is None
