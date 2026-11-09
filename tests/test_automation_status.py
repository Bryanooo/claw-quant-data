from datetime import date

from service.orchestration_v2.automation_status import task_automation, WEEKLY_REFERENCE_PROFILES
from service.orchestration_v2.scheduling import dispatch_weekly_reference_profiles
from service.data_service.dependencies import merge_runtime
import pytest
from service.orchestration_v2.runtime import OrchestrationV2Runtime, V2UnsupportedScopeError
from service.orchestration_v2.contracts import TaskDefinitionDocument
from tests.test_orchestration_v2 import acquisition_definition


def test_registered_and_published_are_not_automatic():
    disabled = {'schedule': {'mode': 'disabled'}}
    assert task_automation('stk_mins', disabled, [])['automatic'] is False
    assert task_automation('index_weight', disabled, [])['automatic'] is False
    item = task_automation('index_weight', disabled, ['valuation_percentile_snapshot'])
    assert item['scope'] == ['000300.SH', '000688.SH']
    assert item['automatic'] is True
    assert not task_automation('factor_value', {'schedule': {'mode': 'cron'}}, [])['automatic']
    assert task_automation('factor_reference_sample', disabled, [])['automatic']


def test_missing_runtime_is_unknown_not_enabled():
    item = {'source': 'tushare', 'tasks': [{'task_key': 'index_weight'}], 'datasets': []}
    assert merge_runtime([item], {}, {})[0]['automation'][0]['automatic'] is None
    assert merge_runtime([item], {}, {}, {})[0]['automation'][0]['state'] == 'not_published'


def test_reference_profiles_are_bounded_and_week_idempotent():
    class Store:
        requests = []
        def active_task_keys(self):
            return set(WEEKLY_REFERENCE_PROFILES)
        def create_execution(self, request):
            self.requests.append(request)
            return {}, True
    store = Store()
    dispatch_weekly_reference_profiles(date(2026,10,30), repository=store)
    dispatch_weekly_reference_profiles(date(2026,10,31), repository=store)
    assert len(store.requests) == 8
    assert [r.idempotency_key for r in store.requests[:4]] == [r.idempotency_key for r in store.requests[4:]]
    assert len(WEEKLY_REFERENCE_PROFILES['fut_basic']) == 6
    assert {r['market'] for r in WEEKLY_REFERENCE_PROFILES['fund_basic']} == {'E','O'}


def test_reference_dispatch_failure_does_not_block_other_profiles():
    class Store:
        def active_task_keys(self):
            return set(WEEKLY_REFERENCE_PROFILES)
        def create_execution(self, request):
            if request.task_key == 'fund_basic':
                raise ValueError('invalid binding')
            return {}, True
    result = dispatch_weekly_reference_profiles(date(2026,10,31), repository=Store())
    assert result['created'] == 3
    assert set(result['errors']) == {'fund_basic'}


def test_empty_forex_recheck_uses_trade_date_not_a_range():
    definition = acquisition_definition(task_key='fx_daily', output_datasets=['forex_daily'], acquisition_endpoint_ids=[7])
    definition['validation_contract']['outputs'] = ['forex_daily']
    definition['validation_contract']['dataset_audits'][0]['dataset_name'] = 'forex_daily'
    class Store:
        def get_endpoint(self, _):
            return {'acquisition_endpoint_id': 7, 'endpoint_key':'fx_daily',
                    'source_id':'tushare','lifecycle_status':'active'}
    day = date(2026, 10, 20)
    spec, = OrchestrationV2Runtime(Store())._plan_acquisition(
        TaskDefinitionDocument.model_validate(definition),
        dict(purpose='backfill', observation_start=day, observation_end=day,
             observation_key=str(day), frozen_scope={'reasons':['recheck_empty']}))
    assert spec.parameters['parameters']['trade_date'] == '20261020'
    assert 'start_date' not in spec.parameters['parameters']
    assert spec.resource_class == 'backfill'


@pytest.mark.parametrize('key', list(WEEKLY_REFERENCE_PROFILES))
def test_reference_runtime_keeps_partitions_inside_acquire_node(key, monkeypatch):
    monkeypatch.setattr('service.orchestration_v2.runtime.list_fanout_values', lambda *a, **k: ['801010.SI'])
    definition = acquisition_definition(task_key=key, output_datasets=[key], acquisition_endpoint_ids=[7])
    definition['validation_contract']['outputs'] = [key]
    definition['validation_contract']['dataset_audits'][0]['dataset_name'] = key
    class Store:
        def get_endpoint(self, _):
            return {'acquisition_endpoint_id': 7, 'endpoint_key': key,
                    'source_id': 'tushare', 'lifecycle_status': 'active'}
    execution = dict(purpose='daily', observation_key='snapshot:2026-10-31',
                     observation_start=date(2026,10,31), observation_end=date(2026,10,31),
                     frozen_scope={'reference_profile': key})
    runtime = OrchestrationV2Runtime(Store())
    document = TaskDefinitionDocument.model_validate(definition)
    specs = runtime._plan_acquisition(document, execution)
    assert len(specs) == len(WEEKLY_REFERENCE_PROFILES[key])
    assert len({s.idempotency_key for s in specs}) == len(specs)
    assert all(s.parameters['complete'] for s in specs)
    expected = ([{'is_new': 'Y', 'l3_code': '801010.SI'}]
                if key in {'index_member_all', 'ci_index_member'} else list(WEEKLY_REFERENCE_PROFILES[key]))
    assert [s.parameters['parameters'] for s in specs] == expected
    execution['frozen_scope']['reference_profile'] = 'unknown'
    with pytest.raises(V2UnsupportedScopeError):
        runtime._plan_acquisition(document, execution)
