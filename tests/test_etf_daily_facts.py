import pytest
from service.data_service.etf_daily_facts import build_facts


def fixture():
    bars = [
        {"trade_date": "2021-01-04", "close": 10, "pre_close": 10, "high": 10, "low": 10, "vol": 100},
        {"trade_date": "2021-01-05", "close": 9, "pre_close": 9, "high": 9, "low": 9, "vol": 100},
        {"trade_date": "2021-01-06", "close": 4.5, "pre_close": 4.5, "high": 4.5, "low": 4.5, "vol": 100},
    ]
    div = [{"div_proc": "实施", "ex_date": "2021-01-05", "div_cash": 1, "pay_date": "2021-01-08"}]
    evidence = {
        "cash_crosscheck": {"start": "2019-01-01", "end": "2026-10-20", "symbols": [{
            "symbol": "510300.SH", "source_url": "crosscheck", "sha256": "hash",
            "cash": div, "no_cash_explicit": False}]},
        "limit_rules": {"start": "2019-01-01", "end": "2026-10-20", "default_rate": "0.1",
                        "tick": "0.001", "source_urls": ["exchange"], "overrides": []},
        "share_transformations": [{"symbol": "510300.SH", "price_effective_date": "2021-01-06",
                                  "new_shares_per_old_share": 2, "source_url": "issuer"}],
        "events": [],
    }
    return bars, div, evidence


def run(bars, div, evidence, calendar=None, end="2021-01-06"):
    return build_facts("510300.SH", bars, div, calendar or [b["trade_date"] for b in bars],
                       evidence, "2021-01-04", end)


def test_cash_and_split_preserve_wealth_and_do_not_use_vendor_adjustment():
    bars, div, evidence = fixture()
    result = run(bars, div, evidence)
    assert [r["total_return_index"] for r in result["data"]] == [100, 100, 100]
    assert result["data"][0]["total_return"] is None
    assert result["data"][1]["payment_date"] == "2021-01-08"
    assert result["data"][2]["share_multiplier"] == 2


def test_half_up_three_decimal_limits_use_reference_not_yesterdays_close():
    bars, div, evidence = fixture()
    bars[1].update(pre_close=9.005)
    row = run(bars, div, evidence)["data"][1]
    assert row["up_limit"] == 9.906
    assert row["down_limit"] == 8.105


def test_unknown_gaps_and_conflicting_events_fail_closed():
    bars, div, evidence = fixture()
    with pytest.raises(ValueError, match="missing bar"):
        run(bars, div, evidence, calendar=[b["trade_date"] for b in bars] + ["2021-01-07"])
    with pytest.raises(ValueError, match="amount"):
        run(bars, [{**div[0], "div_cash": 0.5}], evidence)
    with pytest.raises(ValueError, match="coverage"):
        run(bars, div, evidence, end="2026-10-21")


def test_reviewed_halt_carries_valuation_but_not_price_or_trading_permission():
    bars, div, evidence = fixture()
    evidence["events"] = [{"symbol": "510300.SH", "date": "2021-01-07", "source_url": "issuer"}]
    row = run(bars, div, evidence, calendar=[b["trade_date"] for b in bars] + ["2021-01-07"])["data"][-1]
    assert row["daily_state"] == "full_day_suspended"
    assert row["total_return_index"] == 100
    assert row["up_limit"] is None
    assert row["intraday_state"] == "unknown"


def test_price_outside_rule_and_duplicate_bars_rejected():
    bars, div, evidence = fixture()
    with pytest.raises(ValueError, match="Duplicate"):
        run(bars + [bars[0]], div, evidence)
    bars[0]["high"] = 12
    with pytest.raises(ValueError, match="outside"):
        run(bars, div, evidence)


def test_rule_override_only_applies_from_effective_date():
    bars, div, evidence = fixture()
    evidence["limit_rules"]["overrides"] = [{
        "symbol": "510300.SH", "start": "2021-01-05", "rate": ".2", "source_url": "exchange"}]
    rows = run(bars, div, evidence)["data"]
    assert [r["limit_rate"] for r in rows] == [.1, .2, .2]
