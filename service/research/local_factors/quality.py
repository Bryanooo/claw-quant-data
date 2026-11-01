"""Conservative per-feature input readiness, separate from execution/comparison.

Only proven listing-age exclusions are accepted. A missing bar in an old
security, missing financial input or an unclassified undefined result never
becomes ready merely because another feature has a value.
"""
import re
import math

import pandas as pd

from .catalog import FACTOR_SPECS, MAX_ABS_FACTOR_VALUE
from .ownership import TECHNICAL_FEATURES, SHARED_TECHNICAL_FIELDS


_TECHNICAL_REQUIRED_BARS = {
    "prior_high_20": 21, "atrv_sma_14": 15, "niumen_line": 21,
    "confirmation_line": 21, "signal_ma_10": 10, "cost_20": 20,
    "cost_60": 60,
    "bbi": 24, "bbi_distance_pct": 24,
    "ppo_12_26": 26, "ppo_signal_9": 26, "ppo_histogram": 26,
    "natr_14": 14, "keltner_middle_20": 20,
    "keltner_upper_20_2": 20, "keltner_lower_20_2": 20,
    "ttm_squeeze_momentum": 20,
    "trix_12": 2, "trix_signal_9": 2, "trix_histogram": 2,
    "pvt_20_change": 21, "vroc_12": 13, "vroc_20": 21,
    "force_index_13": 2, "force_index_13_normalized": 20,
    "tsi_25_13": 37,
    "bollinger_percent_b_20_2": 20,
    "bollinger_bandwidth_20_2_pct": 20,
    "body_return": 1, "range_to_open": 1, "body_to_range": 1,
    "upper_shadow_to_open": 1, "upper_shadow_to_range": 1,
    "lower_shadow_to_open": 1, "lower_shadow_to_range": 1,
    "close_location_to_open": 1, "close_location_to_range": 1,
    "range_position_60": 60, "atr_5_to_20_ratio": 20,
    "retracement_depth_20": 20, "retracement_depth_120": 120,
    "regression_slope_20_pct": 20, "regression_r_squared_20": 20,
    "regression_slope_60_pct": 60, "regression_r_squared_60": 60,
    "breakout_over_prior_high_60_atr": 61,
    "high_touch_count_60_1pct": 60, "low_touch_count_60_1pct": 60,
}

_ZERO_RANGE_FEATURES = frozenset({
    "body_to_range", "upper_shadow_to_range", "lower_shadow_to_range",
    "close_location_to_range",
})


def required_bars(name: str) -> int | None:
    if name in _TECHNICAL_REQUIRED_BARS:
        return _TECHNICAL_REQUIRED_BARS[name]
    match = re.fullmatch(r"ema_(\d+)_distance_pct", name)
    if match:
        return int(match[1])
    match = re.fullmatch(r"bias_(\d+)", name)
    if match:
        return int(match[1])
    # Do not consume the separator after a match: it also introduces the
    # next window in names such as bias_turn_21d_504d.
    windows = [int(x) for x in re.findall(r"(?:^|_)(\d+)d(?=_|$)", name)]
    if windows:
        return max(windows) + 1
    match = re.fullmatch(r"(?:ema|sma|rsi|roc|atr|cci|natr|cost)_(\d+)", name)
    if match:
        return int(match[1]) + 1
    return {"ma_20d": 20, "rsi": 15, "niumen_line": 21,
            "confirmation_line": 21, "prior_high_20": 21,
            "atrv_sma_14": 15, "signal_ma_10": 10}.get(name)


def _finite(value) -> bool:
    return (
        value is not None
        and pd.notna(value)
        and math.isfinite(float(value))
        and abs(float(value)) <= MAX_ABS_FACTOR_VALUE
    )


