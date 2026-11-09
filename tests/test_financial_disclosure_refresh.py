from datetime import date
from unittest.mock import Mock

import pytest

from service.orchestration_v2 import financial_refresh as refresh


@pytest.mark.parametrize('today,expected', [
    (date(2026, 1, 1), (date(2025, 12, 31), date(2025, 9, 30))),
    (date(2026, 4, 30), (date(2026, 3, 31), date(2025, 12, 31))),
    (date(2026, 10, 30), (date(2026, 9, 30), date(2026, 6, 30))),
])
def test_refresh_includes_prior_annual_during_first_quarter_disclosure(today, expected):
    assert refresh.recent_report_periods(today) == expected


def test_same_day_deduplicates_but_next_day_refreshes_same_report_period(monkeypatch):
    enqueue = Mock(return_value={'created': 8})
    monkeypatch.setattr(refresh, 'create_repair_executions', enqueue)
    for day in (30, 30, 31):
        refresh.refresh_financial_disclosures(date(2026, 10, day), object())
    calls = [c.kwargs for c in enqueue.call_args_list]
    assert calls[0]['idempotency_prefix'] == calls[1]['idempotency_prefix']
    assert calls[0]['idempotency_prefix'] != calls[2]['idempotency_prefix']
    assert len(calls[0]['proposals']) == 10
    assert {p.task_key for p in calls[0]['proposals']} == set(refresh.FINANCIAL_TASKS)
    assert calls[0]['purpose'] == 'daily'
    assert calls[0]['trigger_source'] == 'schedule'
    assert calls[0]['frozen_scope_extra']['force_acquire'] is True
    assert calls[0]['proposals'][0].observation_end == date(2026, 9, 30)
