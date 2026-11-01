from datetime import date
import pytest
from service.orchestration_v2.history_continuation import next_window, advance_chip_history


@pytest.mark.parametrize('status', ['running', 'attention', 'retrying', 'queued', 'cancelled'])
def test_non_success_never_advances(status):
    assert next_window({'status': status, 'certified': True}, boundary=date(2018, 1, 2)) is None


def test_success_requires_independent_proof():
    assert next_window({'status': 'success', 'certified': False}, boundary=date(2018, 1, 2)) is None
    assert next_window(None, boundary=date(2018, 1, 2)) is None


def test_window_is_contiguous_bounded_and_stops_at_provider_boundary():
    previous = {'status': 'success', 'certified': True, 'observation_start': date(2026, 9, 20)}
    assert next_window(previous, boundary=date(2018, 1, 2)) == (date(2026, 8, 20), date(2026, 9, 19))
    previous['observation_start'] = date(2018, 1, 10)
    assert next_window(previous, boundary=date(2018, 1, 2)) == (date(2018, 1, 2), date(2018, 1, 9))
    previous['observation_start'] = date(2018, 1, 2)
    assert next_window(previous, boundary=date(2018, 1, 2)) is None


def test_continuation_preserves_campaign_identity_and_predecessor(monkeypatch):
    class Repository:
        def latest_chip_history_window(self):
            return {'task_execution_id': 42, 'status': 'success', 'certified': True,
                    'observation_start': date(2026, 9, 20)}
    captured = {}
    def create(repository, **kwargs):
        captured.update(kwargs)
        return {'created': 1}
    monkeypatch.setattr('service.orchestration_v2.history_continuation.create_repair_executions', create)
    assert advance_chip_history(Repository()) == {'created': 1}
    assert captured['frozen_scope_extra']['predecessor_execution_id'] == 42
    assert captured['purpose'] == 'backfill'
    assert len(captured['proposals']) == 1
