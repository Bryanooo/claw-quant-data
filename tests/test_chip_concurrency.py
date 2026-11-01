from threading import Barrier, Lock, Event

import pytest

from service.orchestration_v2 import runtime


def test_chip_requests_are_bounded_and_all_results_kept(monkeypatch):
    monkeypatch.setattr(runtime, 'check_history_window', lambda execution: None)
    monkeypatch.setenv('CYQ_CHIPS_CONCURRENCY', '2')
    barrier = Barrier(2)
    lock = Lock()
    active = peak = 0

    def request(spec):
        nonlocal active, peak
        with lock:
            active += 1
            peak = max(peak, active)
        barrier.wait(timeout=3)
        with lock:
            active -= 1
        return spec * 10

    results = list(runtime.acquisition_results(list(range(6)), {'task_key': 'cyq_chips'}, request))
    assert sorted(results) == [(i, i * 10) for i in range(6)]
    assert peak == 2


def test_failure_drains_success_without_submitting_next_batch(monkeypatch):
    monkeypatch.setattr(runtime, 'check_history_window', lambda execution: None)
    monkeypatch.setenv('CYQ_CHIPS_CONCURRENCY', '2')
    called = []

    def request(spec):
        called.append(spec)
        if spec == 0:
            raise RuntimeError('quota')
        return spec

    results = []
    with pytest.raises(RuntimeError, match='quota'):
        for result in runtime.acquisition_results([0, 1, 2, 3], {'task_key': 'cyq_chips'}, request):
            results.append(result)
    assert results == [(1, 1)]
    assert sorted(called) == [0, 1]


def test_other_collectors_stay_serial(monkeypatch):
    monkeypatch.setattr(runtime, 'check_history_window', lambda execution: None)
    assert list(runtime.acquisition_results([1, 2], {'task_key': 'daily'}, lambda x: x)) == [(1, 1), (2, 2)]


def test_fast_slot_continues_while_other_request_is_slow(monkeypatch):
    monkeypatch.setattr(runtime, 'check_history_window', lambda execution: None)
    monkeypatch.setenv('CYQ_CHIPS_CONCURRENCY', '2')
    third_started = Event()

    def request(spec):
        if spec == 0:
            assert third_started.wait(3), 'fast slot was blocked behind slow request'
        if spec == 2:
            third_started.set()
        return spec

    assert sorted(runtime.acquisition_results([0, 1, 2], {'task_key': 'cyq_chips'}, request)) == [(0, 0), (1, 1), (2, 2)]


def test_market_window_blocks_before_submission(monkeypatch):
    def blocked(execution):
        raise RuntimeError('market window')
    monkeypatch.setattr(runtime, 'check_history_window', blocked)
    with pytest.raises(RuntimeError, match='market window'):
        list(runtime.acquisition_results([1, 2], {'task_key': 'cyq_chips'}, lambda x: pytest.fail('must not start')))
