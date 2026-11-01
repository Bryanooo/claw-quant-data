"""Stable 272-factor catalog and overlap governance.

Positions are an on-disk ABI: ``local_factor_snapshot.factor_values[n-1]``
always identifies the catalog row whose ``position`` is ``n``.  A formula or
position change therefore requires a new schema version rather than an in-place
edit.
"""

from __future__ import annotations

from dataclasses import dataclass

from .alpha101_formulas import ALPHA101_FORMULAS

FACTOR_SCHEMA_VERSION = "local-272-v4"
FACTOR_IMPLEMENTATION_VERSION = "local-272-quality-v3"
# Algebraically finite divisions can still be numerically unstable.  No
# legitimate value in this catalog approaches this storage guardrail.
MAX_ABS_FACTOR_VALUE = 1e100


@dataclass(frozen=True, slots=True)
class FactorSpec:
    position: int
    name: str
    family: str
    formula: str
    computation_group: str
    overlap_kind: str = "none"
    overlap_dataset: str | None = None
    overlap_field: str | None = None
    convention_note: str | None = None


FAMILY_NAMES: dict[str, tuple[str, ...]] = {
    "Growth": (
        "peg_252d", "np_ttm_qoq", "yoy_net_profit", "yoy_ocf", "sa",
        "gross_margin_qoq", "pa", "yoy_roa", "yoy_net_asset",
        "yoy_revenue", "yoy_roe", "yoy_total_asset", "eaa", "eap",
        "asset_growth_qoq",
    ),
    "Liquidity": (
        "avg_turnover_5d", "avg_turnover_10d", "avg_turnover_20d",
        "amount_ma_20d", "turnover_ma_20d", "sum_abs_rtn_amount_20d",
        "turnover_ma_20d_120d", "avg_turnover_21d", "std_turnover_21d",
        "bias_std_turn_21d_252d", "bias_turn_21d_252d",
        "bias_std_turn_21d_504d", "bias_turn_21d_504d",
        "std_turnover_42d", "avg_turnover_42d", "bias_turn_42d_252d",
        "bias_std_turn_42d_252d", "bias_std_turn_42d_504d",
        "bias_turn_42d_504d", "std_turnover_63d", "avg_turnover_63d",
        "bias_turn_63d_252d", "bias_std_turn_63d_252d",
        "bias_std_turn_63d_504d", "bias_turn_63d_504d",
        "avg_turnover_126d", "std_turnover_126d",
        "bias_turn_126d_252d", "bias_std_turn_126d_252d",
        "bias_turn_126d_504d", "bias_std_turn_126d_504d",
        "std_turnover_252d", "avg_turnover_252d",
        "volume_alpha_300d_000001", "volume_alpha_300d_000300",
    ),
    "Momentum": (
        "return_5d", "ma_20d", "return_21d", "return_42d",
        "price_position_ir_60d", "return_63d", "alpha_125d_000300",
        "return_126d", "alpha_250d_000300", "return_252d",
        "alpha_500d_000300", "alpha_528d_000001",
        "alpha_792d_000001", "alpha_1000d_000300",
        "alpha_1320d_000001", "rsrs", "MACD", "dif", "dea",
        "days_down_up",
    ),
    "Quality": (
        "roe_ttm_lag63d", "debt_asset_ratio", "eps_ttm",
        "financial_leverage", "gpm_ttm", "icr", "income_tax_yoy",
        "np_to_inventory_yoy", "npm_q", "quality_composite",
        "ar_ap_to_revenue", "asset_turnover", "delta_current_ratio",
        "delta_de", "gpm_q", "cash_profit_ratio", "delta_opm", "eps_q",
        "eps_y", "delta_npm", "market_value_leverage", "npm_y", "opm_y",
        "quick_ratio", "delta_gpm", "gpm_y", "np_to_total_expenses_yoy",
        "np_to_deferred_tax_yoy", "roe_y", "roa_q", "gpm_qoq",
        "delta_inventory_turnover", "delta_roa", "fixed_asset_turnover",
        "npm_ttm", "opm_ttm", "receivable_turnover", "cfcr",
        "delta_cash_ratio", "lra_yoy", "np_to_fixed_assets_yoy",
        "np_to_salary_yoy", "npm_q_qoq", "npm_tsh", "npm_ttm_qoq",
        "cash_ratio", "current_ratio", "de", "delta_asset_turnover",
        "delta_quick_ratio", "delta_roe", "inventory_turnover", "roa_ttm",
        "roe_ttm", "tax_surcharge_yoy", "equity_turnover",
        "expenses_to_equity_yoy", "roa_y", "opt_tpro",
    ),
    "Reversal": ("small_cap_reversal_21d", "rsi", "price_dist"),
    "Risk": (
        "days_beyond_upper_lower_21d", "return_std_21d", "high_low_21d",
        "high_low_42d", "return_std_42d", "sharpe_60d",
        "beta_60d_000300", "return_std_63d", "high_low_63d",
        "volume_beta_120d_000300", "beta_125d_000300", "high_low_126d",
        "return_std_126d", "beta_250d_000300", "return_std_252d",
        "high_low_252d", "beta_500d_000300", "sharpe_750d",
        "adjusted_sharpe_750d", "beta_1000d_000300",
        "sigma_1320d_000001", "beta_1320d_000001",
        "beta_consistency_1320d_000300", "sigma_1320d_000300", "log_price",
    ),
    "Size": ("float_size", "nl_size", "size"),
    "Value": (
        "dividend_yield_3y_avg", "pegh5", "etp5", "ncf_to_market",
        "fcf_to_market", "ebitda_to_market", "earnings_to_price",
        "book_to_market", "earnings_cut_to_market", "ocf_to_market",
        "sales_to_market",
    ),
}


