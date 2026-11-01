from datetime import date, timedelta
from types import SimpleNamespace

import pytest

from service.orchestration_v2 import runtime


def test_factor_history_excludes_closed_calendar_days(monkeypatch):
    start = date(2026, 8, 28)
    monkeypatch.setattr(runtime, 'list_fanout_values', lambda *a, **k: ['test_factor'])
    monkeypatch.setattr(runtime, 'query', lambda *a: [
        {'cal_date': start + timedelta(days=i), 'is_open': int(i == 0)} for i in range(3)
    ])
    monkeypatch.setattr(runtime.TusharePolicyRegistry, 'get', lambda *a: SimpleNamespace(page_size=1000, max_pages=10))
    monkeypatch.setattr(runtime.TASKS, 'handler_metadata', lambda *a: None)
    specs = runtime.OrchestrationV2Runtime._dynamic_fanout_specs(
        api_name='factor_value', fanout=runtime.FANOUT_DEFINITIONS['factor_value'],
        observation_start=start, observation_end=start + timedelta(days=2), purpose='backfill',
    )
    assert len(specs) == 1
    assert specs[0].parameters['parameters']['trade_date'] == '20260828'


def test_missing_calendar_is_not_assumed_closed(monkeypatch):
    monkeypatch.setattr(runtime, 'list_fanout_values', lambda *a, **k: ['test_factor'])
    monkeypatch.setattr(runtime, 'query', lambda *a: [])
    with pytest.raises(runtime.V2UnsupportedScopeError, match='calendar'):
        runtime.OrchestrationV2Runtime._dynamic_fanout_specs(
            api_name='factor_value', fanout=runtime.FANOUT_DEFINITIONS['factor_value'],
            observation_start=date(2026, 8, 28), observation_end=date(2026, 8, 28), purpose='backfill',
        )
