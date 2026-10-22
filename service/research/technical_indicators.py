"""Additional deterministic technical and relative-risk calculations.

The functions in this module are intentionally independent of repositories and
HTTP contracts.  They consume already-governed observations and expose their
formula assumptions in the returned payloads.
"""

from __future__ import annotations

from itertools import pairwise
from math import sqrt
from statistics import mean, pstdev
from typing import Any

COMMON_INDICATOR_FORMULA_VERSION = "common-technicals-v1"


# Parameters are expressed in bars, not calendar days.  The profile keeps the
# familiar A-share daily settings while preventing a misleading 250-month
# moving average from appearing merely because the same function is reused for
# resampled data.  MACD/KDJ/Ichimoku keep their conventional parameters and are
# reported separately by the research service.
INDICATOR_PARAMETER_PROFILES: dict[str, dict[str, tuple[int, ...]]] = {
    "1d": {
        "sma": (5, 10, 20, 30, 60, 120, 250),
        "ema": (5, 10, 12, 20, 26, 50, 100, 200),
        "rsi": (6, 12, 14, 24),
        "roc": (5, 10, 20, 60, 120),
        "cci": (14, 20),
        "atr": (14, 20),
    },
    "1w": {
        "sma": (5, 10, 20, 30, 40, 52),
        "ema": (5, 10, 12, 20, 26, 50, 52),
        "rsi": (6, 12, 14, 24),
        "roc": (4, 12, 26, 52),
        "cci": (14, 20),
        "atr": (14, 20),
    },
    "1mo": {
        "sma": (3, 6, 12, 24, 36, 60),
        "ema": (3, 6, 12, 20, 24, 26, 36, 60),
        "rsi": (6, 12, 14, 24),
        "roc": (3, 6, 12, 24, 36),
        "cci": (14, 20),
        "atr": (14, 20),
    },
}


def indicator_parameter_profile(timeframe: str) -> dict[str, list[int]]:
    """Return the governed common-parameter profile for one bar frequency."""

    try:
        profile = INDICATOR_PARAMETER_PROFILES[timeframe]
    except KeyError as exc:
        raise ValueError(f"unsupported timeframe: {timeframe}") from exc
    return {name: list(windows) for name, windows in profile.items()}


