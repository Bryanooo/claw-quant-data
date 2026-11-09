from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from service.research.local_factors.quality import (
    audit_security, market_input_diagnostic, required_bars,
)


def panel(days=305):
    index = pd.bdate_range('2025-01-01', periods=days)
    def frame(values):
        return pd.DataFrame({'stock': values}, index=index)
    base = np.arange(days, dtype=float)
    return SimpleNamespace(
        alpha101=SimpleNamespace(open=frame(base+10), high=frame(base+12),
                                 low=frame(base+8), close=frame(base+10+np.sin(base)),
                                 volume=frame(base+100)),
        benchmark_volume_000001=pd.Series(base+200, index=index),
        benchmark_volume_000300=pd.Series(base+300, index=index),
        listing_dates=None, unexplained_market_gaps=pd.Series({'stock': 0}),
    )


def test_composed_windows_include_volume_lag_but_not_price_lag():
    assert required_bars('price_position_ir_60d') == 60
    assert required_bars('volume_alpha_300d_000001') == 305
    assert required_bars('volume_alpha_300d_000300') == 305


def test_price_zero_range_anywhere_in_window_is_proven_domain_not_a_missing_bar():
    p = panel()
    p.alpha101.high.iloc[-12] = p.alpha101.low.iloc[-12]
    reason = market_input_diagnostic('price_position_ir_60d', 'stock', p)
    assert reason == 'undefined_price_position_zero_range_in_complete_60_session_window'
    result = audit_security('stock', {}, {'adjustment_status': 'applied'}, p)
    assert result['excluded']['price_position_ir_60d'] == reason
    p.alpha101.open.iloc[-2] = np.nan
    result = audit_security('stock', {}, {'adjustment_status': 'applied'}, p)
    assert 'price_position_ir_60d' not in result['excluded']
    assert result['unresolved']['price_position_ir_60d'] == 'missing_market_inputs:60_session_ohlc'


def test_flat_day_outside_window_does_not_explain_failure():
    p = panel()
    p.alpha101.high.iloc[-61] = p.alpha101.low.iloc[-61]
    assert market_input_diagnostic('price_position_ir_60d', 'stock', p).startswith('nonfinite_result_')


def test_price_zero_variance_and_invalid_range_are_distinct():
    p = panel()
    p.alpha101.close = p.alpha101.open.copy()
    assert market_input_diagnostic('price_position_ir_60d', 'stock', p).startswith('undefined_price_position_zero_variance')
    p.alpha101.high.iloc[-3] = -1
    assert market_input_diagnostic('price_position_ir_60d', 'stock', p) == 'invalid_market_inputs:high_below_low'


@pytest.mark.parametrize('benchmark', ['000001', '000300'])
def test_volume_zero_base_requires_complete_stock_and_benchmark_inputs(benchmark):
    name = 'volume_alpha_300d_' + benchmark
    p = panel()
    p.alpha101.volume.iloc[0:5] = 0
    assert market_input_diagnostic(name, 'stock', p).startswith('undefined_volume_regression_zero_base')
    getattr(p, 'benchmark_volume_' + benchmark).iloc[-4] = np.nan
    assert market_input_diagnostic(name, 'stock', p).startswith('missing_market_inputs:')


def test_volume_short_window_and_zero_variance_are_not_confused():
    name = 'volume_alpha_300d_000300'
    assert market_input_diagnostic(name, 'stock', panel(304)).startswith('insufficient_market_window:')
    p = panel()
    assert market_input_diagnostic(name, 'stock', p).startswith('nonfinite_result_')
    p.benchmark_volume_000300[:] = 100
    assert market_input_diagnostic(name, 'stock', p) == 'undefined_volume_regression_zero_benchmark_variance'
    p.alpha101.volume.iloc[-8] = -1
    assert market_input_diagnostic(name, 'stock', p) == 'invalid_market_inputs:negative_volume'


def test_new_listing_at_304_sessions_is_warmup_not_unexplained_failure():
    p = panel(304)
    p.listing_dates = pd.Series({'stock': '20250101'})
    result = audit_security('stock', {}, {'adjustment_status': 'applied'}, p)
    assert result['excluded']['volume_alpha_300d_000001'] == 'insufficient_listing_history'
    assert result['excluded']['volume_alpha_300d_000300'] == 'insufficient_listing_history'


def test_other_factor_failures_are_not_blanket_excluded():
    assert market_input_diagnostic('unknown_factor', 'stock', panel()) is None


def test_risk_windows_do_not_publish_short_or_gapped_history():
    from service.research.local_factors.market import MarketFactorEvaluator
    from tests.test_local_factor_272 import _market_panel
    p = _market_panel(days=42, securities=2)
    close = p.alpha101.close
    a, b = close.columns
    close.loc[close.index[:2], a] = np.nan  # 40 sessions for this stock
    values = MarketFactorEvaluator(p)._risk_factors()
    assert pd.isna(values['high_low_42d'][a])
    assert pd.isna(values['days_beyond_upper_lower_21d'][a])
    assert np.isfinite(values['days_beyond_upper_lower_21d'][b])
    assert values['high_low_42d'][b] == pytest.approx(close[b].max() / close[b].min())
    close.loc[close.index[-10], b] = np.nan
    assert pd.isna(MarketFactorEvaluator(p)._risk_factors()['high_low_21d'][b])
    assert required_bars('high_low_21d') == 21
    assert required_bars('rsrs') == 217


