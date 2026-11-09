from datetime import date
from types import SimpleNamespace

import pytest

from service.orchestration_v2 import factor_reference as reference
from service.research.local_factors.reference_sampling import SAMPLE_METHOD


def execution():
    return {'task_execution_id': 1, 'observation_start': date(2026, 10, 30), 'observation_end': date(2026, 10, 30),
            'observation_key': 'reference-sample:2026-10-30', 'frozen_scope': {
                'reference_sample_method': SAMPLE_METHOD,
                'reference_securities': [f'{i:06d}.SZ' for i in range(30)]}}


def test_reference_plans_one_request_per_frozen_security():
    specs = reference.plan_requests(execution())
    assert len(specs) == 30
    assert specs[0].parameters['parameters'] == {'ts_code': '000000.SZ', 'trade_date': '20261030'}


def test_missing_factor_cannot_pass_sample_audit(monkeypatch):
    monkeypatch.setattr(reference, 'query', lambda *a: [])
    result, update, evidence = reference.audit_sample(execution())[0]
    assert not update.ready
    assert result.status == 'gaps'
    assert update.dataset_name == 'factor_reference_sample'
    assert evidence['evidence']['whole_market_certified'] is False


def test_complete_sample_is_not_whole_market_state(monkeypatch):
    names = [s.name for s in reference.FACTOR_SPECS]
    monkeypatch.setattr(reference, 'query', lambda *a: [
        {'manifest': {'ts_code': f'{i:06d}.SZ','trade_date':'20261030',
                      'verified':True,'reference_response_manifest':True,
                      'returned_keys':names[:-7], 'supplier_missing_keys':names[-7:],
                      'explicit_null_keys':[]}} for i in range(30)
    ])
    _, update, _ = reference.audit_sample(execution())[0]
    assert update.ready
    assert update.expected_count == 30
    assert update.dataset_name != 'factor_value'


def test_malformed_absence_evidence_cannot_pass(monkeypatch):
    monkeypatch.setattr(reference, 'query', lambda *a: [
        {'manifest': {'ts_code':'000000.SZ','trade_date':'20261030',
                      'verified':True,'reference_response_manifest':True,
                      'returned_keys':[], 'supplier_missing_keys':[],
                      'explicit_null_keys':[]}}])
    assert not reference.audit_sample(execution())[0][1].ready


def test_acquisition_preserves_absent_and_explicit_null(monkeypatch):
    import pandas as pd
    from collectors import tushare_raw
    monkeypatch.setattr(reference, '_historical_sessions', lambda *a: None)
    name = reference.FACTOR_SPECS[0].name
    frame = pd.DataFrame([dict(ts_code='000000.SZ',trade_date='20261030',
                               factor_name=name,factor_value=None)])
    monkeypatch.setattr(tushare_raw,'CatalogRawCollector',lambda _:SimpleNamespace(
        fetch=lambda **kw:frame, store=lambda f:len(f)))
    result = reference.acquire_reference(reference.plan_requests(execution())[0])
    assert result.completion_evidence['explicit_null_keys'] == [name]
    assert len(result.completion_evidence['supplier_missing_keys']) == 271


def test_cannot_activate_by_dispatch_alone():
    store = SimpleNamespace(get_active_definition=lambda key: None)
    assert reference.dispatch_reference_sample(store, date(2026, 10, 30))['reason'] == 'awaiting_verified_activation'


def test_daily_provider_limit_defers_and_blocks_siblings(monkeypatch):
    from collectors import tushare_raw
    from service import tushare_rate_limit as limits
    monkeypatch.setattr(reference, '_historical_sessions', lambda *a: None)
    marked = []
    def fetch(**kwargs):
        raise Exception('访问接口(factor_value)频率超限(1000次/天)')
    monkeypatch.setattr(tushare_raw, 'CatalogRawCollector', lambda _: SimpleNamespace(fetch=fetch))
    monkeypatch.setattr(limits, 'mark_daily_quota_exhausted', marked.append)
    with pytest.raises(limits.TushareRateSlotDeferredError) as result:
        reference.acquire_reference(reference.plan_requests(execution())[0])
    assert result.value.defer_without_failure
    assert result.value.retry_after_seconds >= 60
    assert marked == ['factor_value']


def test_duplicate_sample_rejected():
    item = execution()
    item['frozen_scope']['reference_securities'][1] = item['frozen_scope']['reference_securities'][0]
    with pytest.raises(ValueError):
        reference.plan_requests(item)