def _number(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _round(value: float | None, digits: int = 4) -> float | None:
    return None if value is None else round(value, digits)


def _returns(values: list[float]) -> list[float]:
    return [current / previous - 1 for previous, current in pairwise(values) if previous]


def _sma_series(values: list[float], window: int) -> list[float | None]:
    """Rolling arithmetic mean in O(n), including long 120/250-bar windows."""

    output: list[float | None] = [None] * len(values)
    running = 0.0
    for index, value in enumerate(values):
        running += value
        if index >= window:
            running -= values[index - window]
        if index + 1 >= window:
            output[index] = running / window
    return output


def sma_series(values: list[float], window: int) -> list[float | None]:
    """Public alias for the rolling mean used by chart payloads."""

    return _sma_series(values, window)


def rolling_pstdev_series(
    values: list[float], window: int = 20
) -> list[float | None]:
    """Population standard deviation per bar using plain float arithmetic.

    ``statistics.pstdev`` evaluates exact rational arithmetic, which costs an
    order of magnitude more than floats when it runs once per bar.  Bollinger
    bands are rounded to four decimals downstream, so the float result is
    identical at the published precision while the series computes in
    milliseconds instead of hundreds of milliseconds.
    """

    output: list[float | None] = [None] * len(values)
    for index in range(window - 1, len(values)):
        segment = values[index - window + 1 : index + 1]
        average = sum(segment) / window
        variance = sum((value - average) ** 2 for value in segment) / window
        output[index] = sqrt(variance)
    return output


def _ema_series(values: list[float], window: int) -> list[float]:
    if not values:
        return []
    alpha = 2 / (window + 1)
    output = [values[0]]
    for value in values[1:]:
        output.append(alpha * value + (1 - alpha) * output[-1])
    return output


def _optional_ema_series(
    values: list[float | None], window: int,
) -> list[float | None]:
    """EMA over a series whose leading values may be unavailable."""

    output: list[float | None] = [None] * len(values)
    current: float | None = None
    alpha = 2 / (window + 1)
    for index, value in enumerate(values):
        if value is None:
            continue
        current = value if current is None else alpha * value + (1 - alpha) * current
        output[index] = current
    return output


def _wilder_series(values: list[float], window: int) -> list[float | None]:
    """Wilder RMA with an SMA seed after a complete initial window."""

    output: list[float | None] = [None] * len(values)
    if len(values) < window:
        return output
    current = mean(values[:window])
    output[window - 1] = current
    for index in range(window, len(values)):
        current = (current * (window - 1) + values[index]) / window
        output[index] = current
    return output


def _rsi_series(values: list[float], window: int) -> list[float | None]:
    """Wilder RSI aligned to input bars and seeded after ``window`` changes."""

    output: list[float | None] = [None] * len(values)
    if len(values) <= window:
        return output
    changes = [values[index] - values[index - 1] for index in range(1, len(values))]
    gain = mean(max(value, 0.0) for value in changes[:window])
    loss = mean(max(-value, 0.0) for value in changes[:window])

    def value() -> float:
        if loss == 0:
            return 100.0 if gain > 0 else 50.0
        return 100 - 100 / (1 + gain / loss)

    output[window] = value()
    for index in range(window + 1, len(values)):
        change = changes[index - 1]
        gain = (gain * (window - 1) + max(change, 0.0)) / window
        loss = (loss * (window - 1) + max(-change, 0.0)) / window
        output[index] = value()
    return output


def _roc_series(values: list[float], window: int) -> list[float | None]:
    return [
        (values[index] / values[index - window] - 1) * 100
        if index >= window and values[index - window] else None
        for index in range(len(values))
    ]


def _cci_series(
    highs: list[float], lows: list[float], closes: list[float], window: int,
) -> list[float | None]:
    typical = [(high + low + close) / 3 for high, low, close in zip(highs, lows, closes)]
    output: list[float | None] = [None] * len(typical)
    for index in range(window - 1, len(typical)):
        selected = typical[index - window + 1:index + 1]
        average = mean(selected)
        deviation = mean(abs(value - average) for value in selected)
        output[index] = (
            (typical[index] - average) / (0.015 * deviation)
            if deviation else 0.0
        )
    return output


def _true_ranges(
    highs: list[float], lows: list[float], closes: list[float],
) -> list[float]:
    return [
        max(
            high - low,
            abs(high - closes[index - 1]) if index else high - low,
            abs(low - closes[index - 1]) if index else high - low,
        )
        for index, (high, low) in enumerate(zip(highs, lows))
    ]


def _tsi_series(
    closes: list[float], slow: int = 25, fast: int = 13,
) -> list[float | None]:
    """True Strength Index using double EMA-smoothed momentum."""

    if not closes:
        return []
    momentum = [0.0] + [current - previous for previous, current in pairwise(closes)]
    first = _ema_series(momentum, slow)
    second = _ema_series(first, fast)
    abs_first = _ema_series([abs(value) for value in momentum], slow)
    abs_second = _ema_series(abs_first, fast)
    minimum = slow + fast - 1
    return [
        numerator / denominator * 100
        if index + 1 >= minimum and denominator else None
        for index, (numerator, denominator) in enumerate(zip(second, abs_second))
    ]


def _linear_regression(values: list[float], window: int) -> dict[str, float | None]:
    if len(values) < window:
        return {"slope_pct_per_bar": None, "r_squared": None}
    selected = values[-window:]
    x_average = (window - 1) / 2
    y_average = mean(selected)
    x_variance = sum((index - x_average) ** 2 for index in range(window))
    covariance = sum(
        (index - x_average) * (value - y_average)
        for index, value in enumerate(selected)
    )
    slope = covariance / x_variance if x_variance else 0.0
    fitted = [y_average + slope * (index - x_average) for index in range(window)]
    total = sum((value - y_average) ** 2 for value in selected)
    residual = sum((value - estimate) ** 2 for value, estimate in zip(selected, fitted))
    return {
        "slope_pct_per_bar": slope / y_average * 100 if y_average else None,
        "r_squared": 1 - residual / total if total else 0.0,
    }


def _candle_geometry(
    opened: float, high: float, low: float, close: float,
) -> dict[str, float | None]:
    span = high - low
    body_top = max(opened, close)
    body_bottom = min(opened, close)
    return {
        "body_return": (close - opened) / opened if opened else None,
        "range_to_open": span / opened if opened else None,
        "body_to_range": (close - opened) / span if span else None,
        "upper_shadow_to_open": (high - body_top) / opened if opened else None,
        "upper_shadow_to_range": (high - body_top) / span if span else None,
        "lower_shadow_to_open": (body_bottom - low) / opened if opened else None,
        "lower_shadow_to_range": (body_bottom - low) / span if span else None,
        "close_location_to_open": (2 * close - high - low) / opened if opened else None,
        "close_location_to_range": (2 * close - high - low) / span if span else None,
    }


def parameterized_indicator_pack(
    opens: list[float],
    highs: list[float],
    lows: list[float],
    closes: list[float],
    volumes: list[float],
    *,
    timeframe: str,
) -> dict[str, Any]:
    """Return common indicator families under a frequency-aware contract.

    These are deterministic descriptive indicators.  Alpha158/Alpha191 factor
    expressions, cross-sectional transforms and predictive validation remain
    outside this package and belong to ``claw-factor-lab``.
    """

    if not (
        len(opens) == len(highs) == len(lows) == len(closes) == len(volumes)
    ):
        raise ValueError("OHLCV inputs must have equal length")
    profile = indicator_parameter_profile(timeframe)
    if not closes:
        missing_family = {
            name: {str(window): None for window in profile[name]}
            for name in ("sma", "ema", "rsi", "roc", "cci", "atr")
        }
        return {
            "status": "insufficient_history",
            "timeframe": timeframe,
            "parameters": profile,
            "series": {},
            "latest": missing_family | {
                "natr": {
                    str(window): None for window in profile["atr"]
                },
                "tsi_25_13": None,
                "bollinger_20_2": {
                    "lower": None,
                    "middle": None,
                    "upper": None,
                    "percent_b": None,
                    "bandwidth_pct": None,
                },
                "candle_geometry": {
                    key: None for key in (
                        "body_return", "range_to_open", "body_to_range",
                        "upper_shadow_to_open", "upper_shadow_to_range",
                        "lower_shadow_to_open", "lower_shadow_to_range",
                        "close_location_to_open", "close_location_to_range",
                    )
                },
                "structure": {
                    "range_position_60": None,
                    "atr_5_to_20_ratio": None,
                    "retracement_depth_20": None,
                    "retracement_depth_120": None,
                    "regression_20": {
                        "slope_pct_per_bar": None, "r_squared": None,
                    },
                    "regression_60": {
                        "slope_pct_per_bar": None, "r_squared": None,
                    },
                    "breakout_over_prior_high_60_atr": None,
                    "high_touch_count_60_1pct": None,
                    "low_touch_count_60_1pct": None,
                },
            },
        }

    sma = {window: _sma_series(closes, window) for window in profile["sma"]}
    ema = {window: _ema_series(closes, window) for window in profile["ema"]}
    rsi = {window: _rsi_series(closes, window) for window in profile["rsi"]}
    roc = {window: _roc_series(closes, window) for window in profile["roc"]}
    cci = {
        window: _cci_series(highs, lows, closes, window)
        for window in profile["cci"]
    }
    true_ranges = _true_ranges(highs, lows, closes)
    atr = {window: _wilder_series(true_ranges, window) for window in profile["atr"]}
    natr = {
        window: [
            value / close * 100 if value is not None and close else None
            for value, close in zip(values, closes)
        ]
        for window, values in atr.items()
    }
    tsi = _tsi_series(closes)
    bollinger_middle = _sma_series(closes, 20)
    bollinger_std = rolling_pstdev_series(closes, 20)
    bollinger_upper = [
        middle + 2 * deviation
        if middle is not None and deviation is not None else None
        for middle, deviation in zip(bollinger_middle, bollinger_std)
    ]
    bollinger_lower = [
        middle - 2 * deviation
        if middle is not None and deviation is not None else None
        for middle, deviation in zip(bollinger_middle, bollinger_std)
    ]
    bollinger_percent_b = [
        (close - lower) / (upper - lower)
        if lower is not None and upper is not None and upper != lower else None
        for close, lower, upper in zip(closes, bollinger_lower, bollinger_upper)
    ]
    bollinger_bandwidth = [
        (upper - lower) / middle * 100
        if lower is not None and upper is not None and middle else None
        for lower, middle, upper in zip(
            bollinger_lower, bollinger_middle, bollinger_upper
        )
    ]
    candle_geometry = [
        _candle_geometry(opened, high, low, close)
        for opened, high, low, close in zip(opens, highs, lows, closes)
    ]

    def retracement(window: int) -> float | None:
        if len(closes) < window:
            return None
        high = max(highs[-window:])
        low = min(lows[-window:])
        return (high - closes[-1]) / (high - low) if high != low else 0.0

    atr5 = mean(true_ranges[-5:]) if len(true_ranges) >= 5 else None
    atr20 = mean(true_ranges[-20:]) if len(true_ranges) >= 20 else None
    atr14_latest = atr.get(14, [None])[-1]
    prior_high60 = max(highs[-61:-1]) if len(highs) >= 61 else None
    range_high60 = max(highs[-60:]) if len(highs) >= 60 else None
    range_low60 = min(lows[-60:]) if len(lows) >= 60 else None
    touch_high = (
        sum(value >= range_high60 * 0.99 for value in highs[-60:])
        if range_high60 is not None else None
    )
    touch_low = (
        sum(value <= range_low60 * 1.01 for value in lows[-60:])
        if range_low60 is not None else None
    )
    structure = {
        "range_position_60": (
            (closes[-1] - range_low60) / (range_high60 - range_low60)
            if range_high60 is not None and range_low60 is not None
            and range_high60 != range_low60 else None
        ),
        "atr_5_to_20_ratio": atr5 / atr20 if atr5 is not None and atr20 else None,
        "retracement_depth_20": retracement(20),
        "retracement_depth_120": retracement(120),
        "regression_20": _linear_regression(closes, 20),
        "regression_60": _linear_regression(closes, 60),
        "breakout_over_prior_high_60_atr": (
            (closes[-1] - prior_high60) / atr14_latest
            if prior_high60 is not None and atr14_latest else None
        ),
        "high_touch_count_60_1pct": touch_high,
        "low_touch_count_60_1pct": touch_low,
    }
    series: dict[str, Any] = {
        "sma": sma,
        "ema": ema,
        "rsi": rsi,
        "roc": roc,
        "cci": cci,
        "atr": atr,
        "natr": natr,
        "tsi_25_13": tsi,
        "bollinger_middle_20": bollinger_middle,
        "bollinger_upper_20_2": bollinger_upper,
        "bollinger_lower_20_2": bollinger_lower,
        "bollinger_percent_b_20_2": bollinger_percent_b,
        "bollinger_bandwidth_20_2_pct": bollinger_bandwidth,
        "candle_geometry": candle_geometry,
    }
    latest = {
        "sma": {str(window): values[-1] for window, values in sma.items()},
        "ema": {str(window): values[-1] for window, values in ema.items()},
        "rsi": {str(window): values[-1] for window, values in rsi.items()},
        "roc": {str(window): values[-1] for window, values in roc.items()},
        "cci": {str(window): values[-1] for window, values in cci.items()},
        "atr": {str(window): values[-1] for window, values in atr.items()},
        "natr": {str(window): values[-1] for window, values in natr.items()},
        "tsi_25_13": tsi[-1],
        "bollinger_20_2": {
            "lower": bollinger_lower[-1],
            "middle": bollinger_middle[-1],
            "upper": bollinger_upper[-1],
            "percent_b": bollinger_percent_b[-1],
            "bandwidth_pct": bollinger_bandwidth[-1],
        },
        "candle_geometry": candle_geometry[-1],
        "structure": structure,
    }
    longest = max(max(values) for values in profile.values())
    return {
        "status": "ready" if len(closes) >= longest else "limited_history",
        "timeframe": timeframe,
        "observations": len(closes),
        "parameters": profile | {
            "tsi": [25, 13],
            "bollinger": [20, 2],
            "structure_windows": [5, 20, 60, 120],
        },
        "series": series,
        "latest": latest,
        "boundary": (
            "descriptive deterministic indicators only; Alpha158/Alpha191 "
            "and predictive factor validation belong to claw-factor-lab"
        ),
    }


def common_indicator_pack(
    highs: list[float],
    lows: list[float],
    closes: list[float],
    volumes: list[float],
) -> dict[str, Any]:
    """Return one auditable common-indicator contract and aligned series.

    Price indicators consume governed adjusted OHLC. Volume is intentionally
    left unadjusted. Raw path-dependent PVT/Force values are accompanied by
    normalized rolling values suitable for cross-sectional factor screening.
    """

    if not (len(highs) == len(lows) == len(closes) == len(volumes)):
        raise ValueError("highs, lows, closes and volumes must have equal length")
    if not closes:
        return {
            "status": "insufficient_history",
            "observations": 0,
            "formula_version": COMMON_INDICATOR_FORMULA_VERSION,
            "series": {},
            "latest": {},
        }

    ema = {window: _ema_series(closes, window) for window in (12, 20, 26, 50, 200)}
    sma = {window: _sma_series(closes, window) for window in (3, 6, 12, 20, 24)}

    bias: dict[int, list[float | None]] = {}
    for window in (6, 12, 24):
        bias[window] = [
            (close / average - 1) * 100 if average else None
            for close, average in zip(closes, sma[window])
        ]
    bbi = [
        mean(float(value) for value in values) if all(value is not None for value in values) else None
        for values in zip(sma[3], sma[6], sma[12], sma[24])
    ]

    ppo = [
        (fast - slow) / slow * 100 if slow else None
        for fast, slow in zip(ema[12], ema[26])
    ]
    ppo_signal = _optional_ema_series(ppo, 9)
    ppo_histogram = [
        value - signal if value is not None and signal is not None else None
        for value, signal in zip(ppo, ppo_signal)
    ]

    true_ranges = [
        max(
            high - low,
            abs(high - closes[index - 1]) if index else high - low,
            abs(low - closes[index - 1]) if index else high - low,
        )
        for index, (high, low) in enumerate(zip(highs, lows))
    ]
    atr14 = _wilder_series(true_ranges, 14)
    atr20 = _wilder_series(true_ranges, 20)
    natr14 = [
        atr / close * 100 if atr is not None and close else None
        for atr, close in zip(atr14, closes)
    ]
    keltner_middle = ema[20]
    keltner_upper = [
        middle + 2 * atr if atr is not None else None
        for middle, atr in zip(keltner_middle, atr20)
    ]
    keltner_lower = [
        middle - 2 * atr if atr is not None else None
        for middle, atr in zip(keltner_middle, atr20)
    ]

    bollinger_middle = sma[20]
    bollinger_std: list[float | None] = rolling_pstdev_series(closes, 20)
    squeeze_on: list[bool | None] = []
    squeeze_momentum: list[float | None] = []
    for index, (middle, deviation, atr) in enumerate(
        zip(bollinger_middle, bollinger_std, atr20)
    ):
        if middle is None or deviation is None or atr is None:
            squeeze_on.append(None)
            squeeze_momentum.append(None)
            continue
        # Canonical TTM squeeze comparison uses a 1.5 ATR Keltner envelope,
        # while the separately exposed display channel uses 2 ATR.
        squeeze_on.append(
            middle + 2 * deviation < keltner_middle[index] + 1.5 * atr
            and middle - 2 * deviation > keltner_middle[index] - 1.5 * atr
        )
        highest = max(highs[max(0, index - 19):index + 1])
        lowest = min(lows[max(0, index - 19):index + 1])
        baseline = (highest + lowest + 2 * middle) / 4
        squeeze_momentum.append(closes[index] - baseline)

    trix_ema_1 = ema[12]
    trix_ema_2 = _ema_series(trix_ema_1, 12)
    trix_ema_3 = _ema_series(trix_ema_2, 12)
    trix: list[float | None] = [None]
    trix.extend(
        (current / previous - 1) * 100 if previous else None
        for previous, current in pairwise(trix_ema_3)
    )
    trix_signal = _optional_ema_series(trix, 9)
    trix_histogram = [
        value - signal if value is not None and signal is not None else None
        for value, signal in zip(trix, trix_signal)
    ]

    pvt = [0.0]
    raw_force = [0.0]
    for index in range(1, len(closes)):
        previous = closes[index - 1]
        pvt.append(pvt[-1] + volumes[index] * (closes[index] / previous - 1) if previous else pvt[-1])
        raw_force.append((closes[index] - previous) * volumes[index])
    force13 = _ema_series(raw_force, 13)
    average_volume20 = _sma_series(volumes, 20)
    pvt_change_20: list[float | None] = []
    force13_normalized: list[float | None] = []
    for index in range(len(closes)):
        pvt_change_20.append(
            pvt[index] - pvt[index - 20] if index >= 20 else None
        )
        denominator = closes[index] * average_volume20[index] if average_volume20[index] else None
        force13_normalized.append(
            force13[index] / denominator * 100 if denominator else None
        )
    vroc: dict[int, list[float | None]] = {}
    for window in (12, 20):
        vroc[window] = [
            (volumes[index] / volumes[index - window] - 1) * 100
            if index >= window and volumes[index - window] else None
            for index in range(len(volumes))
        ]

    strict_ema = {
        window: [
            value if index + 1 >= window else None
            for index, value in enumerate(ema[window])
        ]
        for window in (20, 50, 200)
    }
    series: dict[str, list[Any]] = {
        "ema_12": ema[12],
        "ema_20": strict_ema[20],
        "ema_26": ema[26],
        "ema_50": strict_ema[50],
        "ema_200": strict_ema[200],
        **{f"bias_{window}": bias[window] for window in bias},
        "bbi": bbi,
        "ppo": ppo,
        "ppo_signal": ppo_signal,
        "ppo_histogram": ppo_histogram,
        "natr_14": natr14,
        "keltner_middle": keltner_middle,
        "keltner_upper": keltner_upper,
        "keltner_lower": keltner_lower,
        "ttm_squeeze_on": squeeze_on,
        "ttm_squeeze_momentum": squeeze_momentum,
        "trix_12": trix,
        "trix_signal_9": trix_signal,
        "trix_histogram": trix_histogram,
        "pvt": pvt,
        "pvt_change_20": pvt_change_20,
        "vroc_12": vroc[12],
        "vroc_20": vroc[20],
        "force_index_13": force13,
        "force_index_13_normalized": force13_normalized,
    }
    latest = {key: values[-1] if values else None for key, values in series.items()}
    latest.update({
        "ema_20_distance_pct": (closes[-1] / strict_ema[20][-1] - 1) * 100 if strict_ema[20][-1] else None,
        "ema_50_distance_pct": (closes[-1] / strict_ema[50][-1] - 1) * 100 if strict_ema[50][-1] else None,
        "ema_200_distance_pct": (closes[-1] / strict_ema[200][-1] - 1) * 100 if strict_ema[200][-1] else None,
        "bbi_distance_pct": (closes[-1] / bbi[-1] - 1) * 100 if bbi[-1] else None,
    })
    required_latest = (
        "ema_20", "ema_50", "ema_200", "bias_6", "bias_12", "bias_24",
        "bbi", "ppo", "ppo_signal", "natr_14", "keltner_middle",
        "keltner_upper", "keltner_lower", "ttm_squeeze_on", "trix_12",
        "trix_signal_9", "pvt_change_20", "vroc_12", "vroc_20",
        "force_index_13_normalized",
    )
    status = (
        "limited_history" if len(closes) < 200
        else "ready" if all(latest.get(key) is not None for key in required_latest)
        else "missing_input"
    )
    return {
        "status": status,
        "observations": len(closes),
        "formula_version": COMMON_INDICATOR_FORMULA_VERSION,
        "parameters": {
            "ema_windows": [12, 20, 26, 50, 200],
            "bias_windows": [6, 12, 24],
            "bbi_windows": [3, 6, 12, 24],
            "ppo": [12, 26, 9],
            "natr": 14,
            "keltner": {"ema": 20, "atr": 20, "multiplier": 2.0},
            "ttm_squeeze": {"bollinger": [20, 2.0], "keltner": [20, 1.5]},
            "trix": [12, 9],
            "vroc_windows": [12, 20],
            "force_index": 13,
            "atr_smoothing": "Wilder RMA",
        },
        "series": series,
        "latest": latest,
        "comparability": {
            "cross_sectional": [
                "ema_*_distance_pct", "bias_*", "bbi_distance_pct", "ppo",
                "natr_14", "trix_12", "vroc_*", "force_index_13_normalized",
            ],
            "path_dependent_raw": ["pvt", "force_index_13"],
        },
    }


def aroon(highs: list[float], lows: list[float], window: int = 25) -> dict[str, Any]:
    """Measure how recently the rolling high and low occurred."""

    if len(highs) < window or len(lows) < window:
        return {"status": "insufficient_history", "window": window}
    recent_highs = highs[-window:]
    recent_lows = lows[-window:]
    high_index = max(range(window), key=recent_highs.__getitem__)
    low_index = min(range(window), key=recent_lows.__getitem__)
    denominator = max(window - 1, 1)
    up = high_index / denominator * 100
    down = low_index / denominator * 100
    oscillator = up - down
    state = (
        "bullish" if up >= 70 and down <= 30
        else "bearish" if down >= 70 and up <= 30
        else "mixed"
    )
    return {
        "status": "ready",
        "window": window,
        "up": _round(up),
        "down": _round(down),
        "oscillator": _round(oscillator),
        "state": state,
        "method": "recency of the highest high and lowest low within the completed rolling window",
    }


def parabolic_sar(
    highs: list[float], lows: list[float], closes: list[float],
    acceleration: float = 0.02, maximum: float = 0.2,
) -> dict[str, Any]:
    """Calculate the standard iterative Parabolic SAR contract."""

    if len(closes) < 3:
        return {"status": "insufficient_history"}
    bullish = closes[1] >= closes[0]
    sar = lows[0] if bullish else highs[0]
    extreme = highs[0] if bullish else lows[0]
    factor = acceleration
    reversal_count = 0
    last_reversal_index: int | None = None
    for index in range(1, len(closes)):
        sar = sar + factor * (extreme - sar)
        if bullish:
            sar = min(sar, lows[index - 1], lows[index - 2] if index >= 2 else lows[index - 1])
            if lows[index] < sar:
                bullish = False
                sar = extreme
                extreme = lows[index]
                factor = acceleration
                reversal_count += 1
                last_reversal_index = index
            elif highs[index] > extreme:
                extreme = highs[index]
                factor = min(maximum, factor + acceleration)
        else:
            sar = max(sar, highs[index - 1], highs[index - 2] if index >= 2 else highs[index - 1])
            if highs[index] > sar:
                bullish = True
                sar = extreme
                extreme = highs[index]
                factor = acceleration
                reversal_count += 1
                last_reversal_index = index
            elif lows[index] < extreme:
                extreme = lows[index]
                factor = min(maximum, factor + acceleration)
    return {
        "status": "ready",
        "value": _round(sar),
        "direction": "bullish" if bullish else "bearish",
        "distance_from_close_pct": _round((closes[-1] / sar - 1) * 100 if sar else None),
        "acceleration": acceleration,
        "maximum_acceleration": maximum,
        "reversal_count": reversal_count,
        "periods_since_reversal": (
            len(closes) - 1 - last_reversal_index if last_reversal_index is not None else None
        ),
        "method": "Wilder Parabolic SAR with 0.02 acceleration and 0.20 maximum",
    }


def niumen_breakout_series(
    highs: list[float],
    lows: list[float],
    closes: list[float],
    *,
    high_window: int = 20,
    atr_window: int = 14,
    signal_window: int = 10,
) -> dict[str, list[float | None]]:
    """Return the daily TongdaXin-style Niumen and confirmation-line series.

    ``REF(HHV(H, N), 1)`` deliberately excludes the current trading day.  In
    contrast, the screenshot formula's ``MA(TR1, M)`` includes the current
    day's completed true range.  Keeping those two timing rules explicit
    prevents a current high from raising its own breakout threshold and avoids
    accidental future-data leakage.
    """

    if not (len(highs) == len(lows) == len(closes)):
        raise ValueError("highs, lows and closes must have equal length")
    if min(high_window, atr_window, signal_window) <= 0:
        raise ValueError("indicator windows must be positive")

    true_ranges: list[float] = []
    prior_highs: list[float | None] = []
    atrv_values: list[float | None] = []
    niumen_values: list[float | None] = []
    confirmation_values: list[float | None] = []
    signal_values: list[float | None] = []

    for index, (high, low, close) in enumerate(zip(highs, lows, closes)):
        previous_close = closes[index - 1] if index else close
        true_ranges.append(max(high - low, abs(high - previous_close), abs(low - previous_close)))

        prior_high = (
            max(highs[index - high_window:index])
            if index >= high_window
            else None
        )
        atrv = (
            mean(true_ranges[index - atr_window + 1:index + 1])
            if index + 1 >= atr_window
            else None
        )
        signal = (
            mean(closes[index - signal_window + 1:index + 1])
            if index + 1 >= signal_window
            else None
        )
        prior_highs.append(prior_high)
        atrv_values.append(atrv)
        niumen_values.append(
            prior_high + 0.5 * atrv
            if prior_high is not None and atrv is not None
            else None
        )
        confirmation_values.append(
            prior_high + atrv
            if prior_high is not None and atrv is not None
            else None
        )
        signal_values.append(signal)

    return {
        "prior_high_20": prior_highs,
        "atrv_sma_14": atrv_values,
        "niumen_line": niumen_values,
        "confirmation_line": confirmation_values,
        "signal_ma_10": signal_values,
    }


def niumen_breakout_lines(
    highs: list[float],
    lows: list[float],
    closes: list[float],
    *,
    high_window: int = 20,
    atr_window: int = 14,
    signal_window: int = 10,
) -> dict[str, Any]:
    """Summarize the latest completed-day Niumen breakout state."""

    series = niumen_breakout_series(
        highs,
        lows,
        closes,
        high_window=high_window,
        atr_window=atr_window,
        signal_window=signal_window,
    )
    latest_niumen = series["niumen_line"][-1] if closes else None
    latest_confirmation = series["confirmation_line"][-1] if closes else None
    latest_prior_high = series["prior_high_20"][-1] if closes else None
    latest_atrv = series["atrv_sma_14"][-1] if closes else None
    latest_signal = series["signal_ma_10"][-1] if closes else None
    if latest_niumen is None or latest_confirmation is None or not closes:
        state = "unavailable"
        status = "insufficient_history"
    elif closes[-1] >= latest_confirmation:
        state = "confirmed_breakout"
        status = "ready"
    elif closes[-1] >= latest_niumen:
        state = "above_niumen_pending_confirmation"
        status = "ready"
    else:
        state = "below_niumen"
        status = "ready"

    crossed_niumen = False
    crossed_confirmation = False
    if len(closes) >= 2:
        previous_niumen = series["niumen_line"][-2]
        previous_confirmation = series["confirmation_line"][-2]
        crossed_niumen = bool(
            previous_niumen is not None
            and closes[-2] < previous_niumen
            and latest_niumen is not None
            and closes[-1] >= latest_niumen
        )
        crossed_confirmation = bool(
            previous_confirmation is not None
            and closes[-2] < previous_confirmation
            and latest_confirmation is not None
            and closes[-1] >= latest_confirmation
        )

    return {
        "status": status,
        "state": state,
        "values": {
            "prior_high_20": _round(latest_prior_high),
            "atrv_sma_14": _round(latest_atrv),
            "niumen_line": _round(latest_niumen),
            "confirmation_line": _round(latest_confirmation),
            "signal_ma_10": _round(latest_signal),
        },
        "events": {
            "crossed_niumen_today": crossed_niumen,
            "crossed_confirmation_today": crossed_confirmation,
        },
        "distance_from_niumen_pct": _round(
            (closes[-1] / latest_niumen - 1) * 100
            if closes and latest_niumen
            else None
        ),
        "distance_from_confirmation_pct": _round(
            (closes[-1] / latest_confirmation - 1) * 100
            if closes and latest_confirmation
            else None
        ),
        "parameters": {
            "high_window_trading_days": high_window,
            "atr_window_trading_days": atr_window,
            "signal_window_trading_days": signal_window,
            "niumen_atrv_multiplier": 0.5,
            "confirmation_atrv_multiplier": 1.0,
        },
        "aliases": {
            "niumen_line": "NML / 牛门线",
            "confirmation_line": "QRL / 确认线 / 突破线",
            "signal_ma_10": "SMX / 10日均线",
        },
        "calculation_timing": "after_daily_close",
        "current_bar_policy": {
            "rolling_high_excludes_current_trading_day": True,
            "atrv_includes_current_completed_trading_day": True,
        },
        "formula": (
            "TR=max(H-L,abs(H-REF(C,1)),abs(L-REF(C,1))); "
            "ATRV=MA(TR,14); BASE=REF(HHV(H,20),1); "
            "NIUMEN=BASE+0.5*ATRV; CONFIRMATION=BASE+1.0*ATRV; SIGNAL=MA(C,10)"
        ),
        "formula_version": "niumen-tongdaxin-v1",
    }


def downside_risk(returns: list[float], periods_per_year: int) -> dict[str, Any]:
    """Return historical downside statistics without distribution assumptions."""

    if len(returns) < 20:
        return {"status": "insufficient_history", "observations": len(returns)}
    recent = returns[-250:]
    downside = [min(value, 0.0) for value in recent]
    downside_deviation = sqrt(mean(value * value for value in downside))
    ordered = sorted(recent)
    quantile_index = max(0, int((len(ordered) - 1) * 0.05))
    quantile = ordered[quantile_index]
    tail = [value for value in ordered if value <= quantile]
    annualized_return = mean(recent) * periods_per_year
    annualized_downside = downside_deviation * sqrt(periods_per_year)
    return {
        "status": "ready",
        "observations": len(recent),
        "downside_deviation_annualized_pct": _round(annualized_downside * 100),
        "historical_var_95_pct": _round(max(0.0, -quantile * 100)),
        "historical_expected_shortfall_95_pct": _round(
            max(0.0, -mean(tail) * 100) if tail else None
        ),
        "sortino_zero_target": _round(
            annualized_return / annualized_downside if annualized_downside else None
        ),
        "method": "historical returns, zero target, no normal-distribution assumption",
    }


def gap_analysis(rows: list[dict], limit: int = 12) -> dict[str, Any]:
    """Find full OHLC gaps and whether subsequent bars completely filled them."""

    valid = [
        {
            "trade_date": str(row.get("trade_date")),
            "high": _number(row.get("high")),
            "low": _number(row.get("low")),
        }
        for row in rows
    ]
    valid = [row for row in valid if row["high"] is not None and row["low"] is not None]
    gaps: list[dict[str, Any]] = []
    for index in range(1, len(valid)):
        previous, current = valid[index - 1], valid[index]
        direction = None
        lower = upper = size_pct = None
        if current["low"] > previous["high"]:
            direction = "up"
            lower, upper = previous["high"], current["low"]
            size_pct = (upper / lower - 1) * 100 if lower else None
        elif current["high"] < previous["low"]:
            direction = "down"
            lower, upper = current["high"], previous["low"]
            size_pct = (upper / lower - 1) * 100 if lower else None
        if direction is None or lower is None or upper is None:
            continue
        future = valid[index + 1:]
        fill_date = None
        if direction == "up":
            for row in future:
                if row["low"] <= lower:
                    fill_date = row["trade_date"]
                    break
            penetration = min((row["low"] for row in future), default=upper)
            progress = (upper - max(lower, min(upper, penetration))) / (upper - lower) * 100
        else:
            for row in future:
                if row["high"] >= upper:
                    fill_date = row["trade_date"]
                    break
            penetration = max((row["high"] for row in future), default=lower)
            progress = (min(upper, max(lower, penetration)) - lower) / (upper - lower) * 100
        gaps.append({
            "trade_date": current["trade_date"],
            "direction": direction,
            "lower": _round(lower),
            "upper": _round(upper),
            "size_pct": _round(size_pct),
            "status": "filled" if fill_date else "open",
            "fill_date": fill_date,
            "fill_progress_pct": 100.0 if fill_date else _round(progress),
        })
    open_gaps = [gap for gap in gaps if gap["status"] == "open"]
    return {
        "status": "ready" if len(valid) >= 2 else "insufficient_history",
        "recent": gaps[-limit:],
        "open": open_gaps[-limit:],
        "method": "full gap requires current low above prior high or current high below prior low; fill requires crossing the far boundary",
    }


def relative_risk_metrics(
    asset_prices: list[float], benchmark_prices: list[float],
    windows: tuple[int, ...] = (20, 60, 120, 250),
    periods_per_year: int = 252,
) -> dict[str, Any]:
    """Calculate aligned rolling relative-risk metrics against one benchmark."""

    if len(asset_prices) != len(benchmark_prices):
        raise ValueError("asset and benchmark prices must be aligned")
    output: dict[str, Any] = {}
    for window in windows:
        if len(asset_prices) <= window:
            output[str(window)] = {"status": "insufficient_history"}
            continue
        asset_returns = _returns(asset_prices[-window - 1:])
        benchmark_returns = _returns(benchmark_prices[-window - 1:])
        asset_mean = mean(asset_returns)
        benchmark_mean = mean(benchmark_returns)
        covariance = mean(
            (asset - asset_mean) * (benchmark - benchmark_mean)
            for asset, benchmark in zip(asset_returns, benchmark_returns)
        )
        benchmark_variance = mean(
            (value - benchmark_mean) ** 2 for value in benchmark_returns
        )
        asset_deviation = pstdev(asset_returns)
        benchmark_deviation = pstdev(benchmark_returns)
        beta = covariance / benchmark_variance if benchmark_variance else None
        correlation = (
            covariance / (asset_deviation * benchmark_deviation)
            if asset_deviation and benchmark_deviation else None
        )
        active = [asset - benchmark for asset, benchmark in zip(asset_returns, benchmark_returns)]
        active_deviation = pstdev(active)
        output[str(window)] = {
            "status": "ready",
            "observations": window,
            "beta": _round(beta),
            "correlation": _round(correlation),
            "annualized_alpha_zero_rf_pct": _round(
                (asset_mean - beta * benchmark_mean) * periods_per_year * 100
                if beta is not None else None
            ),
            "tracking_error_annualized_pct": _round(
                active_deviation * sqrt(periods_per_year) * 100
            ),
            "information_ratio": _round(
                mean(active) / active_deviation * sqrt(periods_per_year)
                if active_deviation else None
            ),
            "asset_return_pct": _round((asset_prices[-1] / asset_prices[-window - 1] - 1) * 100),
            "benchmark_return_pct": _round(
                (benchmark_prices[-1] / benchmark_prices[-window - 1] - 1) * 100
            ),
        }
    return {
        "status": "ready" if asset_prices else "missing",
        "windows": output,
        "method": "aligned close-to-close returns; alpha assumes zero risk-free rate",
    }
