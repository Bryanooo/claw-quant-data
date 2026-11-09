from datetime import date

import pytest

from service.research.group_valuation import summarize_valuation, summarize_financials, aggregate_valuation
from service.research.service import ResearchService


DAY = date(2026, 10, 30)


def test_same_date_distribution_and_weights():
    rows = [dict(ts_code='a', trade_date=DAY, pe_ttm=10, pb=1, total_mv=100, dv_ttm=0),
            dict(ts_code='b', trade_date=DAY, pe_ttm=30, pb=3, total_mv=300, dv_ttm=2),
            dict(ts_code='c', trade_date=date(2026, 10, 29), pe_ttm=999)]
    result = summarize_valuation({'a': 50, 'b': 25, 'c': 25}, rows, DAY)
    metric = result['metrics']['pe_ttm']
    assert metric['mean'] == metric['median'] == 20
    assert metric['p25'] == 15
    assert metric['p75'] == 25
    assert metric['market_cap_weighted_mean'] == 25
    assert metric['index_weighted_mean'] == pytest.approx(50 / 3)
    assert metric['index_weight_sum'] == 75
    assert result['missing_codes'] == ['c']
    assert result['metrics']['dv_ttm']['valid_count'] == 2
    assert result['concentration']['market_cap_hhi'] == .625


def test_nonfinite_nonpositive_and_missing_are_not_imputed():
    rows = [dict(ts_code=c, trade_date=DAY, pe_ttm=v) for c, v in
            [('a', -1), ('b', 0), ('c', float('nan')), ('d', float('inf'))]]
    result = summarize_valuation(dict.fromkeys('abcd'), rows, DAY)
    metric = result['metrics']['pe_ttm']
    assert metric['mean'] is None
    assert metric['nonpositive_excluded_codes'] == ['a', 'b']
    assert metric['missing_codes'] == ['c', 'd']
    assert metric['unusable_field_codes'] == ['c', 'd']
    assert metric['sample_status'] == 'no_valid_sample'
    assert metric['missing_member_rows'] == []
    assert result['concentration']['market_cap_hhi'] is None


def test_stale_members_never_claim_ready():
    class Repository:
        def index_valuation_members(self, code, *, as_of):
            assert as_of == DAY
            return [dict(ts_code='a', weight=100, trade_date=date(2026, 8, 31),
                         delist_date=date(2026, 10, 19))]

        def group_valuation_rows(self, codes, *, as_of):
            return [dict(ts_code='a', trade_date=as_of, pe=10, pe_ttm=10,
                         pb=1, ps_ttm=2, dv_ttm=0, total_mv=100)]

    result = ResearchService(None, Repository()).group_valuation('index', trade_date=DAY)
    assert result['meta']['quality']['status'] == 'warning'
    assert result['meta']['quality']['independently_audited'] is False
    assert any('55-day' in w for w in result['meta']['quality']['warnings'])
    assert result['meta']['membership_conflicts'][0]['reason'] == 'delisted_by_requested_date'
    assert result['data']['members'] == 1  # Never silently rewrite the snapshot.


def test_outliers_remain_in_mean_and_percentile_ties_are_equal():
    rows = [dict(ts_code=str(i), trade_date=DAY, pe_ttm=v)
            for i, v in enumerate([10, 10, 10, 10, 1000])]
    metric = summarize_valuation(dict.fromkeys(str(i) for i in range(5)), rows, DAY)['metrics']['pe_ttm']
    assert metric['mean'] == 208
    assert metric['median'] == 10
    assert metric['outliers'] == [{'ts_code': '4', 'value': 1000}]
    assert metric['member_percentiles']['0'] == metric['member_percentiles']['1'] == 40
    assert metric['member_percentiles']['4'] == 90


def test_financials_keep_losses_and_exclude_future_or_wrong_period():
    period = date(2026, 6, 30)
    rows = [dict(ts_code='a', end_date=period, ann_date=DAY, roe=-10),
            dict(ts_code='b', end_date=period, ann_date=date(2026, 11, 1), roe=20),
            dict(ts_code='c', end_date=date(2026, 3, 31), ann_date=DAY, roe=30)]
    result = summarize_financials(dict.fromkeys('abc'), rows, period, DAY)
    assert result['disclosed_members'] == 1
    assert result['metrics']['roe']['median'] == -10
    assert result['metrics']['roe']['negative_count'] == 1
    assert result['metrics']['roe']['missing_codes'] == ['b', 'c']


def test_future_report_period_is_rejected_before_database_access():
    from service.data_service.models import InvalidQueryError
    with pytest.raises(InvalidQueryError):
        ResearchService(None, None).group_valuation('index', trade_date=DAY,
                                                  report_period=date(2026, 12, 31))


def test_aggregate_uses_matched_yuan_denominators_and_includes_losses():
    result = aggregate_valuation(dict.fromkeys('abc'), [
        dict(ts_code='a', total_mv=100, net_income_ttm=100000, parent_equity=500000),
        dict(ts_code='b', total_mv=200, net_income_ttm=-50000, parent_equity=-100000),
        dict(ts_code='c', total_mv=300, net_income_ttm=None, parent_equity=None),
    ])
    assert result['pe_ttm']['value'] == 60
    assert result['pb']['value'] == 7.5
    assert result['pe_ttm']['negative_denominator_members'] == 1
    assert result['pe_ttm']['missing_codes'] == ['c']
    assert result['pe_ttm']['status'] == 'partial'


def test_aggregate_nonpositive_denominator_is_not_a_valid_pe():
    result = aggregate_valuation({'a': None}, [dict(ts_code='a', total_mv=100, net_income_ttm=-1)])
    assert result['pe_ttm']['value'] is None


def test_history_retains_missing_membership_days():
    from service.data_service.models import RecordNotFoundError
    class Repository:
        def group_calendar(self, start, end):
            return [{'cal_date': start, 'is_open': 1}]
    service = ResearchService(None, Repository())
    def missing(*args, **kwargs):
        raise RecordNotFoundError('no members')
    service.group_valuation = missing
    result = service.group_valuation_history('x', start=DAY, end=DAY)
    assert result['meta']['expected_trading_days'] == 1
    assert result['data'][0]['meta']['quality']['status'] == 'missing'


def test_monthly_membership_refresh_is_bounded_and_idempotent(monkeypatch):
    from service.orchestration_v2.scheduling import dispatch_group_weight_refresh
    monkeypatch.setattr('service.orchestration_v2.scheduling.query', lambda *a: [])
    class Store:
        def create_execution(self, request):
            return request
    first = dispatch_group_weight_refresh(Store(), as_of=date(2026, 11, 2))
    second = dispatch_group_weight_refresh(Store(), as_of=date(2026, 11, 3))
    assert first.idempotency_key == second.idempotency_key
    assert first.observation_start == date(2026, 10, 1)
    assert first.observation_end == date(2026, 10, 31)
    assert first.frozen_scope['fanout_values'] == ['000300.SH', '000688.SH']
    monkeypatch.setattr('service.orchestration_v2.scheduling.query', lambda *a: [
        {'index_code': c, 'latest': date(2026, 10, 30)} for c in ('000300.SH', '000688.SH')])
    assert dispatch_group_weight_refresh(Store(), as_of=date(2026, 11, 2)) is None
