"""Conservative per-feature input readiness, separate from execution/comparison.

Only evidenced listing-age and explicitly checked formula-domain exclusions
are accepted. Missing input or an unclassified result never becomes ready
merely because another feature has a value.
"""
import re
import math

import numpy as np
import pandas as pd

from .alpha101 import minimum_history
from .alpha101_formulas import ALPHA101_FORMULAS
from .catalog import FACTOR_BY_NAME, FACTOR_SPECS, MAX_ABS_FACTOR_VALUE
from .ownership import TECHNICAL_FEATURES, SHARED_TECHNICAL_FIELDS


_INDUSTRY_LEVELS = {
    f'alpha101_{n}': tuple(sorted(set(re.findall(r'IndClass\.(\w+)', formula))))
    for n, formula in ALPHA101_FORMULAS.items() if 'IndClass.' in formula
}


def _missing_industry(name, code, alpha):
    missing = []
    for level in _INDUSTRY_LEVELS.get(name, ()):
        groups = getattr(alpha, level, None)
        if groups is None:
            groups = getattr(alpha, 'industry', None)
        value = (groups.iloc[-1].get(code) if isinstance(groups, pd.DataFrame) and len(groups)
                 else groups.get(code) if isinstance(groups, pd.Series) else None)
        if pd.isna(value) or value in ('', '__unknown__'):
            missing.append(level)
    return 'missing_market_inputs:industry_classification.' + ','.join(missing) if missing else None


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
    # A 300-observation regression of 5-session volume-sum changes consumes
    # 305 source sessions, not 301. Intraday price position needs no lag.
    if name in {'volume_alpha_300d_000001', 'volume_alpha_300d_000300'}:
        return 305
    if name in FACTOR_BY_NAME and FACTOR_BY_NAME[name].computation_group == 'financial':
        return None
    if name == 'volume_beta_120d_000300':
        return 125
    if name == 'days_beyond_upper_lower_21d':
        return 41
    if name.startswith('alpha101_') and name in FACTOR_BY_NAME:
        return minimum_history(int(name.rsplit('_', 1)[1]))
    if name == 'rsrs':
        return 217
    if match := re.fullmatch(r"high_low_(\d+)d", name):
        return int(match[1])
    if name == 'price_position_ir_60d':
        return 60
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
        if name.startswith(("avg_turnover_", "std_turnover_", "bias_turn_", "bias_std_turn_",
                            "turnover_ma_", "amount_ma_")):
            return max(windows)
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
            if ratio == 1 and shares != 0 and eps_ttm != 0:
                return "undefined_for_zero_five_year_eps_growth"
            if not math.isfinite(ratio) or ratio <= 0 or eps_ttm == 0:
                return "undefined_for_nonpositive_five_year_growth_base"
    return None


def financial_input_diagnostic(name, code, panel, inputs=None):
    """All financial formulas share their actual dependency contract."""
    from .financial_dependencies import financial_dependencies, input_value
    dependency = financial_dependencies().get(name)
    if dependency is None or panel is None:
        return None
    values = {
        key: inputs[key].get(code) if inputs is not None else input_value(panel, code, *key)
        for key in sorted(dependency.required)
    }
    missing = ['.'.join(key) for key, value in values.items() if not _finite(value)]
    if missing:
        conflicts = [bucket for bucket, metric in values if metric == 'equity_parent'
                     and not _finite(values[bucket, metric])
                     and panel.values(bucket, 'equity_parent_conflict').get(code) == 1]
        if conflicts:
            return 'conflicting_financial_inputs:' + ','.join(
                bucket + '.equity_parent' for bucket in conflicts)
        return 'missing_financial_inputs:' + ','.join(missing)
    denominators = ['.'.join(key) for key in sorted(dependency.nonzero_required)
                    if values.get(key) == 0]
    if denominators:
        return 'undefined_financial_zero_denominator:' + ','.join(denominators)
    # Other zero inputs may be legitimate numerators.
    zero = ['.'.join(key) for key, value in values.items() if value == 0]
    if zero:
        return 'financial_zero_input_requires_domain_audit:' + ','.join(zero)
    return 'nonfinite_result_with_present_financial_inputs'


