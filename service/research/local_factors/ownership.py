"""Single-source ownership for materialized daily research features.

Aliases are representations, not separate values. Supplier comparisons must
never participate in value resolution.
"""

from .catalog import FACTOR_BY_NAME

SHARED_TECHNICAL_FIELDS = {
    "rsi_14": "rsi",
    "macd_dif_12_26": "dif",
    "macd_dea_9": "dea",
    "macd_histogram_12_26_9": "MACD",
    "sma_20": "ma_20d",
    "return_5d": "return_5d",
    "alpha101_101": "alpha101_101",
}

# Same formula but different presentation units/names.
TECHNICAL_ALIASES = {
    "roc_5": ("return_5d", 100.0),
}

INTERNAL_DATASETS = frozenset({"factor_value", "tushare_norm_factor_value"})

# Registered numeric outputs only. Status, inputs and metadata are not factors.
TECHNICAL_FEATURES = tuple("""
prior_high_20 atrv_sma_14 niumen_line confirmation_line signal_ma_10 cost_20 cost_60
ema_20 ema_50 ema_200 ema_20_distance_pct ema_50_distance_pct ema_200_distance_pct
bias_6 bias_12 bias_24 bbi bbi_distance_pct ppo_12_26 ppo_signal_9 ppo_histogram
natr_14 keltner_middle_20 keltner_upper_20_2 keltner_lower_20_2 ttm_squeeze_momentum
trix_12 trix_signal_9 trix_histogram pvt_20_change vroc_12 vroc_20
force_index_13 force_index_13_normalized sma_30 ema_5 ema_10 ema_12 ema_26 ema_100
rsi_6 rsi_12 rsi_24 roc_10 roc_20 roc_60 roc_120 cci_14 cci_20 atr_14 atr_20
natr_20 tsi_25_13 bollinger_percent_b_20_2 bollinger_bandwidth_20_2_pct
body_return range_to_open body_to_range upper_shadow_to_open upper_shadow_to_range
lower_shadow_to_open lower_shadow_to_range close_location_to_open close_location_to_range
range_position_60 atr_5_to_20_ratio retracement_depth_20 retracement_depth_120
regression_slope_20_pct regression_r_squared_20 regression_slope_60_pct regression_r_squared_60
breakout_over_prior_high_60_atr high_touch_count_60_1pct low_touch_count_60_1pct
""".split())


def technical_payload(row: dict) -> dict:
    """Keep only values not already owned by an array slot or alias."""
    excluded = set(SHARED_TECHNICAL_FIELDS) | set(TECHNICAL_ALIASES)
    excluded |= {"snapshot_date", "ts_code", "source_execution_id", "computed_at"}
    return {
        key: value.isoformat() if hasattr(value, "isoformat") else value
        for key, value in row.items() if key not in excluded
    }


def resolve_feature(name: str) -> tuple[str, float]:
    canonical, multiplier = TECHNICAL_ALIASES.get(name, (name, 1.0))
    return SHARED_TECHNICAL_FIELDS.get(canonical, canonical), multiplier


def canonical_position(name: str) -> int | None:
    canonical, _ = resolve_feature(name)
    item = FACTOR_BY_NAME.get(canonical)
    return item.position if item else None
