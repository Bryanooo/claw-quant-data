from datetime import datetime, timezone

from service.intraday.analyzer import analyze_instrument, analyze_market


NOW = datetime(2026, 10, 23, 13, 20, tzinfo=timezone.utc)


def test_market_reversal_requires_price_and_breadth_confirmation():
    proxies = [
        {"last": 103, "previous_close": 100, "low": 96},
        {"last": 102, "previous_close": 100, "low": 97},
        {"last": 101, "previous_close": 100, "low": 96},
        {"last": 104, "previous_close": 100, "low": 97},
    ]
    sectors = [{"pct_chg": 1} for _ in range(27)] + [{"pct_chg": -1} for _ in range(4)]
    flows = [{"main_net_inflow": -7_000_000_000}, {"main_net_inflow": -2_000_000_000}]

    result = analyze_market(
        as_of=NOW, proxies=proxies, sectors=sectors, flows=flows,
        expected_proxies=4, expected_sectors=31,
    )

    assert result["state"] == "strong_uptrend"
    assert result["metrics"]["event_state"] == "reversal_confirmed"
    assert result["confidence"] == "high"
    assert result["metrics"]["sector_up_count"] == 27
    assert "breadth_confirmation" in result["signals"]


def test_incomplete_market_data_caps_score_and_confidence():
    result = analyze_market(
        as_of=NOW,
        proxies=[{"last": 102, "previous_close": 100, "low": 95}],
        sectors=[], flows=[], expected_proxies=4, expected_sectors=31,
    )

    assert result["data_quality"]["status"] == "partial"
    assert result["confidence"] == "low"
    assert result["score"] <= 69


def test_stale_business_timestamp_downgrades_quality():
    result = analyze_market(
        as_of=NOW,
        proxies=[{"pct_chg": 1, "last": 101, "low": 99}],
        sectors=[{"pct_chg": 1}], flows=[],
        expected_proxies=1, expected_sectors=1, timestamp_fresh=False,
    )

    assert result["data_quality"]["coverage"] == 1
    assert result["data_quality"]["status"] == "partial"
    assert result["data_quality"]["timestamp_fresh"] is False


def test_stock_signal_uses_relative_market_strength():
    market = {"metrics": {"proxy_median_pct": -1.0}}
    result = analyze_instrument(
        as_of=NOW,
        row={
            "symbol": "300750.SZ", "name": "宁德时代", "pct_chg": 2.0,
            "last": 102, "low": 101, "limit_status": "NORMAL",
        },
        market=market,
        scope_type="stock",
    )

    assert result["state"] == "uptrend"
    assert result["metrics"]["event_state"] == "relative_strength"
    assert result["metrics"]["relative_strength_pct"] == 3.0


def test_market_downtrend_is_not_mislabeled_as_only_a_reversal_event():
    result = analyze_market(
        as_of=NOW,
        proxies=[{"pct_chg": -2.8, "last": 97.2, "low": 97.0} for _ in range(4)],
        sectors=[{"pct_chg": -1} for _ in range(27)] + [{"pct_chg": 1} for _ in range(4)],
        flows=[{"main_net_inflow": -5_000_000_000}],
        expected_proxies=4, expected_sectors=31,
    )

    assert result["state"] == "strong_downtrend"
    assert result["metrics"]["event_state"] == "selloff"
    assert "强下跌趋势" in result["conclusion"]