# Existing products with a genuinely equivalent formula are reused by the
# materializer when their price basis and date are identical. ``primitive``
# means the shared implementation is reused but the value must be evaluated on
# the local factor panel (for example for a ten-year backfill).
OVERLAPS: dict[str, tuple[str, str, str, str | None]] = {
    "rsi": ("exact_value", "technical_factor_snapshot", "rsi_14", "Wilder 14 on the same adjusted-price basis"),
    "MACD": ("exact_value", "technical_factor_snapshot", "macd_histogram_12_26_9", None),
    "dif": ("exact_value", "technical_factor_snapshot", "macd_dif_12_26", None),
    "dea": ("exact_value", "technical_factor_snapshot", "macd_dea_9", None),
    "ma_20d": ("exact_value", "technical_factor_snapshot", "sma_20", None),
    "return_5d": ("exact_value", "technical_factor_snapshot", "return_5d", None),
    "alpha101_101": (
        "exact_value", "technical_factor_snapshot", "alpha101_101", None,
    ),
    "size": ("primitive", "stock_daily_basic", "total_mv", "negative natural log"),
    "float_size": ("primitive", "stock_daily_basic", "circ_mv", "negative natural log"),
}


def _build_specs() -> tuple[FactorSpec, ...]:
    specs: list[FactorSpec] = []
    position = 1
    for number, formula in ALPHA101_FORMULAS.items():
        name = f"alpha101_{number}"
        overlap = OVERLAPS.get(name, ("none", None, None, None))
        specs.append(FactorSpec(
            position, name, "Alpha101", formula, "alpha101",
            overlap[0], overlap[1], overlap[2], overlap[3],
        ))
        position += 1
    for family, names in FAMILY_NAMES.items():
        computation_group = (
            "financial" if family in {"Growth", "Quality", "Value"}
            else "market"
        )
        for name in names:
            overlap = OVERLAPS.get(name, ("none", None, None, None))
            specs.append(FactorSpec(
                position, name, family, name, computation_group,
                overlap[0], overlap[1], overlap[2], overlap[3],
            ))
            position += 1
    return tuple(specs)


FACTOR_SPECS = _build_specs()
FACTOR_COUNT = len(FACTOR_SPECS)
FACTOR_BY_NAME = {item.name: item for item in FACTOR_SPECS}

assert FACTOR_COUNT == 272
assert len(FACTOR_BY_NAME) == FACTOR_COUNT
assert tuple(item.position for item in FACTOR_SPECS) == tuple(range(1, 273))
