from datetime import date, timedelta

from service.research.volume_price import volume_price_analysis


def _row(index, close, volume):
    return {
        "trade_date": date(2026, 1, 1) + timedelta(days=index),
        "open": close - 0.2,
        "high": close + 0.4,
        "low": close - 0.5,
        "close": close,
        "vol": volume,
    }


def test_volume_price_analysis_confirms_high_volume_breakout_and_turnover():
    rows = [_row(index, 100 + index, 100) for index in range(79)]
    rows.append(_row(79, 180, 500))
    turnover = [
        {
            "trade_date": row["trade_date"],
            "turnover_rate_f": 1 + index / 100,
            "volume_ratio": 1.8 if index == 79 else 1.0,
        }
        for index, row in enumerate(rows)
    ]

    result = volume_price_analysis(rows, turnover_rows=turnover)

    assert result["status"] == "ready"
    assert result["observation"]["trade_date"] == rows[-1]["trade_date"]
    assert result["observation"]["period_complete"] is True
    assert result["activity"]["state"] == "expanding"
    assert result["price_volume_regime"]["classification"] == "bullish_confirmation"
    assert result["breakout_confirmation"]["direction"] == "up"
    assert result["breakout_confirmation"]["confirmed_by_volume"] is True
    assert result["anchored_vwap_proxy"]["anchors"]["20_period"]["value"] is not None
    assert result["turnover"]["basis"] == "free_float"
    assert result["turnover"]["provider_volume_ratio"] == 1.8
    assert result["indicators"]["force_index_13"] is not None


def test_volume_price_analysis_detects_obv_divergence_candidate():
    rows = [_row(0, 100, 20)]
    close = 100.0
    for index in range(1, 25):
        if index % 2:
            close += 2
            volume = 10
        else:
            close -= 1
            volume = 100
        rows.append(_row(index, close, volume))

    result = volume_price_analysis(rows)

    assert result["divergence"]["obv_20"]["classification"] == "bearish_candidate"
    assert result["turnover"]["status"] == "missing"


def test_volume_price_analysis_reports_daily_bar_limitations():
    result = volume_price_analysis([
        _row(0, 100, 0),
        _row(1, 99, 0),
    ])

    assert result["status"] == "ready"
    assert result["anchored_vwap_proxy"]["status"] == "missing_volume"
    assert "Level-2" in result["limitations"][1]
