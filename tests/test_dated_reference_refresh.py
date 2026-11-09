from datetime import date, datetime
from unittest.mock import Mock

import pandas as pd
import pytest

from collectors.stock.reference.pledge_stat import PledgeStatCollector
from collectors.stock.extra.ccass_hold_detail import CcassHoldDetailCollector


def test_ccass_preserves_idless_people_and_refuses_conflicting_positions():
    c=object.__new__(CcassHoldDetailCollector)
    base=dict(ts_code='00700.HK',trade_date='20261030',col_participant_id=None,
              col_participant_name='example',col_shareholding=100)
    other={**base,'col_participant_name':'another'}
    out=c.transform(pd.DataFrame([base,base,other]))
    assert list(out.participant_key)==['name:example','name:another']
    assert out.col_participant_id.isna().all()
    with pytest.raises(ValueError,match='conflicting'):
        c.transform(pd.DataFrame([base,{**base,'col_shareholding':200}]))
from collectors.stock.basic.stk_rewards import StkRewardsCollector
from service.orchestration_v2.dated_reference import enqueue, partitions, reward_partitions


def test_patrol_discovers_non_friday_end_date_and_skips_empty_dates(monkeypatch):
    from service.orchestration_v2 import dated_reference as ref
    store = Mock()
    store.active_task_keys.return_value = {'pledge_stat', 'stock_hsgt'}
    monkeypatch.setattr(ref, 'query', lambda *a: [{'cal_date': date(2026, 9, 30)}])
    provider = Mock()
    provider.pledge_stat.side_effect = lambda end_date, limit: pd.DataFrame(
        [{'end_date': end_date}] if end_date == '20260930' else [])
    monkeypatch.setattr('collectors.stock.reference.pledge_stat.PledgeStatCollector',
                        lambda: Mock(pro=provider))
    assert ref.dispatch(store, datetime(2026, 10, 1, 19, 15)) == {}
    requests = [c.args[0] for c in store.create_execution.call_args_list]
    assert {(r.task_key, r.observation_end) for r in requests} == {
        ('pledge_stat', date(2026, 9, 30)), ('stock_hsgt', date(2026, 9, 30))}
    assert provider.pledge_stat.call_count == 8


def test_exact_periods_and_request_budget():
    day = date(2026, 9, 24)
    assert partitions('pledge_stat', day) == ({'end_date': '20260924'},)
    assert {p['type'] for p in partitions('stock_hsgt', day)} == {'HK_SZ','SZ_HK','HK_SH','SH_HK'}
    r = Mock()
    enqueue(r, 'stock_hsgt', day)
    req = r.create_execution.call_args.args[0]
    assert req.observation_start == req.observation_end == day
    assert req.frozen_scope['force_acquire']
    year = date(2025, 12, 31)
    assert len(reward_partitions(year, list(map(str,range(21))))) == 2
    with pytest.raises(ValueError):
        reward_partitions(year, list(map(str,range(6401))))


def test_salary_revisions_are_not_merged_and_ambiguous_records_fail():
    from service.data_service.registry import DATASETS
    assert DATASETS.get('stk_rewards').date_column == 'end_date'
    c = object.__new__(StkRewardsCollector)
    row = {'ts_code':'600519.SH','end_date':'20251231','name':'example',
           'reward':200,'ann_date':'20260301'}
    revised = {**row,'ann_date':'20260302','reward':400}
    assert len(c.transform(pd.DataFrame([row, revised, row]))) == 2
    with pytest.raises(ValueError, match='conflicting'):
        c.transform(pd.DataFrame([row, {**row,'reward':1000}]))


def test_truncated_pledge_and_wrong_ccass_scope_fail_closed():
    c = object.__new__(PledgeStatCollector)
    c.pro = Mock()
    frame = pd.DataFrame([{'ts_code':'600519.SH','end_date':'20261030'}])
    c.pro.pledge_stat.side_effect = [frame, frame]
    with pytest.raises(ValueError, match='not exhausted'):
        c.fetch(end_date='20261030')
    ccass = object.__new__(CcassHoldDetailCollector)
    with pytest.raises(ValueError, match='HK security'):
        ccass.fetch(ts_code='000001.SZ', start_date='20261001',end_date='20261030')