def test_five_year_market_cap_needs_a_session_before_listing_to_prove_warmup():
    p = panel()
    for code_date, expects_warmup in [('20250102', True), ('20250101', False)]:
        p.listing_dates = pd.Series({'stock': code_date})
        result = audit_security('stock', {}, {'adjustment_status': 'applied'}, p)
        assert ('etp5' in result['excluded']) == expects_warmup


def test_persisted_issue_categories_keep_comparison_independent():
    from service.research.local_factors.issue import issue_category
    row = {'listing_sessions_observed': 35, 'excluded': {'alpha101_84': 'numerically_unstable_extreme_value'}}
    assert issue_category('alpha101_84', False, row) == 'numeric_guard'
    assert issue_category('high_low_42d', True, row) == 'incorrect_short_window_value'
    assert issue_category('high_low_21d', True, row) == 'calculated'
    row['excluded']['peg_252d'] = 'insufficient_listing_history'
    assert issue_category('peg_252d', False, row) == 'formula_inputs_require_review'


@pytest.mark.parametrize(('factor', 'days'), [('alpha101_32', 235), ('alpha101_66', 16)])
def test_alpha_window_checks_missing_sources_before_domain_exclusions(factor, days):
    p = panel(days)
    p.alpha101.amount = p.alpha101.volume * 10
    p.alpha101.volume.iloc[-2] = p.alpha101.amount.iloc[-2] = 0
    assert required_bars(factor) == days
    assert 'zero_volume' in market_input_diagnostic(factor, 'stock', p)
    p.alpha101.amount.iloc[-1] = np.nan
    assert market_input_diagnostic(factor, 'stock', p).startswith('missing_market_inputs')


def test_alpha66_midpoint_and_alpha32_exact_vwap_window():
    p = panel(235)
    p.alpha101.amount = p.alpha101.volume * 10
    assert 'zero_price_denominator' in market_input_diagnostic('alpha101_66', 'stock', p)
    p.alpha101.amount.iloc[-231] = np.nan
    assert market_input_diagnostic('alpha101_32', 'stock', p).startswith('nonfinite_result')
    p.alpha101.close.iloc[-235] = np.nan
    assert market_input_diagnostic('alpha101_32', 'stock', p).startswith('missing_market_inputs')


def test_alpha66_uses_exact_source_midpoint_before_float32_rounding():
    from service.research.local_factors.alpha101 import Alpha101Panel, Alpha101Evaluator

    idx = pd.bdate_range('2026-01-02', periods=22)
    frame = lambda v: pd.DataFrame({'stock': v}, index=idx, dtype='float32')
    # Midpoint(10.01, 10.09) = 10.05 in the source decimal quotes.
    p = Alpha101Panel(frame(10.05),frame(10.09),frame(10.01),frame(10.05),
                      frame(100.),frame(100.5),frame(1.),pd.Series({'stock':'a'}),
                      open_minus_midpoint=frame(0.))
    assert pd.isna(Alpha101Evaluator(p.tail(20)).evaluate(66).iloc[-1,0])
    p.open_minus_midpoint = frame(.005)
    assert np.isfinite(Alpha101Evaluator(p).evaluate(66).iloc[-1,0])


@pytest.mark.parametrize('operator', ['ts_product','ts_rank','decay_linear','ts_argmin','ts_argmax'])
def test_short_alpha_panels_return_warmup_null(operator):
    from service.research.local_factors.alpha101 import Alpha101Evaluator
    data = pd.DataFrame({'a':[1.,2.]})
    assert getattr(Alpha101Evaluator,operator)(data,5).isna().all().all()


def test_alpha_unobserved_condition_and_short_circuit():
    from service.research.local_factors.alpha101 import Alpha101Panel, Alpha101Evaluator, minimum_history
    idx = pd.bdate_range('2026-01-02',periods=24)
    p = pd.DataFrame({'stock':np.arange(24,dtype=float)+10},index=idx)
    ev = Alpha101Evaluator(Alpha101Panel(p,p,p,p,p,p,p,p.iloc[-1]))
    assert minimum_history(7) == 20 and ev.evaluate(7).iloc[:19,0].isna().all()
    unknown = p * np.nan
    assert ev.where(unknown,p,-1).isna().all().all()
    assert ev.logical_or(p*0+1,unknown).eq(1).all().all()
    assert ev.logical_or(p*0,unknown).isna().all().all()


def test_alpha_cross_section_ignores_another_securitys_invalid_division():
    from service.research.local_factors.alpha101 import Alpha101Evaluator
    values = pd.DataFrame([[1.,3.,np.inf]])
    assert Alpha101Evaluator.rank(values).iloc[0,:2].tolist()==[.5,1.]
    assert Alpha101Evaluator.scale(values).iloc[0,:2].tolist()==[.25,.75]
    assert pd.isna(Alpha101Evaluator.rank(values).iloc[0,2])