def market_input_diagnostic(name, code, panel):
    """Prove specific formula-domain failures; never excuse an input gap.

    These are the exact windows consumed by the formulas. A documented
    suspension can contribute a zero-range/zero-volume bar, but an absent
    or nonfinite input must remain unresolved, even if another bar is flat.
    """
    if name == 'alpha101_53':
        # delta(x, 9) reads only the two endpoints, not the intervening highs/lows.
        if len(panel.alpha101.close) < 10:
            return 'insufficient_market_window:required_10_sessions'
        bars = pd.DataFrame({k: getattr(panel.alpha101, k)[code].iloc[[-10, -1]]
                             for k in ('close','high','low')})
        if not np.isfinite(bars.to_numpy()).all():
            return 'missing_market_inputs:alpha101_53_endpoint_quotes'
        if ((bars.close < bars.low) | (bars.close > bars.high) | (bars.low <= 0)).any():
            return 'invalid_market_inputs:alpha101_53_endpoint_quotes'
        if bars.close.eq(bars.low).any():
            return 'undefined_alpha101_53_close_equals_low_at_delta_endpoint'
        return 'nonfinite_result_with_present_market_inputs:alpha101_53'
    if name in {'alpha101_32', 'alpha101_66'}:
        alpha = panel.alpha101
        required = required_bars(name)
        if len(alpha.close.index) < required:
            return f'insufficient_market_window:required_{required}_sessions'
        price_fields = ('close',) if name == 'alpha101_32' else ('open', 'high', 'low')
        prices = {field: getattr(alpha, field)[code].tail(required) for field in price_fields}
        vwap_bars = 230 if name == 'alpha101_32' else 16
        if getattr(alpha, 'amount', None) is None:
            return 'missing_market_inputs:vwap_amount'
        volume = alpha.volume[code].tail(vwap_bars)
        amount = alpha.amount[code].tail(vwap_bars)
        inputs = [*prices.values(), volume, amount]
        if any(not np.isfinite(series.to_numpy()).all() for series in inputs):
            return f'missing_market_inputs:{name}_price_volume_or_amount'
        if any((series <= 0).any() for series in prices.values()) or (amount < 0).any() or (volume < 0).any():
            return f'invalid_market_inputs:{name}_price_volume_or_amount'
        if name == 'alpha101_66' and (
            (prices['open'] < prices['low']) | (prices['open'] > prices['high'])
        ).any():
            return 'invalid_market_inputs:open_outside_bar'
        if ((volume == 0) & (amount != 0)).any() or ((volume != 0) & (amount == 0)).any():
            return 'invalid_market_inputs:inconsistent_volume_and_amount'
        if (volume == 0).any():
            return f'undefined_{name}_zero_volume_in_{vwap_bars}_session_vwap'
        if name == 'alpha101_66':
            source_spread = getattr(alpha, 'open_minus_midpoint', None)
            spread = (source_spread[code].tail(required) if source_spread is not None
                      else prices['open'] - (prices['high'] + prices['low']) / 2)
            if not np.isfinite(spread.to_numpy()).all():
                return 'missing_market_inputs:alpha101_66_midpoint_spread'
            if (spread == 0).any():
                return 'undefined_alpha101_66_zero_price_denominator_in_16_session_window'
        return f'nonfinite_result_with_present_market_inputs:{name}'
    if name == 'price_position_ir_60d':
        window = pd.DataFrame({field: getattr(panel.alpha101, field)[code].tail(60)
                               for field in ('open', 'high', 'low', 'close')})
        if len(window) < 60:
            return 'insufficient_market_window:required_60_sessions'
        if not np.isfinite(window.to_numpy(dtype=float)).all():
            return 'missing_market_inputs:60_session_ohlc'
        ranges = window.high - window.low
        if (ranges < 0).any():
            return 'invalid_market_inputs:high_below_low'
        if (ranges == 0).any():
            return 'undefined_price_position_zero_range_in_complete_60_session_window'
        positions = (window.close - window.open) / ranges
        if positions.astype(float).std(ddof=1) == 0:
            return 'undefined_price_position_zero_variance_in_complete_60_session_window'
        return 'nonfinite_result_with_present_market_inputs:price_position_ir_60d'
    if name in {'volume_alpha_300d_000001', 'volume_alpha_300d_000300'}:
        volume = panel.alpha101.volume[code].tail(305)
        benchmark = getattr(panel, 'benchmark_volume_' + name.rsplit('_', 1)[1])
        inputs = pd.DataFrame({'stock': volume, 'benchmark': benchmark.reindex(volume.index)})
        if len(inputs) < 305:
            return 'insufficient_market_window:required_305_sessions'
        if not np.isfinite(inputs.to_numpy(dtype=float)).all():
            return 'missing_market_inputs:305_session_stock_or_benchmark_volume'
        if (inputs < 0).any().any():
            return 'invalid_market_inputs:negative_volume'
        sums = inputs.rolling(5, min_periods=5).sum()
        # The prior sum is the denominator of every pct_change observation.
        if (sums.shift(1).tail(300) == 0).any().any():
            return 'undefined_volume_regression_zero_base_in_complete_305_session_window'
        changes = sums.pct_change(fill_method=None).tail(300)
        if changes.benchmark.var(ddof=1) == 0:
            return 'undefined_volume_regression_zero_benchmark_variance'
        return 'nonfinite_result_with_present_market_inputs:volume_regression'
    return None


