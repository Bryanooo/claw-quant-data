from datetime import date
from scripts.plan_chip_security_repairs import plan_month
from scripts.chip_provider_gap_evidence import response_reason


def test_missing_request_evidence_is_not_a_verified_empty_response():
    assert response_reason({'rows_fetched':None,'completion_status':'complete'}) == 'provider_response_not_verified'
    assert response_reason({'rows_fetched':0,'completion_status':'partial'}) == 'provider_response_not_verified'
    assert response_reason({'rows_fetched':0,'completion_status':'complete'}) == 'provider_returned_empty'
    assert response_reason({'rows_fetched':'0','completion_status':'empty'}) == 'provider_returned_empty'


def test_active_window_splits_month_and_does_not_duplicate_security():
    days=[{'trade_date':f'2026-09-{d:02d}','missing_codes':['A','B']} for d in (1,2,3)]
    active=[dict(observation_start=date(2026,9,2),observation_end=date(2026,9,2),fanout_values=['A'])]
    result=plan_month(days,active)
    assert [item[2] for item in result]==[['A','B'],['B'],['A','B']]
    assert sum(item[3] for item in result)==5


def test_existing_market_wide_scope_suppresses_all_pairs():
    days=[{'trade_date':'2026-10-30','missing_codes':['A','B']}]
    active=[dict(observation_start=date(2026,10,26),observation_end=date(2026,10,30),fanout_values=None)]
    assert plan_month(days,active)==[]
