from datetime import date, timedelta
from pathlib import Path

from service.orchestration_v2.transformations import (
    FORMULA_VERSION,
    build_technical_factor_snapshot_row,
)


def _bars(count: int) -> list[dict]:
    start = date(2026, 1, 1)
    return [
        {
            "trade_date": start + timedelta(days=index),
            "open": 9.5 + index,
            "high": 11.0 + index,
            "low": 9.0 + index,
            "close": 10.0 + index,
            "pre_close": 9.0 + index,
            "vol": 100.0,
            "amount": 100.0 * (10.0 + index) / 10.0,
            "adj_factor": 1.0,
        }
        for index in range(count)
    ]


def test_snapshot_row_materializes_exact_niumen_and_cost_contracts():
    rows = _bars(260)
    result = build_technical_factor_snapshot_row(
        "000001.SZ", date(2026, 10, 9), rows, source_execution_id=9
    )

    assert result["calculation_status"] == "ready"
    assert result["source_bar_count"] == 260
    assert result["adjustment_matched_count"] == 260
    assert result["prior_high_20"] == 269.0
    assert result["atrv_sma_14"] == 2.0
    assert result["niumen_line"] == 270.0
    assert result["confirmation_line"] == 271.0
    assert result["cost_20"] == 259.5
    assert result["cost_60"] == 239.5
    assert result["common_indicator_status"] == "ready"
    assert result["ema_200"] is not None
    assert result["natr_14"] is not None
    assert result["unavailable_reasons"] == []
    assert result["formula_version"] == FORMULA_VERSION
    assert result["source_execution_id"] == 9


def test_snapshot_row_keeps_insufficient_history_visible():
    result = build_technical_factor_snapshot_row(
        "001234.SZ", date(2026, 10, 9), _bars(10)
    )

    assert result["calculation_status"] == "insufficient_history"
    assert result["niumen_line"] is None
    assert result["cost_20"] is None
    assert result["cost_60"] is None
    assert {item["indicator"] for item in result["unavailable_reasons"]} == {
        "niumen_confirmation",
        "cost_20",
        "cost_60",
        "common_technical_pack",
        "parameterized_technical_pack",
    }


def test_snapshot_row_does_not_mislabel_missing_factors_as_short_history():
    rows = _bars(60)
    for row in rows[:20]:
        row["adj_factor"] = None

    result = build_technical_factor_snapshot_row(
        "002731.SZ", date(2026, 10, 9), rows
    )

    assert result["adjustment_status"] == "partial_history"
    assert result["cost_60_status"] == "missing_input"
    assert any(
        item["indicator"] == "price_adjustment"
        and item["reason"] == "adjustment_partial_history"
        for item in result["unavailable_reasons"]
    )


def test_snapshot_universe_includes_a_security_on_its_delist_date():
    source = Path(
        "service/orchestration_v2/transformations.py"
    ).read_text(encoding="utf-8")

    assert "stock.delist_date >= %s" in source
    assert "stock.delist_date > %s" not in source