def audit_security(code, values, technical, panel, financial_panel=None, *, financial_inputs=None) -> dict:
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
            unresolved[name] = "numerically_unstable_extreme_value"
        elif (name == 'etp5' and pd.notna(listed_at)
              and ((dates > dates[-1] - pd.DateOffset(years=5)) & (dates < listed_at)).any()):
            excluded[name] = "insufficient_listing_history_for_five_year_market_cap"
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
        elif reason := _missing_industry(name, code, panel.alpha101):
            unresolved[name] = reason
        elif (
            name.startswith("alpha101_") and name not in {"alpha101_32", "alpha101_53", "alpha101_66"}
            and observed_sessions >= 512
            and unexplained_market_gaps == 0
            and all(frame[code].iloc[-512:].notna().all() for frame in (
                panel.alpha101.open, panel.alpha101.high, panel.alpha101.low,
                panel.alpha101.close, panel.alpha101.volume,
            ))
        ):
            # OHLCV alone does not prove the exact denominator, industry,
            # VWAP or cross-sectional rank consumed by a particular formula.
            unresolved[name] = "alpha101_result_requires_formula_input_review"
        elif reason := _financial_exclusion(
            name, code, financial_panel
        ):
            excluded[name] = reason
        elif reason := market_input_diagnostic(name, code, panel):
            if reason.startswith('undefined_'):
                excluded[name] = reason
            else:
                unresolved[name] = reason
        else:
            reason = (
                financial_input_diagnostic(name, code, financial_panel, financial_inputs)
                or "missing_input_or_undefined_requires_audit"
            )
            if reason.startswith('undefined_financial_zero_denominator:'):
                excluded[name] = reason
            else:
                unresolved[name] = reason
    if technical.get("adjustment_status") != "applied":
        unresolved["price_adjustment"] = "missing_or_incomplete_adjustment"
    return {"status": "partial" if unresolved else "ready",
            "technical_status": "partial" if technical_names & unresolved.keys() else "ready",
            "unresolved": unresolved, "excluded": excluded,
            "listing_sessions_observed": age,
            "technical_traded_bars_observed": technical_bars,
            "market_sessions_observed": observed_sessions,
            "unexplained_market_gap_sessions": unexplained_market_gaps}
