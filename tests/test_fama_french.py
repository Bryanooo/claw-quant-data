import pytest

from service.research.fama_french import daily_factors, FF3_FORMULA_VERSION
from service.orchestration_v2.transformations import fama_french_sources_complete


def _universe(size=40):
    """Build a simple eligible cross-section with known size and B/M spread."""
    returns = [0.01 + i * 0.001 for i in range(size)]
    caps = [1000.0 + i * 10.0 for i in range(size)]
    book_equity = [
        caps[i] * (0.2 + ((i * 17) % size) / max(size - 1, 1) * 1.2)
        for i in range(size)
    ]
    return returns, caps, book_equity


def test_ready_universe_produces_all_three_factors():
    returns, caps, book_equity = _universe()
    result = daily_factors(returns, caps, book_equity, risk_free=0.0)

    assert result["status"] == "ready"
    assert result["formula_version"] == FF3_FORMULA_VERSION
    assert result["mkt"] is not None
    assert result["smb"] is not None
    assert result["hml"] is not None
    assert result["eligible_count"] == 40
    assert result["small_count"] + result["big_count"] == 40


def test_mkt_is_value_weighted_return_minus_risk_free():
    # Two cap buckets: half at 1000, half at 3000, returns 0.10 vs 0.20.
    returns = [0.10] * 20 + [0.20] * 20
    caps = [1000.0] * 20 + [3000.0] * 20
    book_equity = [500.0] * 20 + [1500.0] * 20
    # value-weighted = (0.10*20000 + 0.20*60000) / 80000 = 0.175
    result = daily_factors(returns, caps, book_equity, risk_free=0.02)
    assert result["mkt"] == pytest.approx(0.175 - 0.02)


def test_smb_signs_follow_size_premium():
    # Each size bucket contains low/mid/high B/M names; small earns more.
    caps = [100.0] * 15 + [1000.0] * 15
    returns = [0.05] * 15 + [0.01] * 15
    book_equity = [caps[index] * (0.2 + (index % 3) * 0.5) for index in range(30)]
    result = daily_factors(returns, caps, book_equity)
    assert result["status"] == "ready"
    assert result["smb"] > 0


def test_hml_signs_follow_value_premium():
    # Both size buckets contain all B/M buckets; high B/M earns more.
    caps = [100.0] * 15 + [1000.0] * 15
    ratios = [0.2, 0.7, 1.2] * 10
    book_equity = [cap * ratio for cap, ratio in zip(caps, ratios)]
    returns = [0.05 if ratio == 1.2 else 0.01 for ratio in ratios]
    result = daily_factors(returns, caps, book_equity)
    assert result["status"] == "ready"
    assert result["hml"] > 0


def test_thin_universe_is_insufficient():
    returns, caps, book_equity = _universe(size=5)
    result = daily_factors(returns, caps, book_equity)
    assert result["status"] == "insufficient_universe"
    # MKT is still defined (value-weighted mean needs no sort), but the
    # size/value splits cannot be built from a thin sample.
    assert result["mkt"] is not None
    assert result["smb"] is None
    assert result["hml"] is None


def test_stocks_without_equity_still_enter_mkt_and_smb():
    returns = [0.10, 0.10, 0.10, 0.10] * 10
    caps = [100.0] * 40
    book_equity = [None] * 40  # no equity disclosed anywhere
    result = daily_factors(returns, caps, book_equity)
    # MKT remains observable, but neither 2x3 factor may be certified.
    assert result["status"] == "insufficient_universe"
    assert result["mkt"] is not None
    assert result["smb"] is None
    assert result["hml"] is None


def test_smb_uses_six_size_value_portfolios_not_a_plain_size_split():
    caps = [100.0] * 15 + [1000.0] * 15
    ratios = [0.2, 0.7, 1.2] * 10
    book_equity = [cap * ratio for cap, ratio in zip(caps, ratios)]
    returns = [0.02 + (0.01 if cap == 100.0 else 0.0) for cap in caps]

    result = daily_factors(returns, caps, book_equity)

    assert set(result["portfolio_returns"]) == {
        "small_low", "small_mid", "small_high",
        "big_low", "big_mid", "big_high",
    }
    assert result["smb"] == pytest.approx(0.01)


def test_rejects_misaligned_inputs():
    with pytest.raises(ValueError):
        daily_factors([0.01, 0.02], [100.0], [50.0, 60.0])


def test_source_reconciliation_requires_every_daily_return_to_have_cap():
    assert fama_french_sources_complete(100, 100) is True
    assert fama_french_sources_complete(100, 99) is False
    assert fama_french_sources_complete(0, 0) is False
