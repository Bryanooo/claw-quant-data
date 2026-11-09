from dataclasses import replace
from datetime import date

import pytest

from scripts.audit_task_contracts import representative_scope
from service.data_coverage.calculator import CoverageCalculator
from service.data_coverage.registry import COVERAGE_RULES
from service.data_coverage.repository import _producer_task
from service.orchestration_v2.audit_contracts import coverage_rule_audit_contract
from service.orchestration_v2.audit_runtime import TaskAuditRuntime
from tests.test_data_coverage import FakeCoverageRepository


@pytest.mark.parametrize('name,old_date,new_date', [('new_share',None,'ipo_date'),
    ('dividend','end_date','ann_date'),('stk_managers','begin_date','ann_date')])
def test_frozen_contract_migrates_to_request_date_without_changing_public_query_dates(name,old_date,new_date):
    from service.data_service.registry import DATASETS
    assert DATASETS.get(name).date_column==old_date
    current=coverage_rule_audit_contract(COVERAGE_RULES.get(name))
    assert current.date_column==new_date
    old=current.model_copy(update={'rule_revision':1,'date_column':old_date,
        'audit_mode':'observed_scope_transport' if old_date else 'exhaustive_snapshot',
        'period_granularity':'day' if old_date else 'snapshot'})
    assert TaskAuditRuntime(repository=object())._effective_contract(old)==current


def test_collection_certificate_belongs_to_producer_not_endpoint_alias():
    assert _producer_task(COVERAGE_RULES.get('financial_indicator'))=='financial_indicator'
    assert _producer_task(COVERAGE_RULES.get('industry_daily'))=='ths_daily'
    assert _producer_task(COVERAGE_RULES.get('cn_lpr'))=='cn_lpr'


@pytest.mark.parametrize('zero,expected',[(True,'empty'),(False,'unverified')])
def test_sparse_empty_requires_zero_response_evidence(zero,expected):
    class Repository(FakeCoverageRepository):
        def collection_scope_evidence(self,*args,**kwargs):
            return {**super().collection_scope_evidence(*args,**kwargs),'requested_scope_verified':True,'certified_zero_rows':zero}
    day=date(2026,11,3)
    result=CoverageCalculator(Repository()).audit(COVERAGE_RULES.get('dividend'),day,day)
    assert result.status==expected


def test_probe_uses_published_month_and_finished_week():
    day=date(2026,11,5)
    assert representative_scope(COVERAGE_RULES.get('cn_cpi'),day,'monthly')==(date(2026,9,1),date(2026,9,30))
    assert representative_scope(COVERAGE_RULES.get('cyq_perf'),day,'weekly')==(date(2026,10,26),date(2026,11,1))


def test_sparse_scope_uses_latest_execution_per_overlapping_date():
    from service.data_coverage.repository import _latest_scope_coverage
    a, b, c = [date(2026, 11, d) for d in (1, 2, 3)]
    def job(id_, start, end, valid, zero):
        return dict(task_execution_id=id_, observation_start=start, observation_end=end,
                    status='attention', transport_verified=valid, zero_rows=zero)
    old = job(1,a,c,True,True)
    failed = job(2,b,b,False,False)
    assert _latest_scope_coverage([old,failed],a,c) == (False,False,b)
    assert _latest_scope_coverage([old,failed,job(3,b,b,True,False)],a,c) == (True,False,None)
    assert _latest_scope_coverage([old,failed,job(3,b,b,True,True)],a,c) == (True,True,None)


def test_monthly_snapshot_probe_uses_scheduler_observation_dates():
    assert representative_scope(COVERAGE_RULES.get('broker_recommend'),date(2026,11,5),'monthly') == (
        date(2026,10,1), date(2026,10,31))


@pytest.mark.parametrize('dataset,column', [('fund_company',None),('fut_weekly_detail','week_date')])
def test_fund_directory_and_futures_weeks_follow_request_scope(dataset,column):
    assert COVERAGE_RULES.get(dataset).date_column == column
