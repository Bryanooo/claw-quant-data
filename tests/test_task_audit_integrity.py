from dataclasses import replace
from datetime import date
from decimal import Decimal

import psycopg2
import pytest

from scripts.audit_task_contracts import inventory
from service.acquisition_runtime.reliability import classify_failure
from service.data_coverage.calculator import CoverageCalculator
from service.data_coverage.diagnostics import audit_issues
from service.data_coverage.models import ActualPartition
from service.data_coverage.registry import COVERAGE_RULES
from service.data_coverage.transport import transport_manifest
from service.ggt_monthly import aggregate_month
from service.orchestration_v2.audit_runtime import TaskAuditRuntime
from service.orchestration_v2.contracts import TaskDefinitionDocument
from service.orchestration_v2.service import DefinitionPublishError, OrchestrationV2Service
from tests.test_data_coverage import FakeCoverageRepository
from tests.test_orchestration_v2 import FakeRepository, HANDLERS, transformation_definition
from tests.test_orchestration_v2_audit_runtime import FakeCalculator, FakeRegistry

DAY = date(2026, 10, 30)


def proof(key='a', **changes):
    result = {'request_key': key, 'completion_status': 'complete',
              'completion_evidence': {'verified': True}, 'rows_fetched': 10, 'rows_inserted': 10}
    result.update(changes)
    return result


@pytest.mark.parametrize('records,expected', [
    ([proof()], False),
    ([proof(), proof('b')], True),
    ([proof(), proof('b'), proof('b', completion_status='incomplete')], False),
    ([proof(), proof('b', completion_evidence={'verified': True, 'skip_store': True})], False),
    ([proof(), proof('b', completion_evidence={'verified': True, 'normalization': {'quarantined_rows': 1}})], False),
    ([proof(), proof('b', completion_evidence={'verified': True, 'normalization': {'complete': False}})], False),
])
def test_manifest_requires_every_frozen_request_and_latest_good_store(records, expected):
    result = transport_manifest(records, [{'request_key': 'a'}, {'request_key': 'b'}])
    assert result['verified'] is expected


def test_manifest_empty_duplicate_and_legacy_plans_fail_closed():
    legacy = proof(); legacy.pop('request_key')
    assert transport_manifest([legacy], [{'request_key': 'a'}])['verified']
    assert not transport_manifest([legacy], [{'request_key': 'a'}, {'request_key': 'b'}])['verified']
    assert not transport_manifest([proof()], [])['verified']
    assert not transport_manifest([proof()], [{'request_key': 'a'}, {'request_key': 'a'}])['verified']


@pytest.mark.parametrize('denominator', [None, 0])
def test_unknown_security_denominator_is_partial_with_specific_reason(denominator):
    repo = FakeCoverageRepository(actual=[ActualPartition(DAY,100,100)],expected=[DAY],expected_entities=denominator)
    result = CoverageCalculator(repo).audit(COVERAGE_RULES.get('stock_daily'),DAY,DAY,as_of=date(2026,11,5))
    assert result.status == 'gaps' and result.partial_partitions == 1
    assert 'entity_reference_unavailable' in {i['code'] for i in audit_issues(result)}


def test_unrelated_success_cannot_certify_sparse_scope():
    class Repository(FakeCoverageRepository):
        def collection_scope_evidence(self, rule, **kwargs):
            assert kwargs == {'start_date': DAY, 'end_date': DAY}
            return {**super().collection_scope_evidence(rule), 'requested_scope_verified': False}
    result = CoverageCalculator(Repository()).audit(COVERAGE_RULES.get('dividend'),DAY,DAY)
    assert result.status == 'unverified'


def test_invalid_physical_row_is_present_partial_not_missing():
    repo = FakeCoverageRepository(actual=[ActualPartition(DAY,1,None,known_incomplete=True,invalid_value_rows=1)], expected=[DAY])
    result = CoverageCalculator(repo).audit(COVERAGE_RULES.get('fama_french_daily'),DAY,DAY,as_of=date(2026,11,5))
    assert result.missing_partitions == 0 and result.partial_partitions == 1
    assert audit_issues(result)[0]['code'] == 'invalid_business_values'


def test_daily_basic_alias_cannot_bypass_security_or_transport_checks():
    alias, canonical = (COVERAGE_RULES.get(n) for n in ('daily_basic','stock_daily_basic'))
    assert replace(alias,dataset_name=canonical.dataset_name,scheduled=canonical.scheduled) == canonical