def _financial_exclusion(name: str, code: str, panel) -> str | None:
    """Return only exclusions supported by point-in-time source evidence."""

    if panel is None:
        return None
    if name == "lra_yoy":
        current = panel.values("current", "longterm_receivable").get(code)
        year_ago = panel.values("year_ago", "longterm_receivable").get(code)
        current_assets = panel.values("current", "total_assets").get(code)
        year_ago_assets = panel.values("year_ago", "total_assets").get(code)
        # Both comparable balance sheets exist, but neither reports this line
        # item.  That is an auditable non-applicable domain, not lost data.
        if (
            _finite(current_assets) and _finite(year_ago_assets)
            and not _finite(current) and not _finite(year_ago)
        ):
            return "line_item_not_reported_in_comparable_statements"
        if _finite(year_ago) and float(year_ago) == 0:
            return "undefined_for_zero_growth_base"
    if name == "pegh5":
        annual = panel.values("annual", "basic_eps").get(code)
        five_year = panel.values("annual_five_year_ago", "basic_eps").get(code)
        profit = panel.values("ttm", "net_profit_parent").get(code)
        shares = panel.values("current", "total_share").get(code)
        if all(_finite(value) for value in (annual, five_year, profit, shares)):
            ratio = float(annual) / float(five_year) if float(five_year) else math.nan
            eps_ttm = float(profit) / float(shares) if float(shares) else math.nan
            if not math.isfinite(ratio) or ratio <= 0 or eps_ttm == 0:
                return "undefined_for_nonpositive_five_year_growth_base"
    return None


def financial_input_diagnostic(name, code, panel):
    """Explain missing inputs without turning absence into applicability proof."""
    required = {
        'ebitda_to_market': (('ttm', 'ebitda'),),
        'fixed_asset_turnover': (('ttm', 'revenue'), ('current', 'fix_assets')),
        'np_to_fixed_assets_yoy': tuple((b, m) for b in ('current', 'year_ago')
                                      for m in ('net_profit', 'fix_assets')),
        'pegh5': (('annual', 'basic_eps'), ('annual_five_year_ago', 'basic_eps'),
                  ('ttm', 'net_profit_parent'), ('current', 'total_share')),
        'lra_yoy': (('current', 'longterm_receivable'),
                    ('year_ago', 'longterm_receivable')),
        'np_to_deferred_tax_yoy': tuple((b, m) for b in ('current', 'year_ago')
                                       for m in ('net_profit', 'defer_tax_assets')),
        'gpm_qoq': tuple((b, m) for b in ('current', 'previous')
                        for m in ('revenue', 'oper_cost')),
        'delta_inventory_turnover': (('ttm', 'oper_cost'),
                                     ('ttm_year_ago', 'oper_cost'),
                                     ('current', 'inventories'),
                                     ('year_ago', 'inventories')),
        'delta_gpm': tuple((b, m) for b in ('ttm', 'ttm_year_ago')
                           for m in ('revenue', 'oper_cost')),
        'income_tax_yoy': (('ttm', 'income_tax'), ('ttm_year_ago', 'income_tax')),
        'quality_composite': (
            ('current', 'total_assets'), ('current', 'equity'),
            *(( 'ttm', m) for m in ('total_profit', 'net_profit', 'revenue',
                                   'operating_cash_inflow', 'investing_cash_inflow')),
        ),
        'np_to_total_expenses_yoy': tuple((b, m) for b in ('current', 'year_ago')
                                        for m in ('net_profit', 'sell_exp', 'admin_exp', 'fin_exp')),
        'expenses_to_equity_yoy': tuple((b, m) for b in ('current', 'year_ago')
                                      for m in ('equity_parent', 'sell_exp', 'admin_exp', 'fin_exp')),
        'np_to_inventory_yoy': tuple((b, m) for b in ('current', 'year_ago')
                                    for m in ('net_profit', 'inventories')),
    }.get(name)
    if required is None or panel is None:
        return None
    missing = [f'{bucket}.{metric}' for bucket, metric in required
               if not _finite(panel.values(bucket, metric).get(code))]
    if name == 'ebitda_to_market' and not _finite(panel.total_mv.get(code)):
        missing.append('market.total_mv')
    if name == 'pegh5' and not _finite(panel.close.get(code)):
        missing.append('market.close')
    if missing:
        return 'missing_financial_inputs:' + ','.join(missing)
    # These are diagnostics, not exemptions: keep zero-domain cases unresolved
    # until the contract explicitly declares their applicability.
    zero = [f'{bucket}.{metric}' for bucket, metric in required
            if panel.values(bucket, metric).get(code) == 0]
    if zero:
        return 'financial_zero_input_requires_domain_audit:' + ','.join(zero)
    return 'nonfinite_result_with_present_financial_inputs'