def test_exact_historical_dispatch_does_not_shift_date(monkeypatch):
    day = date(2026, 10, 8)
    monkeypatch.setattr(reference, 'query', lambda *a: pytest.fail('must not resolve latest date'))
    monkeypatch.setattr(reference, 'reference_sample_plan', lambda target, *, window_days=1: {
        'status': 'planned', 'securities': ['000001.SZ'] * 128
    } if target == day else pytest.fail('wrong date'))
    requests = []
    def create(request):
        requests.append(request)
        return {'task_execution_id': 12}, True
    repository = SimpleNamespace(get_active_definition=lambda _: {'version': 3}, create_execution=create)
    assert reference.dispatch_reference_sample(repository, day, exact_date=True)['created']
    assert requests[0].observation_end == day


def window_execution(days):
    return {'task_execution_id': 2, 'observation_start': days[0],
            'observation_end': days[-1],
            'observation_key': f'reference-sample:{days[0]}:{days[-1]}',
            'frozen_scope': {'reference_sample_method': SAMPLE_METHOD,
                             'reference_securities': [f'{i:06d}.SZ' for i in range(30)],
                             'reference_trade_dates': [d.isoformat() for d in days]}}


def test_window_costs_one_request_per_security_not_per_session():
    days = [date(2026, 10, 26), date(2026, 10, 27), date(2026, 10, 28)]
    specs = reference.plan_requests(window_execution(days))
    # Three sessions of thirty securities is ninety provider calls under the
    # old shape and thirty under a batched window.
    assert len(specs) == 30
    assert specs[0].parameters['parameters'] == {
        'ts_code': '000000.SZ', 'start_date': '20261026', 'end_date': '20261028'}
    assert specs[0].parameters['page_size'] == reference.REFERENCE_WINDOW_PAGE_SIZE


def test_single_session_keeps_the_probed_exact_date_request():
    specs = reference.plan_requests(execution())
    assert specs[0].parameters['parameters'] == {'ts_code': '000000.SZ', 'trade_date': '20261030'}
    assert specs[0].parameters['page_size'] == reference.REFERENCE_PAGE_SIZE


def test_window_wider_than_the_row_budget_is_rejected():
    days = [date(2026, 10, 1), date(2026, 10, 30)]
    item = window_execution(days)
    item['frozen_scope']['reference_trade_dates'] = [
        (date(2026, 9, 1) + __import__('datetime').timedelta(days=i)).isoformat()
        for i in range(reference.MAX_WINDOW_DAYS + 5)]
    with pytest.raises(ValueError):
        reference.frozen_days(item)


def test_windowed_response_records_absence_evidence_per_session(monkeypatch):
    import pandas as pd
    from collectors import tushare_raw
    monkeypatch.setattr(reference, '_historical_sessions', lambda *a: None)
    name = reference.FACTOR_SPECS[0].name
    frame = pd.DataFrame([
        dict(ts_code='000000.SZ', trade_date='20261026', factor_name=name, factor_value=1.0),
        dict(ts_code='000000.SZ', trade_date='20261027', factor_name=name, factor_value=None),
    ])
    monkeypatch.setattr(tushare_raw, 'CatalogRawCollector', lambda _: SimpleNamespace(
        fetch=lambda **kw: frame, store=lambda f: len(f)))
    days = [date(2026, 10, 26), date(2026, 10, 27)]
    result = reference.acquire_reference(reference.plan_requests(window_execution(days))[0])
    sessions = result.completion_evidence['day_manifests']
    assert [item['trade_date'] for item in sessions] == ['20261026', '20261027']
    # One session's explicit null must not be averaged away by the other.
    assert sessions[0]['explicit_null_keys'] == []
    assert sessions[1]['explicit_null_keys'] == [name]


def test_audit_requires_every_security_session_pair(monkeypatch):
    names = [spec.name for spec in reference.FACTOR_SPECS]
    days = [date(2026, 10, 26), date(2026, 10, 27)]
    monkeypatch.setattr(reference, 'query', lambda *a: [
        {'manifest': {'ts_code': f'{i:06d}.SZ', 'verified': True,
                      'reference_response_manifest': True,
                      'day_manifests': [
                          {'ts_code': f'{i:06d}.SZ', 'trade_date': '20261026',
                           'returned_keys': names, 'supplier_missing_keys': [],
                           'explicit_null_keys': []}]}} for i in range(30)
    ])
    result, update, _ = reference.audit_sample(window_execution(days))[0]
    # Only one of two sessions is evidenced, so half the pairs are missing.
    assert update.expected_count == 60
    assert update.actual_count == 30
    assert result.status == 'gaps'
    assert not update.ready