def test_wrapped_database_and_transform_errors_have_actionable_categories():
    outer = RuntimeError('collector failed')
    outer.__cause__ = psycopg2.errors.NotNullViolation('bad ts_code')
    assert classify_failure(outer) == 'storage'
    from service.orchestration_v2.runtime import V2TransformationNotPublishableError
    assert classify_failure(V2TransformationNotPublishableError('missing factor inputs')) == 'data_incomplete'


def test_all_task_outputs_have_executable_audit_or_are_blocked_drafts():
    records = inventory()
    assert len(records) == 216 and len({r['task_key'] for r in records}) == 216
    for record in records:
        if record['handler_implemented']:
            assert all(o['implemented'] for o in record['outputs']), record['task_key']
        else:
            assert record['review'] == 'draft_blocked_at_publish'
        for output in record['outputs']:
            rule = output.get('rule')
            if rule and record['kind'] == 'acquisition' and rule['strategy'].value not in {'observed_only','non_temporal'}:
                assert rule['require_transport_proof'], output['dataset']


def test_unimplemented_transform_cannot_be_published_as_active():
    document = TaskDefinitionDocument.model_validate(transformation_definition())
    repo = FakeRepository(document)
    repo.active_task_keys = lambda: {'daily', 'adj_factor'}
    service = OrchestrationV2Service(repo,allowed_handler_keys=HANDLERS,
                                     known_datasets={'stock_daily','adj_factor','adjusted_price_return'})
    with pytest.raises(DefinitionPublishError, match='implementation is not available'):
        service.publish_definition(11,actor='test',app_revision='test',image_digest='sha256:test')
    assert repo.published is None


def source_row(day=DAY, value='12'):
    return {'trade_date':day, **{f:value for f in ('buy_amount','buy_volume','sell_amount','sell_volume')}}


def test_monthly_means_and_totals_use_observed_connect_days():
    result = aggregate_month([source_row(),source_row(date(2026,10,29),'18')], DAY)
    assert result['month'] == '202610'
    assert result['day_buy_amt'] == Decimal('15')
    assert result['total_sell_vol'] == Decimal('30')


@pytest.mark.parametrize('rows', [[],[source_row(),source_row()], [source_row(date(2026,9,30))],
                                 [source_row(value=None)],[source_row(value='NaN')],
                                 [source_row(value='Infinity')],[source_row(value='-1')]])
def test_monthly_bad_sources_never_generate_a_publishable_row(rows):
    with pytest.raises(ValueError):
        aggregate_month(rows,DAY)


def test_cyclic_exception_context_does_not_recurse_forever():
    a, b = RuntimeError('outer'), RuntimeError('inner')
    a.__cause__, b.__cause__ = b, a
    assert classify_failure(a) == 'upstream_or_internal'


def test_old_reference_replay_cannot_turn_collection_holes_into_supplier_absence(monkeypatch):
    from service.orchestration_v2 import factor_reference as reference
    from tests.test_factor_reference_workflow import execution
    names = [spec.name for spec in reference.FACTOR_SPECS]
    monkeypatch.setattr(reference, 'query', lambda *args: [
        {'manifest': {'ts_code': f'{i:06d}.SZ', 'trade_date': '20261030',
                      'verified': True, 'reference_response_manifest': True,
                      'source': 'historical_db', 'returned_keys': names[:-1],
                      'supplier_missing_keys': names[-1:], 'explicit_null_keys': []}}
        for i in range(30)])
    result, state, _ = reference.audit_sample(execution())[0]
    assert not state.ready and result.missing_partitions == 30


def audited_runtime(mode, result):
    from types import SimpleNamespace
    from service.orchestration_v2.audit_contracts import coverage_rule_audit_contract
    from tests.test_orchestration_v2_audit_runtime import FakeRule
    from tests.test_orchestration_v2 import acquisition_definition
    from service.data_coverage.models import CoverageStrategy
    rule=FakeRule()
    rule.strict_audit_mode=mode
    if mode == 'exhaustive_snapshot':
        rule.date_column=None
    rule.strategy={'expected_partition':CoverageStrategy.TRADING_DAILY,
                   'observed_scope_transport':CoverageStrategy.OBSERVED_ONLY,
                   'exhaustive_snapshot':CoverageStrategy.NON_TEMPORAL}[mode]
    runtime=TaskAuditRuntime(repository=object(),registry=FakeRegistry(rule))
    runtime._calculator=SimpleNamespace(audit=lambda *args,**kwargs:result)
    definition=acquisition_definition()
    definition['validation_contract']['dataset_audits']=[coverage_rule_audit_contract(rule).model_dump(mode='json')]
    return runtime,TaskDefinitionDocument.model_validate(definition)


