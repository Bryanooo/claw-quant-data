"""Formula regressions: original filter order, matured outcomes and no lookahead."""
from math import pi, sin
from statistics import mean

import pytest

from service.research.technical_indicators import (
    xiongmen_rebound_lines, xiongmen_rebound_series,
)


def bear_history():
    closes = [1000.] * 250 + [
        700 * .94 ** (i // 30) * (1 + .15 * sin(2 * pi * i / 30))
        for i in range(1200)
    ]
    return [c + 1 for c in closes], [c - 1 for c in closes], closes


def test_reference_line_excludes_current_low_and_uses_simple_current_atr():
    highs, lows, closes = [100.] * 20 + [50.], [98.] * 20 + [10.], [99.] * 20 + [20.]
    series = xiongmen_rebound_series(highs, lows, closes)
    assert series['xiongmen_atrv_14'][-1] == pytest.approx((13 * 2 + 89) / 14)
    assert series['xiongmen_line'][-1] == pytest.approx(98 - .5 * (13 * 2 + 89) / 14)
    assert series['xiongmen_foundation'][-1] == 20
    assert all(v is None for v in series['xiongmen_line'][:20])
    assert series['xiongmen_bear_state'][-1] is None
    assert xiongmen_rebound_lines(highs, lows, closes)['status'] == 'insufficient_history'


def test_large_up_rejection_still_consumes_original_formula_cooldown():
    closes = [100.] * 250 + [60.] * 20 + [80., 60., 64., 68., 72., 76.]
    series = xiongmen_rebound_series([c + 1 for c in closes], [c - 1 for c in closes], closes)
    assert series['xiongmen_large_up'][270] is True
    assert series['xiongmen_candidate'][270] is False
    assert series['xiongmen_large_up'][275] is False
    assert closes[274] < series['xiongmen_floor_1'][274]
    assert closes[275] >= series['xiongmen_floor_1'][275]
    assert series['xiongmen_candidate'][275] is False


def test_expanding_statistics_only_settle_on_day_20_and_gate_labels():
    highs, lows, closes = bear_history()
    result = xiongmen_rebound_series(highs, lows, closes)
    events = [i for i, signal in enumerate(result['xiongmen_candidate']) if signal]
    assert len(events) >= 30
    assert result['xiongmen_sample_count'][events[0] + 19] == 0
    assert result['xiongmen_sample_count'][events[0] + 20] == 1
    assert any(result['xiongmen_reduction_signal'])
    for i, close in enumerate(closes):
        matured = [t for t in events if t + 20 <= i]
        lower = sum(closes[t + 20] < closes[t] for t in matured)
        rate = lower / max(len(matured), 1) * 100
        assert result['xiongmen_sample_count'][i] == len(matured)
        assert result['xiongmen_lower_count'][i] == lower
        assert result['xiongmen_lower_rate_pct'][i] == pytest.approx(rate)
        eligible = i in events and len(matured) >= 15 and rate >= 65
        expected = ('减二' if close >= result['xiongmen_floor_2'][i] else '减一') if eligible else None
        assert result['xiongmen_reduction_signal'][i] == expected
        if expected:
            assert result['xiongmen_marker_price'][i] == close * (1.05 if expected == '减二' else 1.03)
    summary = xiongmen_rebound_lines(highs, lows, closes)
    assert summary['statistics']['matured_samples'] == len([t for t in events if t + 20 < len(closes)])
    assert summary['statistics']['eligible'] is True


def test_full_formula_crossings_match_independent_literal_evaluation():
    highs, lows, closes = bear_history()
    result = xiongmen_rebound_series(highs, lows, closes)
    blocked_through = -1
    for i in range(249, len(closes)):
        ll, hh = min(closes[i-19:i+1]), max(closes[i-59:i+1])
        old_ll, old_hh = min(closes[i-20:i]), max(closes[i-60:i])
        crossed = any(closes[i] >= ll + (hh-ll)*r and closes[i-1] < old_ll + (old_hh-old_ll)*r for r in (.382, .5))
        xs = closes[i] <= max(closes[i-249:i+1])*.8
        bf = mean(abs(closes[j]-closes[j-1]) for j in range(i-13, i+1))
        accepted = xs and crossed and i > blocked_through
        if accepted:
            blocked_through = i + 10
        assert result['xiongmen_candidate'][i] == (accepted and not closes[i]-closes[i-1] > 3*bf)
        for level, ratio in enumerate((.382, .5, .618), 1):
            assert result[f'xiongmen_floor_{level}'][i] == pytest.approx(ll+(hh-ll)*ratio)


def test_future_bars_do_not_rewrite_lines_statistics_or_signals():
    highs, lows, closes = bear_history()
    full = xiongmen_rebound_series(highs, lows, closes)
    for length in (0, 14, 20, 60, 249, 250, 300, 733, 1000):
        prefix = xiongmen_rebound_series(highs[:length], lows[:length], closes[:length])
        assert prefix == {key: values[:length] for key, values in full.items()}
    assert full['xiongmen_bear_state'][248] is None
    assert full['xiongmen_bear_state'][249] is False
    assert xiongmen_rebound_lines([], [], [])['status'] == 'insufficient_history'


def test_mismatched_inputs_are_rejected():
    with pytest.raises(ValueError, match='equal length'):
        xiongmen_rebound_series([1.], [], [1.])


def test_reduction_labels_follow_current_floor_two_with_original_price_offsets():
    from random import Random
    rng = Random(7)
    closes = [1000.] * 250 + [
        700 * .94 ** (i // 30) * (1 + .15 * sin(2*pi*i/30) + rng.uniform(-.06, .06))
        for i in range(1200)
    ]
    result = xiongmen_rebound_series([c+1 for c in closes], [c-1 for c in closes], closes)
    assert {'减一', '减二'} <= set(result['xiongmen_reduction_signal'])
    for i, label in enumerate(result['xiongmen_reduction_signal']):
        if label is None:
            continue
        assert label == ('减二' if closes[i] >= result['xiongmen_floor_2'][i] else '减一')
        assert result['xiongmen_sample_count'][i] >= 15
        assert result['xiongmen_lower_rate_pct'][i] >= 65
        assert result['xiongmen_marker_price'][i] == closes[i] * (1.05 if label == '减二' else 1.03)


def test_equal_close_at_maturity_is_not_counted_as_lower():
    highs, lows, closes = bear_history()
    initial = xiongmen_rebound_series(highs, lows, closes)
    first = initial['xiongmen_candidate'].index(True)
    closes[first+20] = closes[first]
    result = xiongmen_rebound_series([c+1 for c in closes], [c-1 for c in closes], closes)
    assert result['xiongmen_sample_count'][first+20] == 1
    assert result['xiongmen_lower_count'][first+20] == 0
    assert result['xiongmen_lower_rate_pct'][first+20] == 0