def test_truncated_window_response_is_rejected(monkeypatch):
    import pandas as pd
    from collectors import tushare_raw
    from collectors.tushare_raw import IncompleteCollectionError
    monkeypatch.setattr(reference, '_historical_sessions', lambda *a: None)
    name = reference.FACTOR_SPECS[0].name
    frame = pd.DataFrame([
        dict(ts_code='000000.SZ', trade_date=f'2026102{d}', factor_name=name, factor_value=1.0)
        for d in range(6)])
    frame = pd.concat([frame] * 1000, ignore_index=True)
    monkeypatch.setattr(tushare_raw, 'CatalogRawCollector', lambda _: SimpleNamespace(
        fetch=lambda **kw: frame, store=lambda f: len(f)))
    days = [date(2026, 10, 20), date(2026, 10, 30)]
    with pytest.raises(IncompleteCollectionError):
        reference.acquire_reference(reference.plan_requests(window_execution(days))[0])


def _replay_query(sessions, rows, day_factors, day_codes=200):
    def fake_query(sql, params=None):
        if 'trade_cal' in sql:
            return [{'cal_date': day} for day in sessions]
        if 'count(DISTINCT factor_name)' in sql:
            return [{'trade_date': day, 'factors': day_factors,
                      'codes': day_codes} for day in sessions]
        return rows
    return fake_query


def test_historical_replay_answers_without_a_provider_call(monkeypatch):
    # Stored rows for the same security and dates are themselves provider
    # evidence; a certified window must be answered from the database without
    # touching the collector or spending quota.
    from collectors import tushare_raw
    names = [spec.name for spec in reference.FACTOR_SPECS]
    sessions = [date(2026, 10, 28), date(2026, 10, 29), date(2026, 10, 30)]
    rows = [{'trade_date': day, 'factor_name': name,
             'factor_value': None if name == names[0] else 1.0}
            for day in sessions for name in names]
    monkeypatch.setattr(reference, 'query',
                        _replay_query(sessions, rows, len(names)))
    monkeypatch.setattr(tushare_raw, 'CatalogRawCollector',
                        lambda _: pytest.fail('replay must not call the provider'))
    result = reference.acquire_reference(reference.plan_requests(window_execution(sessions))[0])
    assert result.completion_status == 'complete'
    assert result.rows_inserted == 0
    evidence = result.completion_evidence
    assert evidence['source'] == 'historical_db'
    assert evidence['day_count'] == 3
    assert evidence['supplier_missing_keys'] == []
    for entry in evidence['day_manifests']:
        assert entry['source'] == 'historical_db'
        assert entry['explicit_null_keys'] == [names[0]]


def test_history_counts_cannot_manufacture_supplier_absence(monkeypatch):
    names = {spec.name for spec in reference.FACTOR_SPECS}
    sessions = [date(2026, 10, 30)]
    rows = [{'trade_date': sessions[0], 'factor_name': name, 'factor_value': 1.0}
            for name in sorted(names)[:-3]]
    monkeypatch.setattr(reference, 'query', _replay_query(sessions, rows, len(names)))
    assert reference._historical_sessions({'ts_code':'000000.SZ','trade_date':'20261030'}, names) is None


def test_historical_replay_rejects_partially_collected_days(monkeypatch):
    # A day whose stored rows miss part of the catalogue cannot distinguish
    # "the supplier returned nothing" from "we never asked", so the request
    # must fall back to the provider instead of manufacturing absence.
    from collectors import tushare_raw
    import pandas as pd
    names = [spec.name for spec in reference.FACTOR_SPECS]
    sessions = [date(2026, 10, 30)]
    rows = [{'trade_date': sessions[0], 'factor_name': name, 'factor_value': 1.0}
            for name in names[:-70]]
    monkeypatch.setattr(reference, 'query',
                        _replay_query(sessions, rows, len(names) - 70))
    frame = pd.DataFrame([dict(ts_code='000000.SZ', trade_date='20261030',
                               factor_name=names[0], factor_value=1.0)])
    monkeypatch.setattr(tushare_raw, 'CatalogRawCollector', lambda _: SimpleNamespace(
        fetch=lambda **kw: frame, store=lambda f: len(f)))
    result = reference.acquire_reference(reference.plan_requests(execution())[0])
    assert result.completion_evidence.get('source') is None
    assert result.rows_inserted == 1


