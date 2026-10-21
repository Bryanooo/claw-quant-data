import pytest

from service.research.technical_indicators import (
    common_indicator_pack,
    indicator_parameter_profile,
    parameterized_indicator_pack,
)


def test_common_indicator_pack_exposes_auditable_aligned_series():
    closes = [100.0 + index * 0.2 for index in range(260)]
    highs = [value + 1.0 for value in closes]
    lows = [value - 1.0 for value in closes]
    volumes = [1000.0 + index * 5 for index in range(260)]

    result = common_indicator_pack(highs, lows, closes, volumes)

    assert result["status"] == "ready"
    assert result["formula_version"] == "common-technicals-v1"
    assert all(len(values) == 260 for values in result["series"].values())
    assert result["latest"]["ema_20"] > result["latest"]["ema_50"]
    assert result["latest"]["ema_50"] > result["latest"]["ema_200"]
    assert result["latest"]["bias_6"] > 0
    assert result["latest"]["bbi"] is not None
    assert result["latest"]["natr_14"] > 0
    assert result["latest"]["vroc_12"] > 0
    assert result["latest"]["force_index_13_normalized"] > 0


def test_ppo_is_scale_invariant_and_raw_pvt_is_marked_path_dependent():
    closes = [20.0 + index * 0.1 for index in range(220)]
    volumes = [1000.0 + (index % 9) * 20 for index in range(220)]
    base = common_indicator_pack(
        [value + 0.8 for value in closes],
        [value - 0.8 for value in closes],
        closes,
        volumes,
    )
    scaled = common_indicator_pack(
        [(value + 0.8) * 10 for value in closes],
        [(value - 0.8) * 10 for value in closes],
        [value * 10 for value in closes],
        volumes,
    )

    assert scaled["latest"]["ppo"] == pytest.approx(base["latest"]["ppo"])
    assert scaled["latest"]["natr_14"] == pytest.approx(base["latest"]["natr_14"])
    assert "pvt" in base["comparability"]["path_dependent_raw"]


def test_common_indicator_pack_rejects_misaligned_inputs():
    with pytest.raises(ValueError):
        common_indicator_pack([1.0], [1.0], [1.0], [])


def test_common_indicator_pack_marks_unusable_volume_as_missing_input():
    closes = [10.0 + index * 0.01 for index in range(220)]
    result = common_indicator_pack(
        [value + 0.2 for value in closes],
        [value - 0.2 for value in closes],
        closes,
        [0.0] * len(closes),
    )

    assert result["status"] == "missing_input"
    assert result["latest"]["vroc_12"] is None


def test_frequency_profiles_use_bar_appropriate_common_windows():
    assert indicator_parameter_profile("1d")["sma"] == [
        5, 10, 20, 30, 60, 120, 250
    ]
    assert indicator_parameter_profile("1w")["sma"] == [
        5, 10, 20, 30, 40, 52
    ]
    assert indicator_parameter_profile("1mo")["sma"] == [
        3, 6, 12, 24, 36, 60
    ]


def test_parameterized_pack_exposes_common_families_and_structure_metrics():
    closes = [100 + index * 0.15 + (index % 7) * 0.03 for index in range(300)]
    opens = [value - 0.1 for value in closes]
    highs = [value + 1.0 for value in closes]
    lows = [value - 1.0 for value in closes]
    volumes = [1000 + index * 2 for index in range(300)]

    result = parameterized_indicator_pack(
        opens, highs, lows, closes, volumes, timeframe="1d"
    )

    assert result["status"] == "ready"
    assert set(result["latest"]["rsi"]) == {"6", "12", "14", "24"}
    assert set(result["latest"]["roc"]) == {"5", "10", "20", "60", "120"}
    assert set(result["latest"]["cci"]) == {"14", "20"}
    assert result["latest"]["tsi_25_13"] is not None
    assert result["latest"]["bollinger_20_2"]["percent_b"] is not None
    structure = result["latest"]["structure"]
    assert structure["regression_60"]["r_squared"] is not None
    assert structure["atr_5_to_20_ratio"] is not None
    assert result["latest"]["candle_geometry"]["body_to_range"] is not None


def test_parameterized_pack_marks_long_monthly_windows_as_limited():
    closes = [10 + index * 0.1 for index in range(24)]
    result = parameterized_indicator_pack(
        [value - 0.1 for value in closes],
        [value + 0.2 for value in closes],
        [value - 0.2 for value in closes],
        closes,
        [1000.0] * len(closes),
        timeframe="1mo",
    )

    assert result["status"] == "limited_history"
    assert result["latest"]["sma"]["60"] is None
    assert result["parameters"]["roc"] == [3, 6, 12, 24, 36]
