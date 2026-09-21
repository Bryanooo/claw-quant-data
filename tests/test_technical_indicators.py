from datetime import date, timedelta

from service.research.technical_indicators import (
    aroon,
    downside_risk,
    gap_analysis,
    parabolic_sar,
    relative_risk_metrics,
)


def test_aroon_and_parabolic_sar_expose_auditable_trend_state():
    highs = [100 + index for index in range(30)]
    lows = [90 + index for index in range(30)]
    closes = [95 + index for index in range(30)]

    aroon_result = aroon(highs, lows)
    sar_result = parabolic_sar(highs, lows, closes)

    assert aroon_result["status"] == "ready"
    assert aroon_result["up"] == 100.0
    assert aroon_result["state"] == "bullish"
    assert sar_result["status"] == "ready"
    assert sar_result["direction"] == "bullish"
    assert sar_result["value"] < closes[-1]


def test_downside_risk_uses_historical_tail_without_normal_assumption():
    returns = [0.01, -0.02, 0.005, -0.01, 0.003] * 10
    result = downside_risk(returns, 252)

    assert result["status"] == "ready"
    assert result["historical_var_95_pct"] == 2.0
    assert result["historical_expected_shortfall_95_pct"] == 2.0
    assert result["downside_deviation_annualized_pct"] > 0


def test_gap_analysis_distinguishes_filled_and_open_full_gaps():
    start = date(2026, 1, 1)
    rows = [
        {"trade_date": start, "high": 100, "low": 95},
        {"trade_date": start + timedelta(days=1), "high": 110, "low": 105},
        {"trade_date": start + timedelta(days=2), "high": 108, "low": 101},
        {"trade_date": start + timedelta(days=3), "high": 103, "low": 99},
        {"trade_date": start + timedelta(days=4), "high": 90, "low": 85},
        {"trade_date": start + timedelta(days=5), "high": 91, "low": 86},
    ]
    result = gap_analysis(rows)

    assert result["recent"][0]["direction"] == "up"
    assert result["recent"][0]["status"] == "filled"
    assert result["recent"][0]["fill_date"] == "2026-01-04"
    assert result["open"][-1]["direction"] == "down"


def test_relative_risk_metrics_aligns_beta_tracking_error_and_information_ratio():
    benchmark = [100.0]
    asset = [100.0]
    benchmark_returns = [0.01, -0.006, 0.004, -0.002, 0.007] * 13
    for index, benchmark_return in enumerate(benchmark_returns):
        active = 0.001 if index % 2 == 0 else -0.0005
        benchmark.append(benchmark[-1] * (1 + benchmark_return))
        asset.append(asset[-1] * (1 + 1.4 * benchmark_return + active))

    result = relative_risk_metrics(asset, benchmark)
    window = result["windows"]["60"]

    assert result["status"] == "ready"
    assert window["status"] == "ready"
    assert 1.2 < window["beta"] < 1.6
    assert window["correlation"] > 0.95
    assert window["tracking_error_annualized_pct"] > 0
    assert window["information_ratio"] is not None
    assert result["windows"]["120"]["status"] == "insufficient_history"