def test_routine_dispatch_waits_for_the_window_threshold(monkeypatch):
    # One provider call per security per window only pays off if sessions
    # accumulate first: below the threshold the patrol must do nothing.
    from datetime import timedelta
    target = date(2026, 10, 30)
    def fake_query(sql, params=None):
        if 'local_factor_snapshot' in sql:
            return [{'day': target}]
        if 'observation_end' in sql:
            return [{'day': target - timedelta(days=30)}]
        if 'trade_cal' in sql:
            return [{'cal_date': target}]
        raise AssertionError(sql[:60])
    plans = []
    monkeypatch.setattr(reference, 'query', fake_query)
    monkeypatch.setattr(reference, 'reference_sample_plan', lambda *a, **k: pytest.fail(
        'dispatch must not plan below the threshold') if not plans else None)
    repository = SimpleNamespace(get_active_definition=lambda _: {'version': 3})
    result = reference.dispatch_reference_sample(repository, target)
    assert result['created'] is False
    assert result['reason'] == 'window_not_due'
    assert result['unverified_sessions'] == 1


def test_routine_dispatch_settles_the_oldest_backlog_sessions(monkeypatch):
    # Catch-up continues from the last verified session: with a backlog wider
    # than one window, the dispatch covers the oldest sessions so nothing is
    # silently abandoned.
    from datetime import timedelta
    target = date(2026, 10, 30)
    last_verified = date(2026, 9, 30)
    pending = [date(2026, 10, d) for d in range(1, 31) if d not in (17, 18, 24, 25, 31)]
    def fake_query(sql, params=None):
        if 'local_factor_snapshot' in sql:
            return [{'day': target}]
        if 'observation_end' in sql:
            return [{'day': last_verified}]
        if 'trade_cal' in sql:
            return [{'cal_date': day} for day in pending
                    if day > params[0] and day <= params[1]]
        raise AssertionError(sql[:60])
    planned = {}
    def fake_plan(day, *, window_days=1):
        planned['day'] = day
        planned['window_days'] = window_days
        window = [d.isoformat() for d in pending[:window_days]]
        return {'status': 'planned', 'securities': [f'{i:06d}.SZ' for i in range(30)],
                'trade_dates': window, 'estimated_calls': 30}
    created = []
    monkeypatch.setattr(reference, 'query', fake_query)
    monkeypatch.setattr(reference, 'reference_sample_plan', fake_plan)
    repository = SimpleNamespace(
        get_active_definition=lambda _: {'version': 3},
        create_execution=lambda request: (created.append(request) or ({'task_execution_id': 9}, True))
    )
    result = reference.dispatch_reference_sample(repository, target)
    assert result['created'] is True
    assert result['window_days'] == reference.MAX_WINDOW_DAYS
    # The window ends at the threshold-th pending session, not at today, so
    # the newest sessions stay for the next catch-up round.
    assert planned['day'] == pending[reference.MAX_WINDOW_DAYS - 1]
    assert created[0].observation_end == pending[reference.MAX_WINDOW_DAYS - 1]


def test_narrow_day_without_this_security_falls_back(monkeypatch):
    # A day written only by per-security fetches says nothing about a
    # security that was not in the sample; replay must not invent a full
    # supplier-absence manifest for it, so the request goes to the provider.
    from collectors import tushare_raw
    import pandas as pd
    names = [spec.name for spec in reference.FACTOR_SPECS]
    sessions = [date(2026, 10, 21)]
    monkeypatch.setattr(reference, 'query',
                        _replay_query(sessions, [], len(names), day_codes=128))
    frame = pd.DataFrame([dict(ts_code='000000.SZ', trade_date='20261021',
                               factor_name=names[0], factor_value=1.0)])
    monkeypatch.setattr(tushare_raw, 'CatalogRawCollector', lambda _: SimpleNamespace(
        fetch=lambda **kw: frame, store=lambda f: len(f)))
    result = reference.acquire_reference(
        reference.plan_requests(window_execution(sessions))[0])
    assert result.completion_evidence.get('source') is None
    assert result.rows_inserted == 1