def audit_security(code, values, technical, panel, financial_panel=None) -> dict:
    if code not in panel.alpha101.close.columns:
        return {"status": "not_expected", "technical_status": "not_expected", "reason": "no_target_daily_bar",
                "unresolved": {}, "excluded": {}}
    # Listing-date evidence, not observed-row count, establishes warmup age.
    listing = None if panel.listing_dates is None else panel.listing_dates.get(code)
    listed_at = pd.to_datetime(listing, format="%Y%m%d", errors="coerce")
    dates = panel.alpha101.close.index
    age = int((dates >= listed_at).sum()) if pd.notna(listed_at) and listed_at >= dates[0] else None
    unresolved, excluded = {}, {}
    latest_high = panel.alpha101.high.iloc[-1].get(code)
    latest_low = panel.alpha101.low.iloc[-1].get(code)
    zero_range = (
        pd.notna(latest_high) and pd.notna(latest_low)
        and float(latest_high) == float(latest_low)
    )
    observed_sessions = int(panel.alpha101.close[code].notna().sum())
    unexplained_market_gaps = int(
        panel.unexplained_market_gaps.get(code, 0)
        if panel.unexplained_market_gaps is not None else 0
    )
    technical_names = set(TECHNICAL_FEATURES) | set(SHARED_TECHNICAL_FIELDS.values()) | {'price_adjustment'}
    technical_bars = technical.get('source_bar_count')
    for name in [s.name for s in FACTOR_SPECS] + list(TECHNICAL_FEATURES):
        value = values[name].get(code) if name in values else technical.get(name)
        if _finite(value):
            continue
        need = required_bars(name)
        if (
            value is not None and pd.notna(value)
            and math.isfinite(float(value))
            and abs(float(value)) > MAX_ABS_FACTOR_VALUE
        ):
            excluded[name] = "numerically_unstable_extreme_value"
        elif age is not None and need is not None and age < need:
            excluded[name] = "insufficient_listing_history"
        elif (
            name in technical_names and need is not None and age is not None
            and isinstance(technical_bars, int) and 0 < technical_bars < need
            and panel.unexplained_market_gaps is not None
            and unexplained_market_gaps == 0 and observed_sessions == age
        ):
            # Technical indicators consume actual traded bars, not the padded
            # market panel. Only a fully explained listing window permits this
            # exclusion: the loader pads independently documented suspensions.
            excluded[name] = 'insufficient_traded_bars_with_documented_suspensions'
        elif name in _ZERO_RANGE_FEATURES and zero_range:
            excluded[name] = "undefined_for_zero_price_range"
        elif (
            name.startswith("alpha101_")
            and observed_sessions >= 512
            and unexplained_market_gaps == 0
            and all(frame[code].iloc[-512:].notna().all() for frame in (
                panel.alpha101.open, panel.alpha101.high, panel.alpha101.low,
                panel.alpha101.close, panel.alpha101.volume,
            ))
        ):
            # Alpha101 formulae contain conditional ranks, powers and explicit
            # divisions.  With a complete 512-session OHLCV input window, a
            # non-finite result is a formula-domain outcome for that security;
            # cross-sectional provider validation remains responsible for
            # detecting an incorrect implementation.
            excluded[name] = "undefined_formula_domain_with_complete_market_window"
        elif reason := _financial_exclusion(
            name, code, financial_panel
        ):
            excluded[name] = reason
        else:
            unresolved[name] = (
                financial_input_diagnostic(name, code, financial_panel)
                or "missing_input_or_undefined_requires_audit"
            )
    if technical.get("adjustment_status") != "applied":
        unresolved["price_adjustment"] = "missing_or_incomplete_adjustment"
    return {"status": "partial" if unresolved else "ready",
            "technical_status": "partial" if technical_names & unresolved.keys() else "ready",
            "unresolved": unresolved, "excluded": excluded,
            "listing_sessions_observed": age,
            "technical_traded_bars_observed": technical_bars,
            "market_sessions_observed": observed_sessions,
            "unexplained_market_gap_sessions": unexplained_market_gaps}
