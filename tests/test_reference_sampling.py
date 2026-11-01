from datetime import date

from service.research.local_factors import reference_sampling as sampling
from service.research.local_factors import provider_validation as validation


def test_sampling_contract_is_shared_with_comparison():
    assert sampling.SAMPLE_CODES_SQL in validation.VALIDATION_SQL
    assert validation.DEFAULT_SAMPLE_SIZE == 128
    assert validation.SAMPLE_METHOD == sampling.SAMPLE_METHOD
    assert 'fixed_rank <= 32' in sampling.SAMPLE_CODES_SQL


def test_reference_plan_is_bounded_and_does_not_certify_market(monkeypatch):
    def query(sql, params):
        if 'trade_cal' in sql:
            return [{'is_open': 1}]
        assert params == ('local-272-v4', date(2026, 10, 30), '2026-10-30', 128)
        return [{'ts_code': f'{i:06d}.SZ'} for i in range(128)]
    monkeypatch.setattr(sampling, 'query', query)
    plan = sampling.reference_sample_plan(date(2026, 10, 30))
    assert len(plan['requests']) == 128
    assert plan['requests'][0] == {'ts_code': '000000.SZ', 'trade_date': '20261030'}
    assert plan['provider_contract_probe_required']
    assert plan['whole_market_certified'] is False


def test_unknown_and_closed_calendar_never_request_provider(monkeypatch):
    monkeypatch.setattr(sampling, 'query', lambda *a: [])
    assert sampling.reference_sample_plan(date(2026, 10, 30))['status'] == 'calendar_missing'
    monkeypatch.setattr(sampling, 'query', lambda *a: [{'is_open': 0}])
    assert sampling.reference_sample_plan(date(2026, 10, 31))['requests'] == []


def test_missing_local_snapshot_does_not_collect_unmatched_sample(monkeypatch):
    monkeypatch.setattr(sampling, 'query', lambda sql, params: [{'is_open': 1}] if 'trade_cal' in sql else [])
    plan = sampling.reference_sample_plan(date(2026, 10, 30))
    assert plan['status'] == 'local_sample_insufficient'
    assert plan['requests'] == []


def _calendar_query(codes=128, sessions=None):
    sessions = sessions or [date(2026, 10, 30)]

    def query(sql, params):
        if 'trade_cal' in sql:
            if 'is_open' in sql and 'cal_date=%s' in sql:
                return [{'is_open': 1}]
            return [{'cal_date': day} for day in sessions]
        return [{'ts_code': f'{i:06d}.SZ'} for i in range(codes)]
    return query


def test_window_batches_sessions_into_one_request_per_security(monkeypatch):
    sessions = [date(2026, 10, 26) + __import__('datetime').timedelta(days=i) for i in range(5)]
    monkeypatch.setattr(sampling, 'query', _calendar_query(sessions=sessions))
    plan = sampling.reference_sample_plan(date(2026, 10, 30), window_days=5)
    assert plan['window_days'] == 5
    # Five sessions still cost one call per security, not five.
    assert plan['estimated_calls'] == 128
    assert plan['requests'][0] == {'ts_code': '000000.SZ',
                                   'start_date': '20261026', 'end_date': '20261030'}
    assert len({request['ts_code'] for request in plan['requests']}) == 128


def test_window_is_capped_by_the_provider_row_budget(monkeypatch):
    monkeypatch.setattr(sampling, 'query', _calendar_query())
    plan = sampling.reference_sample_plan(date(2026, 10, 30), window_days=999)
    assert plan['window_days'] <= sampling.MAX_WINDOW_DAYS
    assert plan['max_window_days'] == sampling.MAX_WINDOW_DAYS


def test_window_stays_below_the_provider_row_cap():
    # A truncated response is indistinguishable from a complete one, so the
    # widest permitted window must leave the cap unbreached.
    factors = len(__import__('service.research.local_factors.catalog',
                             fromlist=['FACTOR_SPECS']).FACTOR_SPECS)
    assert sampling.MAX_WINDOW_DAYS * factors < sampling.PROVIDER_ROW_CAP
