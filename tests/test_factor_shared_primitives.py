from collections import Counter

import pandas as pd

from service.research.local_factors import market
from test_local_factor_272 import _market_panel


def test_turnover_windows_are_computed_once_without_changing_values(monkeypatch):
    panel = _market_panel(days=600, securities=3)
    original_mean, original_std = market._last_rolling_mean, market._last_rolling_std
    calls = Counter()
    def mean(frame, window):
        calls['mean', window] += 1
        return original_mean(frame, window)
    def std(frame, window):
        calls['std', window] += 1
        return original_std(frame, window)
    monkeypatch.setattr(market, '_last_rolling_mean', mean)
    monkeypatch.setattr(market, '_last_rolling_std', std)
    values = market.MarketFactorEvaluator(panel)._turnover_factors()
    for window in (21, 42, 63, 126, 252, 504):
        assert calls['mean', window] == calls['std', window] == 1
    turnover = panel.turnover_rate / 100
    pd.testing.assert_series_equal(values['bias_turn_21d_504d'], original_mean(turnover,21) / original_mean(turnover,504) - 1)
    pd.testing.assert_series_equal(values['turnover_ma_20d'], -values['avg_turnover_20d'])


def test_momentum_and_risk_share_identical_price_regressions(monkeypatch):
    panel = _market_panel(days=1400, securities=3)
    evaluator = market.MarketFactorEvaluator(panel)
    original = market._rolling_regression
    calls = Counter()
    def regression(stocks, benchmark, window):
        if stocks is evaluator.returns:
            calls[window, benchmark.name] += 1
        return original(stocks, benchmark, window)
    monkeypatch.setattr(market, '_rolling_regression', regression)
    momentum = evaluator._momentum_factors()
    risk = evaluator._risk_factors()
    for window in (125,250,500,1000):
        assert calls[window,None] == 1
        alpha,beta,_ = original(evaluator.returns,panel.benchmark_close_000300.pct_change(),window)
        pd.testing.assert_series_equal(momentum[f'alpha_{window}d_000300'],alpha)
        pd.testing.assert_series_equal(risk[f'beta_{window}d_000300'],beta)