def base_result(**changes):
    from service.data_coverage.models import CoverageAuditResult
    result=CoverageAuditResult(dataset_name='stock_daily_basic',strategy='observed_only',
        start_date=DAY,end_date=DAY,status='complete',expected_partitions=1,present_partitions=1,
        missing_partitions=0,observed_partitions=1,coverage_ratio=1,partitions=(),evidence={})
    return replace(result,**changes)


def test_missing_request_cannot_borrow_previous_complete_business_verdict():
    runtime,document=audited_runtime('expected_partition',base_result())
    result,state=runtime.audit_output(document,dataset_name='stock_daily_basic',observation_key=str(DAY),
        start_date=DAY,end_date=DAY,transport_evidence=[proof()],
        expected_requests=[{'request_key':'a'},{'request_key':'b'}])
    assert not state.ready and result.status=='unverified'
    assert result.evidence['issues'][0]['missing_request_keys']==['b']


def test_sparse_transport_success_does_not_overwrite_partial_business_data():
    runtime,document=audited_runtime('observed_scope_transport',base_result(status='gaps',partial_partitions=1,present_partitions=0))
    result,state=runtime.audit_output(document,dataset_name='stock_daily_basic',observation_key=str(DAY),
        start_date=DAY,end_date=DAY,transport_evidence=[proof()],expected_requests=[{'request_key':'a'}])
    assert result.partial_partitions==1 and not state.ready and state.data_status.value=='partial'


def test_empty_snapshot_response_cannot_certify_stale_physical_rows():
    runtime,document=audited_runtime('exhaustive_snapshot',base_result(evidence={'row_count':3}))
    result,state=runtime.audit_output(document,dataset_name='stock_daily_basic',observation_key=str(DAY),
        start_date=DAY,end_date=DAY,transport_evidence=[proof(rows_fetched=0,rows_inserted=0)],expected_requests=[{'request_key':'a'}])
    assert not state.ready and result.evidence['issues'][0]['code']=='snapshot_response_storage_mismatch'


def test_missing_calendar_is_diagnosed_as_calendar_error_not_zero_obligation_success():
    runtime,document=audited_runtime('expected_partition',base_result(status='unverified',expected_partitions=0,evidence={'calendar_complete_for_range':False}))
    result,state=runtime.audit_output(document,dataset_name='stock_daily_basic',observation_key=str(DAY),
        start_date=DAY,end_date=DAY,transport_evidence=[proof()],expected_requests=[{'request_key':'a'}])
    assert not state.ready and 'calendar_incomplete' in {i['code'] for i in audit_issues(result)}


@pytest.mark.parametrize('today,source_status,created', [('2026-11-01','complete',0),('2026-11-05','gaps',0),('2026-11-05','complete',1)])
def test_monthly_dispatch_uses_closed_month_and_complete_source(monkeypatch,today,source_status,created):
    from datetime import datetime
    from types import SimpleNamespace
    from service import ggt_monthly
    from service.orchestration_v2 import scheduling
    class Repository:
        requests=[]
        def active_task_keys(self): return {'ggt_monthly'}
        def auxiliary_input_revision(self,names,end): return {'pending_count':0,'revision_digest':'source-v1'}
        def create_execution(self,request): self.requests.append(request);return {},True
    repo=Repository()
    monkeypatch.setattr(scheduling,'business_now',lambda:datetime.fromisoformat(today+'T12:00:00+08:00'))
    monkeypatch.setattr(ggt_monthly,'source_audit',lambda day:SimpleNamespace(status=source_status))
    result=scheduling.dispatch_ready_transformations(repository=repo)
    assert result['created']==created and not result['errors']
    if created:
        assert repo.requests[0].observation_start==date(2026,10,1)
        assert repo.requests[0].observation_end==date(2026,10,31)
        assert repo.requests[0].observation_key=='2026-10'
