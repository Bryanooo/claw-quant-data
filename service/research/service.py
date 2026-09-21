"""Deterministic research calculations over governed standard datasets."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date, datetime, timedelta, timezone
from itertools import pairwise
from math import sqrt
from statistics import mean, median, pstdev
from typing import Any

from service.clock import business_now
from service.data_service.models import InvalidQueryError, RecordNotFoundError
from service.research.catalog import capability_catalog
from service.research.technical_indicators import (
    aroon as _aroon,
    downside_risk as _downside_risk,
    gap_analysis as _gap_analysis,
    parabolic_sar as _parabolic_sar,
    relative_risk_metrics as _relative_risk_metrics,
)


def _number(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_div(numerator: Any, denominator: Any) -> float | None:
    top = _number(numerator)
    bottom = _number(denominator)
    if top is None or bottom in (None, 0):
        return None
    return top / bottom


def _pct_change(current: Any, previous: Any) -> float | None:
    ratio = _safe_div(current, previous)
    return None if ratio is None else (ratio - 1) * 100


def _round(value: float | None, digits: int = 4) -> float | None:
    return None if value is None else round(value, digits)


def _day(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value or "").strip()
    if not text:
        return None
    try:
        if len(text) >= 10 and text[4] == "-":
            return date.fromisoformat(text[:10])
        if len(text) >= 8 and text[:8].isdigit():
            return date(int(text[:4]), int(text[4:6]), int(text[6:8]))
    except ValueError:
        return None
    return None


def _percentile_rank(values: Iterable[Any], current: Any) -> float | None:
    clean = sorted(value for value in (_number(item) for item in values) if value is not None)
    target = _number(current)
    if not clean or target is None:
        return None
    below = sum(value < target for value in clean)
    equal = sum(value == target for value in clean)
    return round((below + equal * 0.5) / len(clean) * 100, 2)


def _moving_average(values: list[float], window: int) -> float | None:
    if len(values) < window:
        return None
    return mean(values[-window:])


def _sma_series(values: list[float], window: int) -> list[float | None]:
    """Return a position-preserving simple moving-average series."""

    output: list[float | None] = []
    for index in range(len(values)):
        if index + 1 < window:
            output.append(None)
        else:
            output.append(mean(values[index - window + 1:index + 1]))
    return output


def _weighted_moving_average(values: list[float], window: int) -> float | None:
    if len(values) < window:
        return None
    weights = range(1, window + 1)
    return sum(value * weight for value, weight in zip(values[-window:], weights)) / sum(weights)


def _weighted_series(values: list[float], window: int) -> list[float | None]:
    return [
        _weighted_moving_average(values[:index + 1], window)
        for index in range(len(values))
    ]


def _ema_series(values: list[float], window: int) -> list[float]:
    if not values:
        return []
    alpha = 2 / (window + 1)
    output = [values[0]]
    for value in values[1:]:
        output.append(alpha * value + (1 - alpha) * output[-1])
    return output


def _rsi(values: list[float], window: int = 14) -> float | None:
    if len(values) <= window:
        return None
    changes = [right - left for left, right in zip(values[-window - 1:-1], values[-window:])]
    gains = sum(max(change, 0) for change in changes) / window
    losses = sum(max(-change, 0) for change in changes) / window
    if losses == 0:
        return 100.0 if gains > 0 else 50.0
    return 100 - 100 / (1 + gains / losses)


def _max_drawdown(values: list[float]) -> float | None:
    if not values:
        return None
    peak = values[0]
    worst = 0.0
    for value in values:
        peak = max(peak, value)
        if peak:
            worst = min(worst, value / peak - 1)
    return worst * 100


def _stochastic(
    highs: list[float], lows: list[float], closes: list[float], window: int = 9
) -> tuple[float | None, float | None, float | None]:
    if len(closes) < window:
        return None, None, None
    k = d = 50.0
    for index in range(window - 1, len(closes)):
        highest = max(highs[index - window + 1:index + 1])
        lowest = min(lows[index - window + 1:index + 1])
        rsv = 50.0 if highest == lowest else (closes[index] - lowest) / (highest - lowest) * 100
        k = 2 / 3 * k + 1 / 3 * rsv
        d = 2 / 3 * d + 1 / 3 * k
    return k, d, 3 * k - 2 * d


def _williams_r(
    highs: list[float], lows: list[float], closes: list[float], window: int = 14
) -> float | None:
    if len(closes) < window:
        return None
    highest = max(highs[-window:])
    lowest = min(lows[-window:])
    return None if highest == lowest else (highest - closes[-1]) / (highest - lowest) * -100


def _cci(
    highs: list[float], lows: list[float], closes: list[float], window: int = 20
) -> float | None:
    if len(closes) < window:
        return None
    typical = [(high + low + close) / 3 for high, low, close in zip(highs, lows, closes)]
    recent = typical[-window:]
    average = mean(recent)
    deviation = mean(abs(value - average) for value in recent)
    return None if deviation == 0 else (typical[-1] - average) / (0.015 * deviation)


def _obv(closes: list[float], volumes: list[float]) -> list[float]:
    output = [0.0]
    for previous, current, volume in zip(closes[:-1], closes[1:], volumes[1:]):
        direction = 1 if current > previous else -1 if current < previous else 0
        output.append(output[-1] + direction * volume)
    return output


def _mfi(
    highs: list[float], lows: list[float], closes: list[float],
    volumes: list[float], window: int = 14,
) -> float | None:
    if len(closes) <= window:
        return None
    typical = [(high + low + close) / 3 for high, low, close in zip(highs, lows, closes)]
    positive = negative = 0.0
    for previous, current, volume in zip(
        typical[-window - 1:-1], typical[-window:], volumes[-window:]
    ):
        flow = current * volume
        if current > previous:
            positive += flow
        elif current < previous:
            negative += flow
    if negative == 0:
        return 100.0 if positive else 50.0
    return 100 - 100 / (1 + positive / negative)


def _stochastic_rsi(values: list[float], window: int = 14) -> float | None:
    """Return StochRSI on a 0-100 scale using reproducible simple-window RSI."""

    if len(values) < window * 2 + 1:
        return None
    # Only the latest ``window`` RSI observations are required for StochRSI.
    # Bound each input slice as well, avoiding quadratic copying on long histories.
    rsi_values = [
        value
        for index in range(len(values) - window, len(values))
        if (value := _rsi(values[index - window:index + 1], window)) is not None
    ]
    recent = rsi_values[-window:]
    if len(recent) < window:
        return None
    low, high = min(recent), max(recent)
    return 50.0 if high == low else (recent[-1] - low) / (high - low) * 100


def _chaikin_money_flow(
    highs: list[float], lows: list[float], closes: list[float],
    volumes: list[float], window: int = 20,
) -> float | None:
    if len(closes) < window:
        return None
    weighted = 0.0
    total_volume = 0.0
    for high, low, close, volume in zip(
        highs[-window:], lows[-window:], closes[-window:], volumes[-window:]
    ):
        multiplier = 0.0 if high == low else ((close - low) - (high - close)) / (high - low)
        weighted += multiplier * volume
        total_volume += volume
    return None if total_volume == 0 else weighted / total_volume


def _ichimoku(
    highs: list[float], lows: list[float], close: float,
) -> dict[str, Any]:
    def midpoint(window: int) -> float | None:
        if len(highs) < window:
            return None
        return (max(highs[-window:]) + min(lows[-window:])) / 2

    conversion = midpoint(9)
    base = midpoint(26)
    span_a = (conversion + base) / 2 if conversion is not None and base is not None else None
    span_b = midpoint(52)
    cloud_low = min(span_a, span_b) if span_a is not None and span_b is not None else None
    cloud_high = max(span_a, span_b) if span_a is not None and span_b is not None else None
    state = (
        "above_cloud" if cloud_high is not None and close > cloud_high
        else "below_cloud" if cloud_low is not None and close < cloud_low
        else "inside_cloud" if cloud_low is not None
        else "unavailable"
    )
    return {
        "conversion_9": _round(conversion),
        "base_26": _round(base),
        "leading_span_a": _round(span_a),
        "leading_span_b_52": _round(span_b),
        "state": state,
        "projection_periods": 26,
        "method": "9/26/52 Ichimoku values; leading spans are current projections, not future observations",
    }


def _donchian(
    highs: list[float], lows: list[float], close: float, window: int,
) -> dict[str, Any]:
    if len(highs) < window:
        return {"window": window, "status": "insufficient_history"}
    upper = max(highs[-window:])
    lower = min(lows[-window:])
    prior_upper = max(highs[-window - 1:-1]) if len(highs) > window else None
    prior_lower = min(lows[-window - 1:-1]) if len(lows) > window else None
    signal = (
        "up_breakout" if prior_upper is not None and close > prior_upper
        else "down_breakout" if prior_lower is not None and close < prior_lower
        else "inside_channel"
    )
    return {
        "window": window,
        "upper": _round(upper),
        "middle": _round((upper + lower) / 2),
        "lower": _round(lower),
        "signal": signal,
        "method": "current channel uses rolling extremes; breakout compares close with the prior completed channel",
    }


def _supertrend(
    highs: list[float], lows: list[float], closes: list[float],
    window: int = 10, multiplier: float = 3.0,
) -> dict[str, Any]:
    if len(closes) < window + 1:
        return {"status": "insufficient_history", "window": window, "multiplier": multiplier}
    true_ranges = [highs[0] - lows[0]]
    for index in range(1, len(closes)):
        true_ranges.append(max(
            highs[index] - lows[index],
            abs(highs[index] - closes[index - 1]),
            abs(lows[index] - closes[index - 1]),
        ))
    final_upper = final_lower = trend = None
    direction = 1
    for index in range(window - 1, len(closes)):
        atr = mean(true_ranges[index - window + 1:index + 1])
        midpoint = (highs[index] + lows[index]) / 2
        basic_upper = midpoint + multiplier * atr
        basic_lower = midpoint - multiplier * atr
        if final_upper is None:
            final_upper, final_lower = basic_upper, basic_lower
        else:
            previous_close = closes[index - 1]
            final_upper = basic_upper if basic_upper < final_upper or previous_close > final_upper else final_upper
            final_lower = basic_lower if basic_lower > final_lower or previous_close < final_lower else final_lower
        if direction < 0 and closes[index] > final_upper:
            direction = 1
        elif direction > 0 and closes[index] < final_lower:
            direction = -1
        trend = final_lower if direction > 0 else final_upper
    return {
        "status": "ready",
        "window": window,
        "multiplier": multiplier,
        "value": _round(trend),
        "direction": "bullish" if direction > 0 else "bearish",
        "method": "rolling simple ATR Supertrend; signal changes only after close crosses the active band",
    }


def _adx(
    highs: list[float], lows: list[float], closes: list[float], window: int = 14
) -> tuple[float | None, float | None, float | None]:
    """Return a transparent rolling approximation of Wilder ADX/+DI/-DI."""

    if len(closes) < window * 2:
        return None, None, None
    tr: list[float] = []
    plus_dm: list[float] = []
    minus_dm: list[float] = []
    for index in range(1, len(closes)):
        up = highs[index] - highs[index - 1]
        down = lows[index - 1] - lows[index]
        plus_dm.append(up if up > down and up > 0 else 0.0)
        minus_dm.append(down if down > up and down > 0 else 0.0)
        tr.append(max(
            highs[index] - lows[index],
            abs(highs[index] - closes[index - 1]),
            abs(lows[index] - closes[index - 1]),
        ))
    dx_values: list[float] = []
    latest_plus = latest_minus = None
    for index in range(window - 1, len(tr)):
        tr_sum = sum(tr[index - window + 1:index + 1])
        if tr_sum == 0:
            continue
        latest_plus = sum(plus_dm[index - window + 1:index + 1]) / tr_sum * 100
        latest_minus = sum(minus_dm[index - window + 1:index + 1]) / tr_sum * 100
        denominator = latest_plus + latest_minus
        dx_values.append(0.0 if denominator == 0 else abs(latest_plus - latest_minus) / denominator * 100)
    adx = mean(dx_values[-window:]) if len(dx_values) >= window else None
    return adx, latest_plus, latest_minus


def _candlestick_patterns(rows: list[dict], limit: int = 20) -> list[dict[str, Any]]:
    patterns: list[dict[str, Any]] = []
    recent = rows[-limit:]
    for offset, row in enumerate(recent):
        open_price = _number(row.get("open"))
        high = _number(row.get("high"))
        low = _number(row.get("low"))
        close = _number(row.get("close"))
        if None in (open_price, high, low, close) or high == low:
            continue
        assert open_price is not None and high is not None and low is not None and close is not None
        body = abs(close - open_price)
        span = high - low
        upper = high - max(open_price, close)
        lower = min(open_price, close) - low
        observed = str(row.get("trade_date"))
        if body / span <= 0.1:
            patterns.append({"trade_date": observed, "pattern": "doji", "direction": "neutral"})
        if lower >= max(body * 2, span * 0.45) and upper <= max(body, span * 0.15):
            patterns.append({"trade_date": observed, "pattern": "hammer", "direction": "bullish_candidate"})
        if upper >= max(body * 2, span * 0.45) and lower <= max(body, span * 0.15):
            patterns.append({"trade_date": observed, "pattern": "shooting_star", "direction": "bearish_candidate"})
        if offset == 0:
            continue
        previous = recent[offset - 1]
        previous_open = _number(previous.get("open"))
        previous_close = _number(previous.get("close"))
        if previous_open is None or previous_close is None:
            continue
        if previous_close < previous_open and close > open_price and open_price <= previous_close and close >= previous_open:
            patterns.append({"trade_date": observed, "pattern": "bullish_engulfing", "direction": "bullish_candidate"})
        if previous_close > previous_open and close < open_price and open_price >= previous_close and close <= previous_open:
            patterns.append({"trade_date": observed, "pattern": "bearish_engulfing", "direction": "bearish_candidate"})
    return patterns


def _zigzag(
    rows: list[dict], threshold_pct: float
) -> list[dict[str, Any]]:
    """Extract confirmed volatility-filtered swing pivots plus the live extreme."""

    if len(rows) < 2:
        return []
    closes = [_number(row.get("close")) for row in rows]
    if any(value is None for value in closes):
        return []
    values = [float(value) for value in closes if value is not None]
    threshold = threshold_pct / 100
    direction = 0
    extreme_index = 0
    extreme_value = values[0]
    initial_high_index = initial_low_index = 0
    initial_high = initial_low = values[0]
    pivots: list[dict[str, Any]] = []

    def append(index: int, kind: str, confirmed: bool) -> None:
        pivots.append({
            "trade_date": str(rows[index].get("trade_date")),
            "price": _round(values[index]),
            "type": kind,
            "confirmed": confirmed,
        })

    for index, value in enumerate(values[1:], start=1):
        if direction == 0:
            if value >= initial_high:
                initial_high_index, initial_high = index, value
            if value <= initial_low:
                initial_low_index, initial_low = index, value
            if value / initial_low - 1 >= threshold and initial_low_index < index:
                append(initial_low_index, "low", True)
                direction = 1
                extreme_index, extreme_value = initial_high_index, initial_high
            elif value / initial_high - 1 <= -threshold and initial_high_index < index:
                append(initial_high_index, "high", True)
                direction = -1
                extreme_index, extreme_value = initial_low_index, initial_low
        elif direction > 0:
            if value >= extreme_value:
                extreme_index, extreme_value = index, value
            elif value / extreme_value - 1 <= -threshold:
                append(extreme_index, "high", True)
                direction = -1
                extreme_index, extreme_value = index, value
        else:
            if value <= extreme_value:
                extreme_index, extreme_value = index, value
            elif value / extreme_value - 1 >= threshold:
                append(extreme_index, "low", True)
                direction = 1
                extreme_index, extreme_value = index, value
    append(extreme_index, "high" if direction > 0 else "low", False)
    return pivots[-12:]


def _fibonacci_retracement(
    pivots: list[dict[str, Any]], current_price: float,
) -> dict[str, Any]:
    """Project retracement and extension levels from the last completed swing."""

    confirmed = [pivot for pivot in pivots if pivot.get("confirmed")]
    if len(confirmed) < 2:
        return {
            "status": "insufficient_structure",
            "method": "last two confirmed volatility-filtered ZigZag pivots",
        }
    start, end = confirmed[-2], confirmed[-1]
    start_price = _number(start.get("price"))
    end_price = _number(end.get("price"))
    if start_price is None or end_price is None or start_price == end_price:
        return {"status": "insufficient_structure"}
    direction = "up" if end_price > start_price else "down"
    span = abs(end_price - start_price)
    retracement_ratios = (0.0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0)
    extension_ratios = (1.272, 1.618, 2.0)
    retracements = {
        f"{ratio * 100:g}": _round(
            end_price - span * ratio if direction == "up"
            else end_price + span * ratio
        )
        for ratio in retracement_ratios
    }
    extensions = {
        f"{ratio * 100:g}": _round(
            start_price + span * ratio if direction == "up"
            else start_price - span * ratio
        )
        for ratio in extension_ratios
    }
    retracement_pct = (
        (end_price - current_price) / span * 100
        if direction == "up"
        else (current_price - end_price) / span * 100
    )
    nearest_name, nearest_price = min(
        retracements.items(), key=lambda item: abs(float(item[1]) - current_price)
    )
    live = pivots[-1] if pivots and not pivots[-1].get("confirmed") else None
    return {
        "status": "ready",
        "direction": direction,
        "anchor_start": start,
        "anchor_end": end,
        "retracement_levels": retracements,
        "extension_levels": extensions,
        "current_retracement_pct": _round(retracement_pct),
        "nearest_retracement": {"ratio_pct": float(nearest_name), "price": nearest_price},
        "invalidation_price": _round(start_price),
        "live_pivot_excluded": live,
        "method": "last two confirmed volatility-filtered ZigZag pivots; the live pivot is never an anchor",
    }


def _chan_normalized_bars(rows: list[dict]) -> list[dict[str, Any]]:
    """Remove containing K-line relationships using one documented Chan variant."""

    normalized: list[dict[str, Any]] = []
    for source_index, row in enumerate(rows):
        high = _number(row.get("high"))
        low = _number(row.get("low"))
        opened = _number(row.get("open"))
        close = _number(row.get("close"))
        if None in (high, low, opened, close):
            continue
        bar = {
            "start_date": str(row.get("trade_date")),
            "end_date": str(row.get("trade_date")),
            "open": opened,
            "high": high,
            "low": low,
            "close": close,
            "source_start_index": source_index,
            "source_end_index": source_index,
            "source_bars": 1,
        }
        if not normalized:
            normalized.append(bar)
            continue
        previous = normalized[-1]
        contains = (
            (bar["high"] >= previous["high"] and bar["low"] <= previous["low"])
            or (previous["high"] >= bar["high"] and previous["low"] <= bar["low"])
        )
        if not contains:
            normalized.append(bar)
            continue
        if len(normalized) >= 2:
            before = normalized[-2]
            upward = previous["high"] >= before["high"] and previous["low"] >= before["low"]
            downward = previous["high"] <= before["high"] and previous["low"] <= before["low"]
        else:
            upward = bar["close"] >= previous["close"]
            downward = not upward
        if not upward and not downward:
            upward = bar["close"] >= previous["close"]
        previous.update({
            "end_date": bar["end_date"],
            "high": max(previous["high"], bar["high"]) if upward else min(previous["high"], bar["high"]),
            "low": max(previous["low"], bar["low"]) if upward else min(previous["low"], bar["low"]),
            "close": bar["close"],
            "source_end_index": source_index,
            "source_bars": previous["source_bars"] + 1,
        })
    return normalized


def _chan_fractals(bars: list[dict[str, Any]]) -> list[dict[str, Any]]:
    fractals: list[dict[str, Any]] = []
    for index in range(1, len(bars) - 1):
        left, middle, right = bars[index - 1:index + 2]
        is_top = (
            middle["high"] > left["high"] and middle["high"] >= right["high"]
            and middle["low"] > left["low"] and middle["low"] >= right["low"]
        )
        is_bottom = (
            middle["low"] < left["low"] and middle["low"] <= right["low"]
            and middle["high"] < left["high"] and middle["high"] <= right["high"]
        )
        if is_top or is_bottom:
            kind = "top" if is_top else "bottom"
            fractals.append({
                "normalized_index": index,
                "trade_date": middle["end_date"],
                "type": kind,
                "price": _round(middle["high"] if is_top else middle["low"]),
                "source_index": middle["source_end_index"],
                "confirmed": True,
            })
    return fractals


def _chan_strokes(
    fractals: list[dict[str, Any]], macd_histogram: list[float],
    minimum_separation: int = 4,
) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    for fractal in fractals:
        if not selected:
            selected.append(fractal)
            continue
        previous = selected[-1]
        if fractal["type"] == previous["type"]:
            more_extreme = (
                fractal["price"] > previous["price"]
                if fractal["type"] == "top"
                else fractal["price"] < previous["price"]
            )
            if more_extreme:
                selected[-1] = fractal
            continue
        if fractal["normalized_index"] - previous["normalized_index"] >= minimum_separation:
            selected.append(fractal)
    strokes: list[dict[str, Any]] = []
    for index, (start, end) in enumerate(pairwise(selected)):
        source_start = int(start["source_index"])
        source_end = int(end["source_index"])
        energy = sum(abs(value) for value in macd_histogram[source_start:source_end + 1])
        strokes.append({
            "index": index,
            "start_date": start["trade_date"],
            "end_date": end["trade_date"],
            "start_price": start["price"],
            "end_price": end["price"],
            "direction": "up" if end["price"] > start["price"] else "down",
            "high": max(start["price"], end["price"]),
            "low": min(start["price"], end["price"]),
            "normalized_bar_span": end["normalized_index"] - start["normalized_index"] + 1,
            "change_pct": _round(_pct_change(end["price"], start["price"])),
            "macd_histogram_energy": _round(energy),
            "confirmed": True,
        })
    return strokes


def _chan_segments(strokes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return explicit three-stroke extension candidates, not subjective final segments."""

    segments: list[dict[str, Any]] = []
    for index in range(2, len(strokes)):
        first, middle, third = strokes[index - 2:index + 1]
        if first["direction"] != third["direction"]:
            continue
        extends = (
            third["end_price"] > first["end_price"]
            if third["direction"] == "up"
            else third["end_price"] < first["end_price"]
        )
        if not extends:
            continue
        segments.append({
            "start_stroke_index": first["index"],
            "end_stroke_index": third["index"],
            "start_date": first["start_date"],
            "end_date": third["end_date"],
            "start_price": first["start_price"],
            "end_price": third["end_price"],
            "direction": third["direction"],
            "confirmed": True,
            "method": "three alternating strokes with the third extending the first",
        })
    return segments


def _chan_centers(strokes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    centers: list[dict[str, Any]] = []
    for index in range(2, len(strokes)):
        group = strokes[index - 2:index + 1]
        lower = max(stroke["low"] for stroke in group)
        upper = min(stroke["high"] for stroke in group)
        if lower > upper:
            continue
        candidate = {
            "start_stroke_index": group[0]["index"],
            "end_stroke_index": group[-1]["index"],
            "start_date": group[0]["start_date"],
            "end_date": group[-1]["end_date"],
            "lower": _round(lower),
            "upper": _round(upper),
            "middle": _round((lower + upper) / 2),
            "stroke_count": 3,
            "confirmed": True,
        }
        if centers and candidate["start_stroke_index"] <= centers[-1]["end_stroke_index"]:
            merged_lower = max(float(centers[-1]["lower"]), lower)
            merged_upper = min(float(centers[-1]["upper"]), upper)
            if merged_lower <= merged_upper:
                centers[-1].update({
                    "end_stroke_index": candidate["end_stroke_index"],
                    "end_date": candidate["end_date"],
                    "lower": _round(merged_lower),
                    "upper": _round(merged_upper),
                    "middle": _round((merged_lower + merged_upper) / 2),
                    "stroke_count": candidate["end_stroke_index"] - centers[-1]["start_stroke_index"] + 1,
                })
                continue
        centers.append(candidate)
    return centers


def _chan_divergences_and_signals(
    strokes: list[dict[str, Any]], centers: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    divergences: list[dict[str, Any]] = []
    signals: list[dict[str, Any]] = []
    first_signal_by_stroke: dict[int, dict[str, Any]] = {}
    latest_center = centers[-1] if centers else None
    for index in range(2, len(strokes)):
        previous, current = strokes[index - 2], strokes[index]
        if previous["direction"] != current["direction"]:
            continue
        previous_energy = _number(previous.get("macd_histogram_energy"))
        current_energy = _number(current.get("macd_histogram_energy"))
        price_extends = (
            current["end_price"] > previous["end_price"]
            if current["direction"] == "up"
            else current["end_price"] < previous["end_price"]
        )
        if not price_extends or previous_energy in (None, 0) or current_energy is None:
            continue
        energy_ratio = current_energy / previous_energy
        if energy_ratio >= 0.8:
            continue
        kind = "bearish" if current["direction"] == "up" else "bullish"
        divergence = {
            "stroke_index": current["index"],
            "trade_date": current["end_date"],
            "type": kind,
            "price": current["end_price"],
            "energy_ratio": _round(energy_ratio),
            "method": "price extends the prior same-direction stroke while absolute MACD histogram energy falls below 80%",
        }
        divergences.append(divergence)
        signal = {
            "stroke_index": current["index"],
            "trade_date": current["end_date"],
            "type": "first_sell_candidate" if kind == "bearish" else "first_buy_candidate",
            "price": current["end_price"],
            "basis": "same-direction stroke MACD-energy divergence",
            "confirmed": True,
        }
        signals.append(signal)
        first_signal_by_stroke[current["index"]] = signal

    for first_index, first in first_signal_by_stroke.items():
        revisit_index = first_index + 2
        if revisit_index >= len(strokes):
            continue
        revisit = strokes[revisit_index]
        buy = first["type"] == "first_buy_candidate"
        holds = (
            revisit["direction"] == "down" and revisit["end_price"] > first["price"]
            if buy else
            revisit["direction"] == "up" and revisit["end_price"] < first["price"]
        )
        if holds:
            signals.append({
                "stroke_index": revisit["index"],
                "trade_date": revisit["end_date"],
                "type": "second_buy_candidate" if buy else "second_sell_candidate",
                "price": revisit["end_price"],
                "basis": "the second same-direction test does not break the first divergence extreme",
                "confirmed": True,
            })

    if latest_center:
        start = int(latest_center["end_stroke_index"]) + 1
        upper = float(latest_center["upper"])
        lower = float(latest_center["lower"])
        for index in range(start, len(strokes) - 1):
            breakout, pullback = strokes[index:index + 2]
            if (
                breakout["direction"] == "up" and breakout["end_price"] > upper
                and pullback["direction"] == "down" and pullback["end_price"] > upper
            ):
                signals.append({
                    "stroke_index": pullback["index"], "trade_date": pullback["end_date"],
                    "type": "third_buy_candidate", "price": pullback["end_price"],
                    "basis": "upward center breakout followed by a pullback that remains above the center",
                    "confirmed": True,
                })
            if (
                breakout["direction"] == "down" and breakout["end_price"] < lower
                and pullback["direction"] == "up" and pullback["end_price"] < lower
            ):
                signals.append({
                    "stroke_index": pullback["index"], "trade_date": pullback["end_date"],
                    "type": "third_sell_candidate", "price": pullback["end_price"],
                    "basis": "downward center breakout followed by a rebound that remains below the center",
                    "confirmed": True,
                })
    unique_signals = list({(item["type"], item["stroke_index"]): item for item in signals}.values())
    return divergences, sorted(unique_signals, key=lambda item: item["stroke_index"])


def _chan_analysis(rows: list[dict], current_price: float) -> dict[str, Any]:
    """Return a deterministic, auditable Chan-structure candidate contract."""

    normalized = _chan_normalized_bars(rows)
    fractals = _chan_fractals(normalized)
    closes = [float(_number(row.get("close"))) for row in rows]
    ema12 = _ema_series(closes, 12)
    ema26 = _ema_series(closes, 26)
    macd = [left - right for left, right in zip(ema12, ema26)]
    signal = _ema_series(macd, 9)
    histogram = [line - signal_value for line, signal_value in zip(macd, signal)]
    strokes = _chan_strokes(fractals, histogram)
    segments = _chan_segments(strokes)
    centers = _chan_centers(strokes)
    divergences, signals = _chan_divergences_and_signals(strokes, centers)
    latest_center = centers[-1] if centers else None
    position = (
        "above_center" if latest_center and current_price > latest_center["upper"]
        else "below_center" if latest_center and current_price < latest_center["lower"]
        else "inside_center" if latest_center
        else "unavailable"
    )
    return {
        "status": "ready" if centers else "limited_structure",
        "variant": "deterministic inclusion/fractal/stroke candidate",
        "normalized_bar_count": len(normalized),
        "source_bar_count": len(rows),
        "fractals": fractals[-30:],
        "strokes": strokes[-20:],
        "segment_candidates": segments[-12:],
        "centers": centers[-8:],
        "divergences": divergences[-8:],
        "signals": signals[-12:],
        "current_position": position,
        "methodology": {
            "inclusion": "containing bars merge in the inferred direction before fractal detection",
            "fractal": "three normalized bars with both high and low above/below their neighbors",
            "stroke": "alternating confirmed fractals separated by at least four normalized-bar indices (five bars inclusive)",
            "segment": "three alternating strokes whose third stroke extends the first; exposed as a candidate",
            "center": "intersection of the price ranges of at least three consecutive strokes",
            "divergence": "new price extreme with same-direction MACD histogram energy below 80% of the prior stroke",
            "signals": "first/second/third buy-sell points are structural candidates, never execution advice",
        },
        "limitations": [
            "Chan schools differ on inclusion, stroke and segment rules; this response identifies its exact variant",
            "the latest unconfirmed source-bar structure is not promoted to a fractal or stroke",
        ],
    }


def _swing_zones(
    rows: list[dict], current: float, atr: float | None, window: int = 3
) -> dict[str, Any]:
    candidates: list[float] = []
    for index in range(window, len(rows) - window):
        low = _number(rows[index].get("low"))
        high = _number(rows[index].get("high"))
        around = rows[index - window:index + window + 1]
        nearby_lows = [_number(item.get("low")) for item in around]
        nearby_highs = [_number(item.get("high")) for item in around]
        if low is not None and all(value is None or low <= value for value in nearby_lows):
            candidates.append(low)
        if high is not None and all(value is None or high >= value for value in nearby_highs):
            candidates.append(high)
    tolerance = max((atr or 0) * 0.5, current * 0.01)
    clusters: list[list[float]] = []
    for candidate in sorted(candidates):
        target = next(
            (cluster for cluster in clusters if abs(mean(cluster) - candidate) <= tolerance),
            None,
        )
        if target is None:
            clusters.append([candidate])
        else:
            target.append(candidate)
    levels = [
        {"price": _round(mean(cluster)), "touches": len(cluster)}
        for cluster in clusters if len(cluster) >= 2
    ]
    support = sorted((item for item in levels if item["price"] <= current), key=lambda item: current - item["price"])
    resistance = sorted((item for item in levels if item["price"] > current), key=lambda item: item["price"] - current)
    return {
        "support": support[:3],
        "resistance": resistance[:3],
        "tolerance": _round(tolerance),
        "method": "3-bar swing pivots clustered within max(0.5×ATR14, 1% of close)",
    }


def _resample_ohlcv(rows: list[dict], timeframe: str) -> list[dict]:
    """Aggregate governed daily bars into reproducible weekly/monthly bars."""

    if timeframe not in {"1w", "1mo"}:
        raise ValueError(f"unsupported resample timeframe: {timeframe}")
    ordered = sorted(rows, key=lambda row: _day(row.get("trade_date")) or date.min)
    grouped: dict[tuple[int, int], list[dict]] = {}
    for row in ordered:
        observed = _day(row.get("trade_date"))
        if observed is None:
            continue
        if timeframe == "1w":
            iso = observed.isocalendar()
            key = (iso.year, iso.week)
        else:
            key = (observed.year, observed.month)
        grouped.setdefault(key, []).append(row)
    bars: list[dict] = []
    for group in grouped.values():
        opens = [_number(row.get("open")) for row in group]
        highs = [_number(row.get("high")) for row in group]
        lows = [_number(row.get("low")) for row in group]
        closes = [_number(row.get("close")) for row in group]
        if any(value is None for value in (opens[0], closes[-1])):
            continue
        clean_highs = [value for value in highs if value is not None]
        clean_lows = [value for value in lows if value is not None]
        if not clean_highs or not clean_lows:
            continue
        bars.append({
            "trade_date": group[-1].get("trade_date"),
            "open": opens[0],
            "high": max(clean_highs),
            "low": min(clean_lows),
            "close": closes[-1],
            "vol": sum(_number(row.get("vol")) or 0 for row in group),
            "amount": sum(_number(row.get("amount")) or 0 for row in group),
            "source_observations": len(group),
            "period_complete": True,
        })
    if bars:
        # The latest aggregate can still be the live week/month.  Indicators may
        # describe it, but structural confirmation must not depend on it.
        bars[-1]["period_complete"] = False
    return bars


def _adjust_ohlcv(
    rows: list[dict], adjustments: list[dict], *, dataset: str,
) -> tuple[list[dict], dict[str, Any]]:
    """Put OHLC on the latest factor basis without mixing adjusted/raw history."""

    factors = {
        observed: factor
        for row in adjustments
        if (observed := _day(row.get("trade_date"))) is not None
        and (factor := _number(row.get("adj_factor"))) not in (None, 0)
    }
    ordered = sorted(rows, key=lambda row: _day(row.get("trade_date")) or date.min)
    matched = [row for row in ordered if _day(row.get("trade_date")) in factors]
    if not matched:
        return ordered, {
            "dataset": dataset,
            "status": "missing",
            "matched": 0,
            "source_rows": len(ordered),
            "price_basis": "raw",
            "warning": "adjustment factors are unavailable; long-horizon returns and levels may cross corporate-action discontinuities",
        }
    latest_day = _day(ordered[-1].get("trade_date")) if ordered else None
    if latest_day not in factors:
        return ordered, {
            "dataset": dataset,
            "status": "stale",
            "matched": len(matched),
            "source_rows": len(ordered),
            "price_basis": "raw",
            "warning": "the latest price has no adjustment factor; adjusted analysis was not mixed with raw history",
        }
    latest_factor = factors[latest_day]
    adjusted: list[dict] = []
    for row in matched:
        observed = _day(row.get("trade_date"))
        factor = factors[observed]
        scale = factor / latest_factor
        item = dict(row)
        for field in ("open", "high", "low", "close", "pre_close"):
            value = _number(row.get(field))
            if value is not None:
                item[field] = value * scale
        adjusted.append(item)
    complete = len(adjusted) == len(ordered)
    return adjusted, {
        "dataset": dataset,
        "status": "applied" if complete else "partial_history",
        "matched": len(adjusted),
        "source_rows": len(ordered),
        "coverage_pct": _round(len(adjusted) / len(ordered) * 100 if ordered else None),
        "price_basis": "latest-factor-adjusted",
        "latest_factor": latest_factor,
        "warning": None if complete else "analysis is limited to dates with factors; raw and adjusted prices were not mixed",
    }


def _pivot_systems(previous: dict) -> dict[str, Any]:
    """Return the commonly used deterministic next-period pivot families."""

    high = _number(previous.get("high"))
    low = _number(previous.get("low"))
    close = _number(previous.get("close"))
    open_price = _number(previous.get("open"))
    basis = previous.get("trade_date")
    if None in (high, low, close):
        return {}
    assert high is not None and low is not None and close is not None
    span = high - low
    classic = (high + low + close) / 3
    woodie = (high + low + 2 * close) / 4
    demark_x = (
        high + 2 * low + close
        if open_price is not None and close < open_price
        else 2 * high + low + close
        if open_price is not None and close > open_price
        else high + low + 2 * close
    )
    cpr_bc = (high + low) / 2
    cpr_tc = 2 * classic - cpr_bc

    def levels(**values: float | None) -> dict[str, Any]:
        return {key: _round(value) for key, value in values.items()} | {
            "basis_date": basis,
        }

    return {
        "classic": levels(
            pivot=classic,
            support_1=2 * classic - high,
            support_2=classic - span,
            support_3=low - 2 * (high - classic),
            resistance_1=2 * classic - low,
            resistance_2=classic + span,
            resistance_3=high + 2 * (classic - low),
        ) | {"method": "P=(H+L+C)/3"},
        "fibonacci": levels(
            pivot=classic,
            support_1=classic - 0.382 * span,
            support_2=classic - 0.618 * span,
            support_3=classic - span,
            resistance_1=classic + 0.382 * span,
            resistance_2=classic + 0.618 * span,
            resistance_3=classic + span,
        ) | {"method": "classic pivot ± Fibonacci fractions of prior range"},
        "woodie": levels(
            pivot=woodie,
            support_1=2 * woodie - high,
            support_2=woodie - span,
            resistance_1=2 * woodie - low,
            resistance_2=woodie + span,
        ) | {"method": "P=(H+L+2C)/4"},
        "camarilla": levels(
            support_1=close - span * 1.1 / 12,
            support_2=close - span * 1.1 / 6,
            support_3=close - span * 1.1 / 4,
            support_4=close - span * 1.1 / 2,
            resistance_1=close + span * 1.1 / 12,
            resistance_2=close + span * 1.1 / 6,
            resistance_3=close + span * 1.1 / 4,
            resistance_4=close + span * 1.1 / 2,
        ) | {"method": "C ± prior range × Camarilla multipliers"},
        "demark": levels(
            pivot=demark_x / 4,
            support_1=demark_x / 2 - high,
            resistance_1=demark_x / 2 - low,
        ) | {"method": "DeMark conditional X from prior O/H/L/C"},
        "cpr": levels(
            pivot=classic,
            lower_central=min(cpr_bc, cpr_tc),
            upper_central=max(cpr_bc, cpr_tc),
            width=abs(cpr_tc - cpr_bc),
        ) | {"method": "Central Pivot Range (P, BC, TC)"},
    }


def _timeframe_analysis(
    rows: list[dict],
    *,
    timeframe: str,
    chart_points: int,
) -> dict[str, Any]:
    """Calculate one consistent technical contract for any OHLCV instrument."""

    prices = sorted(rows, key=lambda row: _day(row.get("trade_date")) or date.min)
    prices = [
        row for row in prices
        if all(_number(row.get(field)) is not None for field in ("open", "high", "low", "close"))
    ]
    if not prices:
        return {"status": "missing", "timeframe": timeframe, "observations": 0}
    closes = [float(_number(row.get("close"))) for row in prices]
    opens = [float(_number(row.get("open"))) for row in prices]
    highs = [float(_number(row.get("high"))) for row in prices]
    lows = [float(_number(row.get("low"))) for row in prices]
    volumes = [_number(row.get("vol")) or 0 for row in prices]
    ema12 = _ema_series(closes, 12)
    ema26 = _ema_series(closes, 26)
    macd_line = [left - right for left, right in zip(ema12, ema26)]
    signal_line = _ema_series(macd_line, 9)
    true_ranges = [
        max(
            highs[index] - lows[index],
            abs(highs[index] - closes[index - 1]) if index else 0,
            abs(lows[index] - closes[index - 1]) if index else 0,
        )
        for index in range(len(prices))
    ]
    returns = [current / previous - 1 for previous, current in pairwise(closes) if previous]
    latest_close = closes[-1]
    ma = {str(window): _round(_moving_average(closes, window)) for window in (5, 10, 20, 60, 120, 250)}
    ma_series = {window: _sma_series(closes, window) for window in (5, 10, 20, 60)}
    trend_score = sum(latest_close > value for value in (ma["20"], ma["60"], ma["120"]) if value is not None)
    atr14 = mean(true_ranges[-14:]) if len(true_ranges) >= 14 else None
    kdj_k, kdj_d, kdj_j = _stochastic(highs, lows, closes)
    adx14, plus_di14, minus_di14 = _adx(highs, lows, closes)
    obv_series = _obv(closes, volumes)
    typical = [(3 * close + low + opened + high) / 6 for opened, high, low, close in zip(opens, highs, lows, closes)]
    bull_series = _weighted_series(typical, 20)
    valid_bull = [value for value in bull_series if value is not None]
    bull_line = valid_bull[-1] if valid_bull else None
    bear_line = mean(valid_bull[-6:]) if len(valid_bull) >= 6 else None
    threshold_pct = max(5.0, min(15.0, 2 * atr14 / latest_close * 100 if atr14 else 5.0))
    structure_prices = (
        prices
        if timeframe == "1d"
        else [row for row in prices if row.get("period_complete", True)]
    )
    zigzag = _zigzag(structure_prices, threshold_pct)
    fibonacci_retracement = _fibonacci_retracement(zigzag, latest_close)
    chan_analysis = _chan_analysis(structure_prices, latest_close)
    legs = [
        {
            "start_date": left["trade_date"],
            "end_date": right["trade_date"],
            "direction": "up" if (change := _pct_change(right["price"], left["price"])) is not None and change >= 0 else "down",
            "change_pct": _round(change),
            "confirmed": bool(left["confirmed"] and right["confirmed"]),
        }
        for left, right in pairwise(zigzag)
    ]
    window20 = closes[-20:]
    boll_mid = mean(window20) if window20 else None
    boll_std = pstdev(window20) if len(window20) > 1 else None
    periods_per_year = {"1d": 252, "1w": 52, "1mo": 12}[timeframe]
    pivot_systems = _pivot_systems(prices[-2] if len(prices) >= 2 else prices[-1])
    chart_start = max(0, len(prices) - chart_points)
    chart = []
    for index in range(chart_start, len(prices)):
        window = closes[max(0, index - 19):index + 1]
        average = mean(window) if len(window) == 20 else None
        deviation = pstdev(window) if len(window) == 20 else None
        chart.append({
            "trade_date": prices[index].get("trade_date"),
            "open": _round(opens[index]), "high": _round(highs[index]),
            "low": _round(lows[index]), "close": _round(closes[index]),
            "volume": _round(volumes[index]),
            "ma_5": _round(ma_series[5][index]), "ma_10": _round(ma_series[10][index]),
            "ma_20": _round(ma_series[20][index]), "ma_60": _round(ma_series[60][index]),
            "bollinger_upper": _round(average + 2 * deviation) if average is not None and deviation is not None else None,
            "bollinger_lower": _round(average - 2 * deviation) if average is not None and deviation is not None else None,
        })
    minimum_history = {"1d": 60, "1w": 52, "1mo": 24}[timeframe]
    return {
        "status": "ready" if len(prices) >= minimum_history else "limited_history",
        "timeframe": timeframe,
        "observations": len(prices),
        "observation": {
            "trade_date": prices[-1].get("trade_date"),
            "close": latest_close,
            "period_complete": prices[-1].get("period_complete", True),
        },
        "trend": {
            "moving_averages": ma,
            "ema_12": _round(ema12[-1]), "ema_26": _round(ema26[-1]),
            "macd": _round(macd_line[-1]), "macd_signal": _round(signal_line[-1]),
            "regime": "bullish" if trend_score == 3 else "bearish" if trend_score == 0 else "mixed",
            "bull_bear_boundary": {
                "value": ma["250"],
                "alias": f"MA250 ({timeframe})",
                "state": "above" if ma["250"] is not None and latest_close > ma["250"] else "below" if ma["250"] is not None else "unavailable",
            },
            "weighted_trend": {
                "bull_line": _round(bull_line), "bear_line": _round(bear_line),
                "state": "bullish" if bull_line is not None and bear_line is not None and bull_line >= bear_line else "bearish" if bull_line is not None and bear_line is not None else "unavailable",
                "formula": "bull=20-period LWMA((3C+L+O+H)/6); bear=SMA6(bull)",
            },
            "systems": {
                "ichimoku": _ichimoku(highs, lows, latest_close),
                "donchian_20": _donchian(highs, lows, latest_close, 20),
                "donchian_55": _donchian(highs, lows, latest_close, 55),
                "supertrend_10_3": _supertrend(highs, lows, closes),
                "aroon_25": _aroon(highs, lows),
                "parabolic_sar": _parabolic_sar(highs, lows, closes),
            },
        },
        "momentum": {
            **{
                f"return_{window}_period_pct": _round(_pct_change(latest_close, closes[-window - 1]) if len(closes) > window else None)
                for window in (4, 12, 20, 60)
            },
            "rsi_14": _round(_rsi(closes)),
            "stochastic_rsi_14": _round(_stochastic_rsi(closes)),
            "roc_12_pct": _round(_pct_change(latest_close, closes[-13]) if len(closes) >= 13 else None),
            "kdj": {"k": _round(kdj_k), "d": _round(kdj_d), "j": _round(kdj_j)},
            "williams_r_14": _round(_williams_r(highs, lows, closes)),
            "cci_20": _round(_cci(highs, lows, closes)),
            "mfi_14": _round(_mfi(highs, lows, closes, volumes)),
        },
        "volatility": {
            "atr_14": _round(atr14),
            "annualized_volatility_20_period_pct": _round(pstdev(returns[-20:]) * sqrt(periods_per_year) * 100 if len(returns) >= 20 else None),
            "bollinger_20": {
                "lower": _round(boll_mid - 2 * boll_std if boll_mid is not None and boll_std is not None else None),
                "middle": _round(boll_mid),
                "upper": _round(boll_mid + 2 * boll_std if boll_mid is not None and boll_std is not None else None),
            },
            "max_drawdown_pct": _round(_max_drawdown(closes)),
            "downside_risk": _downside_risk(returns, periods_per_year),
        },
        "volume_price": {
            "volume_5_average": _round(mean(volumes[-5:]) if len(volumes) >= 5 else None),
            "volume_20_average": _round(mean(volumes[-20:]) if len(volumes) >= 20 else None),
            "volume_5_to_20_ratio": _round(
                _safe_div(
                    mean(volumes[-5:]) if len(volumes) >= 5 else None,
                    mean(volumes[-20:]) if len(volumes) >= 20 else None,
                )
            ),
            "obv": _round(obv_series[-1]),
            "chaikin_money_flow_20": _round(
                _chaikin_money_flow(highs, lows, closes, volumes)
            ),
        },
        "levels": {
            "swing_zones": _swing_zones(prices[-250:], latest_close, atr14),
            "pivot_systems": pivot_systems,
            "classic_pivots": pivot_systems.get("classic", {}),
            "fibonacci_retracement": fibonacci_retracement,
            "gaps": _gap_analysis(prices[-500:]),
        },
        "trend_strength": {"adx_14": _round(adx14), "plus_di_14": _round(plus_di14), "minus_di_14": _round(minus_di14)},
        "candlesticks": {"patterns": _candlestick_patterns(prices)},
        "wave_analysis": {
            "status": "candidate_only", "method": "volatility-adjusted ZigZag",
            "threshold_pct": _round(threshold_pct), "pivots": zigzag, "legs": legs,
            "current_leg": legs[-1]["direction"] if legs else "unavailable",
        },
        "chan_analysis": chan_analysis,
        "chart": {"price_basis": "source OHLCV", "points": chart},
    }


def _long_horizon_summary(rows: list[dict]) -> dict[str, Any]:
    ordered = sorted(rows, key=lambda row: _day(row.get("trade_date")) or date.min)
    valid = [(row, _number(row.get("close"))) for row in ordered]
    valid = [(row, close) for row, close in valid if close is not None and _day(row.get("trade_date"))]
    if not valid:
        return {"status": "missing"}
    by_year: dict[int, list[tuple[dict, float]]] = {}
    for row, close in valid:
        observed = _day(row.get("trade_date"))
        assert observed is not None
        by_year.setdefault(observed.year, []).append((row, float(close)))
    annual_returns = [
        {
            "year": year,
            "start_close": _round(points[0][1]),
            "end_close": _round(points[-1][1]),
            "return_pct": _round(_pct_change(points[-1][1], points[0][1])),
            "observations": len(points),
        }
        for year, points in sorted(by_year.items())
    ]
    first_day = _day(valid[0][0].get("trade_date"))
    last_day = _day(valid[-1][0].get("trade_date"))
    years = (last_day - first_day).days / 365.2425 if first_day and last_day else 0
    cagr = ((valid[-1][1] / valid[0][1]) ** (1 / years) - 1) * 100 if years > 0 and valid[0][1] else None
    trailing = valid[-252:]
    trailing_values = [point[1] for point in trailing]
    latest = valid[-1][1]
    return {
        "status": "ready",
        "first_date": first_day, "last_date": last_day,
        "calendar_year_returns": annual_returns,
        "cagr_pct": _round(cagr),
        "max_drawdown_pct": _round(_max_drawdown([point[1] for point in valid])),
        "trailing_52_week": {
            "high": _round(max(trailing_values)), "low": _round(min(trailing_values)),
            "from_high_pct": _round(_pct_change(latest, max(trailing_values))),
            "from_low_pct": _round(_pct_change(latest, min(trailing_values))),
        },
        "methodology": "yearly trend is summarized from daily observations; indicators that require 14+ annual bars are intentionally not fabricated",
    }


def _prior_year(value: date) -> date:
    """Return the same reporting date a year earlier, including leap days."""
    try:
        return value.replace(year=value.year - 1)
    except ValueError:
        return value.replace(year=value.year - 1, day=28)


class ResearchService:
    """High-level calculations whose formulas remain stable across clients."""

    def __init__(self, data_service, repository):
        self._data = data_service
        self._repository = repository

    def capabilities(self) -> dict[str, Any]:
        return capability_catalog(self._repository.backfill_statuses())

    def _load(
        self,
        name: str,
        *,
        filters: dict[str, str] | None = None,
        start: date | None = None,
        end: date | None = None,
        as_of: date | None = None,
        limit: int = 1000,
    ) -> list[dict]:
        return self._data.query_dataset(
            name,
            exact_filters=filters or {},
            date_value=None,
            start_date=start.isoformat() if start else None,
            end_date=end.isoformat() if end else None,
            as_of=as_of.isoformat() if as_of else None,
            limit=limit,
            offset=0,
            include_total=False,
        )["data"]

    def _load_many(
        self,
        name: str,
        *,
        filters: dict[str, str] | None = None,
        start: date | None = None,
        end: date | None = None,
        as_of: date | None = None,
        max_records: int = 5000,
    ) -> list[dict]:
        """Page through a governed dataset without bypassing its public rules."""

        rows: list[dict] = []
        offset = 0
        while len(rows) < max_records:
            limit = min(1000, max_records - len(rows))
            page = self._data.query_dataset(
                name,
                exact_filters=filters or {},
                date_value=None,
                start_date=start.isoformat() if start else None,
                end_date=end.isoformat() if end else None,
                as_of=as_of.isoformat() if as_of else None,
                limit=limit,
                offset=offset,
                include_total=False,
            )["data"]
            rows.extend(page)
            if len(page) < limit:
                break
            offset += len(page)
        return rows

    def _ensure_stock(self, ts_code: str) -> dict:
        rows = self._load("stock_basic", filters={"ts_code": ts_code}, limit=1)
        if not rows:
            raise RecordNotFoundError(f"stock not found: {ts_code}")
        return rows[0]

    @staticmethod
    def _latest_by_date(rows: list[dict], column: str) -> dict[str, dict]:
        selected: dict[str, dict] = {}
        for row in rows:
            observed = _day(row.get(column))
            if observed is None:
                continue
            selected.setdefault(observed.isoformat(), row)
        return selected

    @staticmethod
    def _provenance(data: dict[str, list[dict]]) -> list[dict]:
        return [
            {"dataset": name, "returned": len(rows), "state": "available" if rows else "missing"}
            for name, rows in data.items()
        ]

    def fundamentals(
        self,
        ts_code: str,
        *,
        periods: int = 12,
        as_of: date | None = None,
    ) -> dict[str, Any]:
        effective_as_of = as_of or business_now().date()
        basic = self._ensure_stock(ts_code)
        loaded = {
            "financial_indicator": self._load(
                "financial_indicator", filters={"ts_code": ts_code},
                end=effective_as_of, as_of=effective_as_of, limit=min(periods * 4, 48),
            ),
            "income": self._load(
                "income", filters={"ts_code": ts_code}, end=effective_as_of,
                as_of=effective_as_of, limit=min(periods * 4, 48),
            ),
            "balancesheet": self._load(
                "balancesheet", filters={"ts_code": ts_code}, end=effective_as_of,
                as_of=effective_as_of, limit=min(periods * 4, 48),
            ),
            "cashflow": self._load(
                "cashflow", filters={"ts_code": ts_code}, end=effective_as_of,
                as_of=effective_as_of, limit=min(periods * 4, 48),
            ),
            "fina_mainbz": self._load(
                "fina_mainbz", filters={"ts_code": ts_code}, end=effective_as_of,
                limit=1000,
            ),
        }
        indicators = self._latest_by_date(loaded["financial_indicator"], "end_date")
        incomes = self._latest_by_date(loaded["income"], "end_date")
        balances = self._latest_by_date(loaded["balancesheet"], "end_date")
        cashflows = self._latest_by_date(loaded["cashflow"], "end_date")
        dates = sorted(set(indicators) | set(incomes) | set(balances) | set(cashflows))[-periods:]
        series: list[dict[str, Any]] = []
        for observed in dates:
            indicator = indicators.get(observed, {})
            income = incomes.get(observed, {})
            balance = balances.get(observed, {})
            cashflow = cashflows.get(observed, {})
            prior_day = _prior_year(date.fromisoformat(observed)).isoformat()
            prior_income = incomes.get(prior_day, {})
            prior_cashflow = cashflows.get(prior_day, {})
            equity = balance.get("total_hldr_eqy_inc_min_int")
            equity_multiplier = _safe_div(balance.get("total_assets"), equity)
            net_margin = _number(indicator.get("netprofit_margin"))
            asset_turnover = _number(indicator.get("assets_turn"))
            dupont_roe = (
                net_margin / 100 * asset_turnover * equity_multiplier * 100
                if None not in (net_margin, asset_turnover, equity_multiplier)
                else None
            )
            series.append(
                {
                    "period": observed,
                    "announced_at": max(
                        (value for value in (
                            _day(indicator.get("ann_date")), _day(income.get("ann_date")),
                            _day(balance.get("ann_date")), _day(cashflow.get("ann_date")),
                        ) if value is not None),
                        default=None,
                    ),
                    "profitability": {
                        "gross_margin_pct": _number(indicator.get("grossprofit_margin")),
                        "net_margin_pct": net_margin,
                        "roe_pct": _number(indicator.get("roe")),
                        "roa_pct": _number(indicator.get("roa")),
                        "roic_pct": _number(indicator.get("roic")),
                    },
                    "growth": {
                        "revenue_yoy_pct": _round(_pct_change(income.get("revenue"), prior_income.get("revenue"))),
                        "net_income_yoy_pct": _round(_pct_change(income.get("n_income_attr_p"), prior_income.get("n_income_attr_p"))),
                        "operating_cashflow_yoy_pct": _round(_pct_change(cashflow.get("n_cashflow_act"), prior_cashflow.get("n_cashflow_act"))),
                    },
                    "quality": {
                        "operating_cash_to_net_income": _round(_safe_div(cashflow.get("n_cashflow_act"), income.get("n_income_attr_p"))),
                        "sales_cash_to_revenue": _round(_safe_div(cashflow.get("c_fr_sale_sg"), income.get("revenue"))),
                        "accrual_to_assets": _round(
                            _safe_div(
                                net_income - operating_cashflow,
                                balance.get("total_assets"),
                            )
                            if (
                                (net_income := _number(income.get("n_income_attr_p")))
                                is not None
                                and (
                                    operating_cashflow := _number(
                                        cashflow.get("n_cashflow_act")
                                    )
                                )
                                is not None
                            )
                            else None
                        ),
                        "free_cashflow": _number(cashflow.get("free_cashflow") or indicator.get("fcff")),
                    },
                    "solvency": {
                        "current_ratio": _number(indicator.get("current_ratio")),
                        "quick_ratio": _number(indicator.get("quick_ratio")),
                        "debt_to_assets_pct": _number(indicator.get("debt_to_assets")),
                        "interest_coverage": _number(indicator.get("ebit_to_interest")),
                    },
                    "efficiency": {
                        "receivables_turnover": _number(indicator.get("ar_turn")),
                        "inventory_turnover": _number(indicator.get("inv_turn")),
                        "asset_turnover": asset_turnover,
                        "turnover_days": _number(indicator.get("turn_days")),
                    },
                    "dupont": {
                        "net_margin_pct": net_margin,
                        "asset_turnover": asset_turnover,
                        "equity_multiplier": _round(equity_multiplier),
                        "derived_roe_pct": _round(dupont_roe),
                        "reported_roe_pct": _number(indicator.get("roe")),
                    },
                }
            )

        segment_rows = loaded["fina_mainbz"]
        latest_segment_period = max(
            (
                observed
                for row in segment_rows
                if (observed := _day(row.get("end_date"))) is not None
            ),
            default=None,
        )
        latest_segments = [
            row for row in segment_rows if _day(row.get("end_date")) == latest_segment_period
        ]
        latest_segments.sort(key=lambda row: _number(row.get("bz_sales")) or 0, reverse=True)
        total_segment_sales = sum(_number(row.get("bz_sales")) or 0 for row in latest_segments)
        segments = [
            {
                "item": row.get("bz_item"),
                "code": row.get("bz_code"),
                "sales": _number(row.get("bz_sales")),
                "profit": _number(row.get("bz_profit")),
                "cost": _number(row.get("bz_cost")),
                "sales_share_pct": _round(
                    (_number(row.get("bz_sales")) or 0) / total_segment_sales * 100
                    if total_segment_sales else None
                ),
            }
            for row in latest_segments[:20]
        ]
        missing = [item["dataset"] for item in self._provenance(loaded) if item["state"] == "missing"]
        historical_view = effective_as_of < business_now().date()
        return {
            "data": {
                "profile": basic,
                "periods": series,
                "latest": series[-1] if series else None,
                "segments": {"period": latest_segment_period, "items": segments},
            },
            "meta": {
                "ts_code": ts_code,
                "as_of": effective_as_of,
                "generated_at": datetime.now(timezone.utc),
                "methodology": {
                    "growth": "same fiscal period one year earlier",
                    "dupont": "net margin × asset turnover × equity multiplier",
                    "segment_share": "share of latest returned segment sales",
                },
                "provenance": self._provenance(loaded),
                "quality": {
                    "status": "warning" if missing or historical_view else "ready",
                    "missing_datasets": missing,
                    "point_in_time_safe": not historical_view,
                    "warnings": ([
                        "fina_mainbz has no announcement-date contract; segment data is current-only in historical views"
                    ] if historical_view else []),
                },
            },
        }

    def valuation(
        self,
        ts_code: str,
        *,
        lookback_days: int = 730,
        peer_limit: int = 20,
        as_of: date | None = None,
    ) -> dict[str, Any]:
        effective_as_of = as_of or business_now().date()
        self._ensure_stock(ts_code)
        start = effective_as_of - timedelta(days=lookback_days - 1)
        valuations = self._load(
            "stock_daily_basic", filters={"ts_code": ts_code}, start=start,
            end=effective_as_of, as_of=effective_as_of, limit=min(lookback_days, 1000),
        )
        valuations.sort(key=lambda row: _day(row.get("trade_date")) or date.min)
        indicators = self._load(
            "financial_indicator", filters={"ts_code": ts_code}, end=effective_as_of,
            as_of=effective_as_of, limit=8,
        )
        latest = valuations[-1] if valuations else None
        metrics: dict[str, Any] = {}
        for field in ("pe", "pe_ttm", "pb", "ps", "ps_ttm", "dv_ratio", "dv_ttm"):
            current = latest.get(field) if latest else None
            history = [row.get(field) for row in valuations if _number(row.get(field)) is not None]
            if field.startswith("pe"):
                history = [value for value in history if (_number(value) or 0) > 0]
            metrics[field] = {
                "value": _number(current),
                "history_percentile": _percentile_rank(history, current),
                "history_low": min((_number(value) for value in history), default=None),
                "history_high": max((_number(value) for value in history), default=None),
                "observations": len(history),
            }

        peers = (
            self._data.stock_peers(
                ts_code,
                provider=None,
                as_of=effective_as_of,
                max_sectors=3,
                limit=peer_limit,
            ).get("data", [])
            if peer_limit
            else []
        )
        peer_rows: list[dict[str, Any]] = []
        for peer in peers[:peer_limit]:
            peer_code = peer.get("ts_code")
            if not peer_code or peer_code == ts_code:
                continue
            rows = self._load(
                "stock_daily_basic", filters={"ts_code": peer_code},
                end=effective_as_of, as_of=effective_as_of, limit=1,
            )
            if rows:
                peer_rows.append({
                    "ts_code": peer_code,
                    "shared_sector_count": peer.get("shared_sector_count"),
                    "trade_date": rows[0].get("trade_date"),
                    "pe_ttm": _number(rows[0].get("pe_ttm")),
                    "pb": _number(rows[0].get("pb")),
                    "ps_ttm": _number(rows[0].get("ps_ttm")),
                })
        latest_indicator = indicators[0] if indicators else {}
        peer_medians = {
            field: _round(median(values)) if (values := [
                row[field] for row in peer_rows if row.get(field) is not None
            ]) else None
            for field in ("pe_ttm", "pb", "ps_ttm")
        }
        return {
            "data": {
                "latest": latest,
                "historical_distribution": metrics,
                "peers": {"items": peer_rows, "medians": peer_medians},
                "intrinsic_value_inputs": {
                    "fcff": _number(latest_indicator.get("fcff")),
                    "fcfe": _number(latest_indicator.get("fcfe")),
                    "roe_pct": _number(latest_indicator.get("roe")),
                    "roic_pct": _number(latest_indicator.get("roic")),
                    "dividend_yield_ttm_pct": _number(latest.get("dv_ttm")) if latest else None,
                    "fair_value": None,
                    "required_assumptions": ["forecast horizon", "terminal growth", "discount rate"],
                },
            },
            "meta": {
                "ts_code": ts_code,
                "as_of": effective_as_of,
                "lookback_days": lookback_days,
                "generated_at": datetime.now(timezone.utc),
                "provenance": [
                    {"dataset": "stock_daily_basic", "returned": len(valuations)},
                    {"dataset": "financial_indicator", "returned": len(indicators)},
                    {"dataset": "stock peers", "returned": len(peer_rows)},
                ],
                "quality": {
                    "status": "ready" if latest else "warning",
                    "warnings": [] if latest else ["no valuation observations in requested window"],
                },
            },
        }

    def technicals(
        self,
        ts_code: str,
        *,
        lookback_days: int = 3000,
        chart_points: int = 120,
        benchmark: str = "399006.SZ",
        as_of: date | None = None,
    ) -> dict[str, Any]:
        effective_as_of = as_of or business_now().date()
        self._ensure_stock(ts_code)
        start = effective_as_of - timedelta(days=max(lookback_days * 2, 500))
        prices = self._load_many(
            "stock_daily", filters={"ts_code": ts_code}, start=start,
            end=effective_as_of, as_of=effective_as_of, max_records=min(lookback_days, 5000),
        )
        benchmark_rows = self._load_many(
            "index_daily", filters={"ts_code": benchmark}, start=start,
            end=effective_as_of, as_of=effective_as_of, max_records=min(lookback_days, 5000),
        )
        adjustments = self._load_many(
            "adj_factor", filters={"ts_code": ts_code}, start=start,
            end=effective_as_of, max_records=min(lookback_days, 5000),
        )
        prices.sort(key=lambda row: _day(row.get("trade_date")) or date.min)
        prices = [
            row for row in prices
            if all(_number(row.get(field)) is not None for field in ("open", "high", "low", "close"))
        ]
        source_price_count = len(prices)
        benchmark_rows.sort(key=lambda row: _day(row.get("trade_date")) or date.min)
        prices, adjustment_meta = _adjust_ohlcv(
            prices, adjustments, dataset="adj_factor"
        )
        closes = [float(_number(row.get("close"))) for row in prices]
        highs = [float(_number(row.get("high"))) for row in prices]
        lows = [float(_number(row.get("low"))) for row in prices]
        opens = [float(_number(row.get("open"))) for row in prices]
        volumes = [_number(row.get("vol")) or 0 for row in prices]
        if not closes:
            raise RecordNotFoundError(f"no daily prices found for {ts_code}")

        ema12 = _ema_series(closes, 12)
        ema26 = _ema_series(closes, 26)
        macd_line = [left - right for left, right in zip(ema12, ema26)]
        signal_line = _ema_series(macd_line, 9)
        true_ranges: list[float] = []
        for index, row in enumerate(prices):
            high = _number(row.get("high"))
            low = _number(row.get("low"))
            previous = _number(prices[index - 1].get("close")) if index else None
            if high is None or low is None:
                continue
            true_ranges.append(max(high - low, abs(high - previous) if previous else 0, abs(low - previous) if previous else 0))
        returns = [
            current / previous - 1
            for previous, current in pairwise(closes) if previous
        ]
        latest_close = closes[-1]
        ma = {str(window): _round(_moving_average(closes, window)) for window in (5, 10, 20, 60, 120, 250)}
        ma_series = {window: _sma_series(closes, window) for window in (5, 10, 20, 60)}
        window20 = closes[-20:] if len(closes) >= 20 else closes
        boll_mid = mean(window20) if window20 else None
        boll_std = pstdev(window20) if len(window20) > 1 else None
        momentum = {
            f"return_{window}d_pct": _round(_pct_change(latest_close, closes[-window - 1]) if len(closes) > window else None)
            for window in (20, 60, 120, 250)
        }
        adjustment_safe = adjustment_meta["status"] in {"applied", "partial_history"}
        relative: dict[str, Any]
        if adjustment_safe:
            benchmark_by_day = {
                _day(row.get("trade_date")): _number(row.get("close"))
                for row in benchmark_rows if _day(row.get("trade_date")) and _number(row.get("close")) is not None
            }
            stock_by_day = {
                _day(row.get("trade_date")): _number(row.get("close"))
                for row in prices if _day(row.get("trade_date")) and _number(row.get("close")) is not None
            }
            common_days = sorted(set(stock_by_day) & set(benchmark_by_day))
            relative = {"status": "ready" if common_days else "missing"}
            for window in (20, 60, 120):
                if len(common_days) > window:
                    first, last = common_days[-window - 1], common_days[-1]
                    stock_return = _pct_change(stock_by_day[last], stock_by_day[first])
                    benchmark_return = _pct_change(benchmark_by_day[last], benchmark_by_day[first])
                    relative[f"excess_return_{window}d_pct"] = _round(
                        stock_return - benchmark_return
                        if stock_return is not None and benchmark_return is not None else None
                    )
                else:
                    relative[f"excess_return_{window}d_pct"] = None
            relative["risk_metrics"] = _relative_risk_metrics(
                [float(stock_by_day[observed]) for observed in common_days],
                [float(benchmark_by_day[observed]) for observed in common_days],
            )
        else:
            relative = {
                "status": "unavailable_unadjusted",
                "warning": "relative returns and risk metrics require current adjustment factors",
                **{f"excess_return_{window}d_pct": None for window in (20, 60, 120)},
                "risk_metrics": {"status": "unavailable_unadjusted", "windows": {}},
            }

        adjusted_closes = closes if adjustment_safe else []
        volume_5 = mean(volumes[-5:]) if len(volumes) >= 5 else None
        volume_20 = mean(volumes[-20:]) if len(volumes) >= 20 else None
        atr14 = mean(true_ranges[-14:]) if len(true_ranges) >= 14 else None
        trend_score = sum(
            latest_close > value for value in (ma["20"], ma["60"], ma["120"]) if value is not None
        )
        latest_rsi = _rsi(closes)
        kdj_k, kdj_d, kdj_j = _stochastic(highs, lows, closes)
        adx14, plus_di14, minus_di14 = _adx(highs, lows, closes)
        obv_series = _obv(closes, volumes)
        typical_prices = [
            (3 * close + low + open_price + high) / 6
            for open_price, high, low, close in zip(opens, highs, lows, closes)
        ]
        bull_line_series = _weighted_series(typical_prices, 20)
        valid_bull_lines = [value for value in bull_line_series if value is not None]
        bull_line = valid_bull_lines[-1] if valid_bull_lines else None
        bear_line = mean(valid_bull_lines[-6:]) if len(valid_bull_lines) >= 6 else None
        threshold_pct = max(
            5.0,
            min(15.0, (2 * atr14 / latest_close * 100) if atr14 and latest_close else 5.0),
        )
        pivots = _zigzag(prices, threshold_pct)
        fibonacci_retracement = _fibonacci_retracement(pivots, latest_close)
        chan_analysis = _chan_analysis(prices, latest_close)
        legs = []
        for left, right in pairwise(pivots):
            change = _pct_change(right["price"], left["price"])
            legs.append({
                "start_date": left["trade_date"],
                "end_date": right["trade_date"],
                "direction": "up" if (change or 0) >= 0 else "down",
                "change_pct": _round(change),
                "confirmed": bool(left["confirmed"] and right["confirmed"]),
            })
        swing_zones = _swing_zones(prices[-250:], latest_close, atr14)
        previous = prices[-2] if len(prices) >= 2 else prices[-1]
        pivot_systems = _pivot_systems(previous)
        classic_levels = pivot_systems.get("classic", {})
        weekly_prices = _resample_ohlcv(prices, "1w")
        monthly_prices = _resample_ohlcv(prices, "1mo")
        chart_start = max(0, len(prices) - chart_points)
        chart_rows = []
        for index in range(chart_start, len(prices)):
            boll_window = closes[max(0, index - 19):index + 1]
            boll_average = mean(boll_window) if len(boll_window) == 20 else None
            boll_deviation = pstdev(boll_window) if len(boll_window) == 20 else None
            chart_rows.append({
                "trade_date": prices[index].get("trade_date"),
                "open": _round(opens[index]),
                "high": _round(highs[index]),
                "low": _round(lows[index]),
                "close": _round(closes[index]),
                "volume": _round(volumes[index]),
                "ma_5": _round(ma_series[5][index]),
                "ma_10": _round(ma_series[10][index]),
                "ma_20": _round(ma_series[20][index]),
                "ma_60": _round(ma_series[60][index]),
                "bollinger_upper": _round(boll_average + 2 * boll_deviation) if boll_average is not None and boll_deviation is not None else None,
                "bollinger_lower": _round(boll_average - 2 * boll_deviation) if boll_average is not None and boll_deviation is not None else None,
            })
        return {
            "data": {
                "observation": {"trade_date": prices[-1].get("trade_date"), "close": latest_close},
                "trend": {
                    "moving_averages": ma,
                    "ema_12": _round(ema12[-1]),
                    "ema_26": _round(ema26[-1]),
                    "macd": _round(macd_line[-1]),
                    "macd_signal": _round(signal_line[-1]),
                    "regime": "bullish" if trend_score == 3 else "bearish" if trend_score == 0 else "mixed",
                    "bull_bear_boundary": {
                        "value": ma["250"],
                        "alias": "MA250 / 年线 / 常见牛熊分界线",
                        "state": "above" if ma["250"] is not None and latest_close > ma["250"] else "below" if ma["250"] is not None else "unavailable",
                    },
                    "weighted_trend": {
                        "bull_line": _round(bull_line),
                        "bear_line": _round(bear_line),
                        "state": "bullish" if bull_line is not None and bear_line is not None and bull_line >= bear_line else "bearish" if bull_line is not None and bear_line is not None else "unavailable",
                        "formula": "bull = 20-period linearly weighted average of (3C+L+O+H)/6; bear = 6-period SMA of bull",
                        "terminology": "民间常称牛线/熊线；不把含义不统一的‘牛门线’当作标准名称",
                    },
                    "systems": {
                        "ichimoku": _ichimoku(highs, lows, latest_close),
                        "donchian_20": _donchian(highs, lows, latest_close, 20),
                        "donchian_55": _donchian(highs, lows, latest_close, 55),
                        "supertrend_10_3": _supertrend(highs, lows, closes),
                        "aroon_25": _aroon(highs, lows),
                        "parabolic_sar": _parabolic_sar(highs, lows, closes),
                    },
                },
                "momentum": {
                    **momentum,
                    "rsi_14": _round(latest_rsi),
                    "stochastic_rsi_14": _round(_stochastic_rsi(closes)),
                    "roc_12_pct": _round(_pct_change(latest_close, closes[-13]) if len(closes) >= 13 else None),
                    "kdj": {"k": _round(kdj_k), "d": _round(kdj_d), "j": _round(kdj_j)},
                    "williams_r_14": _round(_williams_r(highs, lows, closes)),
                    "cci_20": _round(_cci(highs, lows, closes)),
                    "mfi_14": _round(_mfi(highs, lows, closes, volumes)),
                },
                "volatility": {
                    "atr_14": _round(atr14),
                    "annualized_volatility_20d_pct": _round(pstdev(returns[-20:]) * sqrt(252) * 100 if len(returns) >= 20 else None),
                    "bollinger_20": {
                        "lower": _round(boll_mid - 2 * boll_std if boll_mid is not None and boll_std is not None else None),
                        "middle": _round(boll_mid),
                        "upper": _round(boll_mid + 2 * boll_std if boll_mid is not None and boll_std is not None else None),
                    },
                    "max_drawdown_pct": _round(_max_drawdown(closes)),
                    "downside_risk": _downside_risk(returns, 252),
                },
                "volume_price": {
                    "volume_5d_average": _round(volume_5),
                    "volume_20d_average": _round(volume_20),
                    "volume_5_to_20_ratio": _round(_safe_div(volume_5, volume_20)),
                    "obv": _round(obv_series[-1]),
                    "obv_change_20d": _round(obv_series[-1] - obv_series[-21]) if len(obv_series) > 20 else None,
                    "chaikin_money_flow_20": _round(
                        _chaikin_money_flow(highs, lows, closes, volumes)
                    ),
                },
                "levels": {
                    f"high_{window}d": _round(max(value for value in highs[-window:] if value is not None)) if len(highs) >= window else None
                    for window in (20, 60, 250)
                } | {
                    f"low_{window}d": _round(min(value for value in lows[-window:] if value is not None)) if len(lows) >= window else None
                    for window in (20, 60, 250)
                } | {
                    "swing_zones": swing_zones,
                    "classic_pivots": classic_levels,
                    "pivot_systems": pivot_systems,
                    "fibonacci_retracement": fibonacci_retracement,
                    "gaps": _gap_analysis(prices[-500:]),
                    "methodology": "rolling extrema are descriptive ranges; actionable zones require repeated swing touches or next-session pivot formulas",
                },
                "trend_strength": {
                    "adx_14": _round(adx14),
                    "plus_di_14": _round(plus_di14),
                    "minus_di_14": _round(minus_di14),
                },
                "candlesticks": {
                    "patterns": _candlestick_patterns(prices),
                    "methodology": "deterministic OHLC geometry; every pattern is a candidate that requires trend and volume confirmation",
                },
                "wave_analysis": {
                    "status": "candidate_only",
                    "method": "volatility-adjusted ZigZag swing extraction",
                    "threshold_pct": _round(threshold_pct),
                    "pivots": pivots,
                    "legs": legs,
                    "current_leg": legs[-1]["direction"] if legs else "unavailable",
                    "elliott_note": "Elliott labels are scenario-dependent; the API exposes reproducible pivots and does not claim one definitive wave count.",
                    "invalidation": "a live pivot remains unconfirmed until price reverses by the configured threshold",
                },
                "chan_analysis": chan_analysis,
                "relative_strength": {"benchmark": benchmark, **relative},
                "total_return": {
                    "status": "ready" if adjustment_safe else "unavailable_unadjusted",
                    "adjusted_observations": len(adjusted_closes),
                    "adjusted_return_pct": _round(_pct_change(adjusted_closes[-1], adjusted_closes[0])) if len(adjusted_closes) > 1 else None,
                },
                "chart": {
                    "price_basis": adjustment_meta["price_basis"],
                    "points": chart_rows,
                },
                "timeframes": {
                    "1d": _timeframe_analysis(
                        prices, timeframe="1d", chart_points=chart_points
                    ),
                    "1w": _timeframe_analysis(
                        weekly_prices, timeframe="1w", chart_points=chart_points
                    ),
                    "1mo": _timeframe_analysis(
                        monthly_prices, timeframe="1mo", chart_points=chart_points
                    ),
                },
                "long_horizon": _long_horizon_summary(prices),
            },
            "meta": {
                "ts_code": ts_code,
                "as_of": effective_as_of,
                "benchmark": benchmark,
                "chart_points": chart_points,
                "generated_at": datetime.now(timezone.utc),
                "provenance": [
                    {"dataset": "stock_daily", "returned": source_price_count},
                    {"dataset": "index_daily", "returned": len(benchmark_rows)},
                    {"dataset": "adj_factor", "returned": len(adjustments)},
                ],
                "price_adjustment": adjustment_meta,
                "quality": {
                    "status": "ready" if len(prices) >= 250 and not adjustment_meta.get("warning") else "warning",
                    "warnings": (
                        ([] if len(prices) >= 250 else ["fewer than 250 daily observations"])
                        + ([str(adjustment_meta["warning"])] if adjustment_meta.get("warning") else [])
                    ),
                },
            },
        }

    def instrument_technicals(
        self,
        asset_type: str,
        code: str,
        *,
        lookback_days: int = 3000,
        chart_points: int = 120,
        benchmark: str | None = None,
        provider: str | None = None,
        as_of: date | None = None,
    ) -> dict[str, Any]:
        """Analyze any governed OHLCV asset through one stable contract."""

        normalized_type = asset_type.lower()
        configurations = {
            "stock": ("stock_daily", "stock_basic", "stock"),
            "index": ("index_daily", "index_basic", "index"),
            "fund": ("fund_daily", "fund_basic", "fund"),
            "etf": ("fund_daily", "fund_basic", "fund"),
            "spot": ("sge_daily", "sge_basic", "commodity"),
            "sector": ("industry_daily", None, "sector"),
        }
        if normalized_type not in configurations:
            raise InvalidQueryError(
                "asset_type must be one of stock, index, fund, etf, spot, sector"
            )
        if normalized_type == "sector" and (provider or "ths").lower() != "ths":
            raise InvalidQueryError("sector technicals currently support provider=ths")
        dataset, basic_dataset, category = configurations[normalized_type]
        effective_as_of = as_of or business_now().date()
        start = effective_as_of - timedelta(days=max(lookback_days * 2, 1500))
        prices = self._load_many(
            dataset,
            filters={"ts_code": code},
            start=start,
            end=effective_as_of,
            max_records=min(lookback_days, 5000),
        )
        if not prices:
            raise RecordNotFoundError(
                f"no governed {normalized_type} prices found for {code}"
            )
        source_price_count = len(prices)
        adjustment_rows: list[dict] = []
        adjustment_meta: dict[str, Any] = {
            "status": "not_applicable", "price_basis": "raw"
        }
        adjustment_dataset = (
            "adj_factor" if normalized_type == "stock"
            else "fund_adj" if normalized_type in {"fund", "etf"}
            else None
        )
        if adjustment_dataset:
            adjustment_rows = self._load_many(
                adjustment_dataset,
                filters={"ts_code": code},
                start=start,
                end=effective_as_of,
                max_records=min(lookback_days, 5000),
            )
            prices, adjustment_meta = _adjust_ohlcv(
                prices, adjustment_rows, dataset=adjustment_dataset
            )
        identity = None
        if basic_dataset:
            basic_rows = self._load(basic_dataset, filters={"ts_code": code}, limit=1)
            identity = basic_rows[0] if basic_rows else None
        weekly = _resample_ohlcv(prices, "1w")
        monthly = _resample_ohlcv(prices, "1mo")
        timeframes = {
            "1d": _timeframe_analysis(prices, timeframe="1d", chart_points=chart_points),
            "1w": _timeframe_analysis(weekly, timeframe="1w", chart_points=chart_points),
            "1mo": _timeframe_analysis(monthly, timeframe="1mo", chart_points=chart_points),
        }
        benchmark_rows: list[dict] = []
        relative: dict[str, Any] = {"benchmark": benchmark, "status": "not_requested"}
        adjustment_safe = (
            adjustment_dataset is None
            or adjustment_meta["status"] in {"applied", "partial_history"}
        )
        if benchmark and adjustment_safe:
            benchmark_rows = self._load_many(
                "index_daily", filters={"ts_code": benchmark}, start=start,
                end=effective_as_of,
                max_records=min(lookback_days, 5000),
            )
            asset_by_day = {
                _day(row.get("trade_date")): _number(row.get("close")) for row in prices
                if _day(row.get("trade_date")) and _number(row.get("close")) is not None
            }
            benchmark_by_day = {
                _day(row.get("trade_date")): _number(row.get("close")) for row in benchmark_rows
                if _day(row.get("trade_date")) and _number(row.get("close")) is not None
            }
            common = sorted(set(asset_by_day) & set(benchmark_by_day))
            relative = {"benchmark": benchmark, "status": "ready" if common else "missing"}
            for window in (20, 60, 120, 250):
                value = None
                if len(common) > window:
                    first, last = common[-window - 1], common[-1]
                    asset_return = _pct_change(asset_by_day[last], asset_by_day[first])
                    benchmark_return = _pct_change(benchmark_by_day[last], benchmark_by_day[first])
                    if asset_return is not None and benchmark_return is not None:
                        value = asset_return - benchmark_return
                relative[f"excess_return_{window}d_pct"] = _round(value)
            relative["risk_metrics"] = _relative_risk_metrics(
                [float(asset_by_day[observed]) for observed in common],
                [float(benchmark_by_day[observed]) for observed in common],
            )
        elif benchmark:
            relative = {
                "benchmark": benchmark,
                "status": "unavailable_unadjusted",
                "warning": "relative returns and risk metrics require current adjustment factors",
                **{f"excess_return_{window}d_pct": None for window in (20, 60, 120, 250)},
                "risk_metrics": {"status": "unavailable_unadjusted", "windows": {}},
            }
        warnings = []
        if len(prices) < 250:
            warnings.append(f"only {len(prices)} daily observations; long-cycle signals are limited")
        if timeframes["1mo"]["observations"] < 24:
            warnings.append("fewer than 24 monthly bars")
        if adjustment_meta.get("warning"):
            warnings.append(str(adjustment_meta["warning"]))
        return {
            "data": {
                "instrument": {
                    "asset_type": normalized_type,
                    "category": category,
                    "code": code,
                    "provider": provider.lower() if provider else None,
                    "identity": identity,
                },
                "timeframes": timeframes,
                "long_horizon": _long_horizon_summary(prices),
                "relative_strength": relative,
            },
            "meta": {
                "asset_type": normalized_type,
                "code": code,
                "as_of": effective_as_of,
                "generated_at": datetime.now(timezone.utc),
                "provenance": [
                    {"dataset": dataset, "returned": source_price_count},
                    *([{"dataset": adjustment_dataset, "returned": len(adjustment_rows)}] if adjustment_dataset else []),
                    {"dataset": "index_daily", "returned": len(benchmark_rows)},
                ],
                "price_adjustment": adjustment_meta,
                "quality": {
                    "status": "ready" if not warnings else "warning",
                    "warnings": warnings,
                },
            },
        }

    def repurchase_progress(
        self,
        ts_code: str,
        *,
        as_of: date | None = None,
        benchmark: str = "399006.SZ",
    ) -> dict[str, Any]:
        """Reconcile structured buyback disclosures with subsequent prices."""

        effective_as_of = as_of or business_now().date()
        self._ensure_stock(ts_code)
        rows = self._load(
            "repurchase",
            filters={"ts_code": ts_code},
            end=effective_as_of,
            limit=1000,
        )
        rows.sort(key=lambda row: _day(row.get("ann_date")) or date.min)
        plan_markers = ("预案", "股东大会通过", "董事会通过")
        execution_markers = ("实施", "完成")
        plans = [row for row in rows if any(marker in str(row.get("proc") or "") for marker in plan_markers)]
        executions = [row for row in rows if any(marker in str(row.get("proc") or "") for marker in execution_markers)]
        latest_plan = plans[-1] if plans else None
        latest_execution = executions[-1] if executions else None
        target_plan = next(
            (row for row in reversed(plans) if _number(row.get("amount")) is not None),
            latest_plan,
        )
        planned_amount = _number(target_plan.get("amount")) if target_plan else None
        executed_amount = _number(latest_execution.get("amount")) if latest_execution else None
        executed_volume = _number(latest_execution.get("vol")) if latest_execution else None
        latest_ann_date = _day(latest_execution.get("ann_date")) if latest_execution else None
        price_start = latest_ann_date - timedelta(days=10) if latest_ann_date else effective_as_of - timedelta(days=30)
        prices = self._load(
            "stock_daily", filters={"ts_code": ts_code}, start=price_start,
            end=effective_as_of, as_of=effective_as_of, limit=60,
        )
        benchmark_rows = self._load(
            "index_daily", filters={"ts_code": benchmark}, start=price_start,
            end=effective_as_of, as_of=effective_as_of, limit=60,
        )
        prices.sort(key=lambda row: _day(row.get("trade_date")) or date.min)
        benchmark_rows.sort(key=lambda row: _day(row.get("trade_date")) or date.min)

        def return_since(rows_: list[dict], observed: date | None) -> float | None:
            eligible = [row for row in rows_ if _day(row.get("trade_date")) and (observed is None or _day(row.get("trade_date")) >= observed)]
            if len(eligible) < 2:
                return None
            return _pct_change(eligible[-1].get("close"), eligible[0].get("close"))

        stock_return = return_since(prices, latest_ann_date)
        benchmark_return = return_since(benchmark_rows, latest_ann_date)
        current_close = _number(prices[-1].get("close")) if prices else None
        average_price = _safe_div(executed_amount, executed_volume)
        progress = (
            executed_amount / planned_amount * 100
            if executed_amount is not None and planned_amount not in (None, 0)
            else None
        )
        status = "no_disclosure"
        if latest_execution:
            status = "completed" if "完成" in str(latest_execution.get("proc") or "") else "in_progress"
        elif latest_plan:
            status = "approved_not_reported_executing"
        return {
            "data": {
                "status": status,
                "plan": latest_plan,
                "target_plan": target_plan,
                "latest_execution": latest_execution,
                "progress": {
                    "planned_amount": planned_amount,
                    "executed_amount": executed_amount,
                    "executed_volume": executed_volume,
                    "amount_progress_pct": _round(progress),
                    "average_execution_price": _round(average_price),
                    "current_close": _round(current_close),
                    "current_vs_average_execution_pct": _round(
                        _pct_change(current_close, average_price)
                    ),
                    "denominator_note": "uses the latest structured approved/proposal amount; a disclosed min-max range requires announcement text for both bounds",
                },
                "market_since_latest_execution_disclosure": {
                    "announcement_date": latest_ann_date,
                    "stock_return_pct": _round(stock_return),
                    "benchmark": benchmark,
                    "benchmark_return_pct": _round(benchmark_return),
                    "abnormal_return_pct": _round(
                        stock_return - benchmark_return
                        if stock_return is not None and benchmark_return is not None
                        else None
                    ),
                    "interpretation": "market response is evidence, not proof that the buyback caused the move",
                },
                "timeline": list(reversed(rows[-20:])),
            },
            "meta": {
                "ts_code": ts_code,
                "as_of": effective_as_of,
                "generated_at": datetime.now(timezone.utc),
                "provenance": [
                    {"dataset": "repurchase", "returned": len(rows)},
                    {"dataset": "stock_daily", "returned": len(prices)},
                    {"dataset": "index_daily", "returned": len(benchmark_rows)},
                ],
                "quality": {
                    "status": "ready" if rows else "warning",
                    "warnings": [] if rows else ["no local repurchase disclosures"],
                    "publication_finality": "late-arrival refresh enabled for the announcement date partition",
                },
            },
        }

    def capital_flow(
        self,
        ts_code: str,
        *,
        lookback_days: int = 60,
        as_of: date | None = None,
    ) -> dict[str, Any]:
        effective_as_of = as_of or business_now().date()
        self._ensure_stock(ts_code)
        start = effective_as_of - timedelta(days=lookback_days * 2)
        loaded = {
            "moneyflow": self._load("moneyflow", filters={"ts_code": ts_code}, start=start, end=effective_as_of, limit=lookback_days),
            "margin_detail": self._load("margin_detail", filters={"ts_code": ts_code}, start=start, end=effective_as_of, limit=lookback_days),
            "hk_hold": self._load("hk_hold", filters={"ts_code": ts_code}, start=start, end=effective_as_of, limit=lookback_days),
            "block_trade": self._load("block_trade", filters={"ts_code": ts_code}, start=start, end=effective_as_of, limit=500),
            "cyq_perf": self._load("cyq_perf", filters={"ts_code": ts_code}, start=start, end=effective_as_of, limit=lookback_days),
        }
        money = loaded["moneyflow"]
        net_amounts = [_number(row.get("net_mf_amount")) for row in money]
        clean_net = [value for value in net_amounts if value is not None]
        margin = loaded["margin_detail"]
        northbound = loaded["hk_hold"]
        blocks = loaded["block_trade"]
        chips = loaded["cyq_perf"]
        return {
            "data": {
                "moneyflow": {
                    "observations": len(clean_net),
                    "net_amount_sum": _round(sum(clean_net)) if clean_net else None,
                    "net_amount_average": _round(mean(clean_net)) if clean_net else None,
                    "positive_days": sum(value > 0 for value in clean_net),
                    "latest": money[0] if money else None,
                },
                "margin": {
                    "observations": len(margin),
                    "latest": margin[0] if margin else None,
                    "financing_buy_sum": _round(sum(_number(row.get("rzmre")) or 0 for row in margin)) if margin else None,
                    "financing_repay_sum": _round(sum(_number(row.get("rzche")) or 0 for row in margin)) if margin else None,
                },
                "northbound": {"observations": len(northbound), "latest": northbound[0] if northbound else None},
                "block_trades": {
                    "count": len(blocks),
                    "amount_sum": _round(sum(_number(row.get("amount")) or 0 for row in blocks)),
                    "latest": blocks[0] if blocks else None,
                },
                "chips": {"observations": len(chips), "latest": chips[0] if chips else None},
            },
            "meta": {
                "ts_code": ts_code,
                "as_of": effective_as_of,
                "lookback_days": lookback_days,
                "generated_at": datetime.now(timezone.utc),
                "provenance": self._provenance(loaded),
                "quality": {
                    "status": "warning" if not money else "ready",
                    "warnings": [
                        "event-like sources can legitimately be empty; absence is not treated as zero"
                    ],
                },
            },
        }

    def event_study(
        self,
        ts_code: str,
        *,
        event_date: date,
        pre_days: int = 5,
        post_days: int = 10,
        benchmark: str = "399006.SZ",
    ) -> dict[str, Any]:
        self._ensure_stock(ts_code)
        padding = max((pre_days + post_days) * 3, 30)
        start, end = event_date - timedelta(days=padding), event_date + timedelta(days=padding)
        stock_rows = self._load("stock_daily", filters={"ts_code": ts_code}, start=start, end=end, limit=200)
        benchmark_rows = self._load("index_daily", filters={"ts_code": benchmark}, start=start, end=end, limit=200)
        stock = {_day(row.get("trade_date")): row for row in stock_rows if _day(row.get("trade_date"))}
        index = {_day(row.get("trade_date")): row for row in benchmark_rows if _day(row.get("trade_date"))}
        common = sorted(set(stock) & set(index))
        anchor_candidates = [observed for observed in common if observed >= event_date]
        if not anchor_candidates:
            raise RecordNotFoundError("no trading observation on or after event_date")
        anchor = anchor_candidates[0]
        anchor_index = common.index(anchor)
        selected = common[max(0, anchor_index - pre_days):anchor_index + post_days + 1]
        observations = []
        car = 0.0
        for observed in selected:
            stock_return = _number(stock[observed].get("pct_chg"))
            benchmark_return = _number(index[observed].get("pct_chg"))
            abnormal = (
                stock_return - benchmark_return
                if stock_return is not None and benchmark_return is not None else None
            )
            if abnormal is not None:
                car += abnormal
            observations.append({
                "relative_day": common.index(observed) - anchor_index,
                "trade_date": observed,
                "stock_return_pct": stock_return,
                "benchmark_return_pct": benchmark_return,
                "abnormal_return_pct": _round(abnormal),
                "cumulative_abnormal_return_pct": _round(car),
            })
        return {
            "data": {"event_trade_date": anchor, "observations": observations, "car_pct": _round(car)},
            "meta": {
                "ts_code": ts_code,
                "event_date": event_date,
                "benchmark": benchmark,
                "pre_days": pre_days,
                "post_days": post_days,
                "methodology": "market-adjusted return: stock daily return minus benchmark daily return",
                "generated_at": datetime.now(timezone.utc),
                "quality": {"status": "ready" if len(observations) == pre_days + post_days + 1 else "warning"},
            },
        }

    def market_breadth(self, *, as_of: date | None = None) -> dict[str, Any]:
        effective_as_of = as_of or business_now().date()
        row = self._repository.market_breadth(effective_as_of)
        if not row:
            raise RecordNotFoundError("no market breadth observation found")
        securities = int(row.get("securities") or 0)
        advancing = int(row.get("advancing") or 0)
        declining = int(row.get("declining") or 0)
        normalized = {
            **row,
            "securities": securities,
            "advancing": advancing,
            "declining": declining,
            "unchanged": int(row.get("unchanged") or 0),
            "average_return_pct": _round(_number(row.get("average_return_pct"))),
            "median_return_pct": _round(_number(row.get("median_return_pct"))),
            "amount": _round(_number(row.get("amount"))),
            "above_ma20": int(row.get("above_ma20") or 0),
            "above_ma60": int(row.get("above_ma60") or 0),
            "limit_up": int(row.get("limit_up") or 0),
            "limit_down": int(row.get("limit_down") or 0),
            "opened_limits": int(row.get("opened_limits") or 0),
        }
        return {
            "data": {
                **normalized,
                "advance_decline_ratio": _round(_safe_div(advancing, declining)),
                "advance_share_pct": _round(advancing / securities * 100 if securities else None),
                "above_ma20_share_pct": _round((row.get("above_ma20") or 0) / securities * 100 if securities else None),
                "above_ma60_share_pct": _round((row.get("above_ma60") or 0) / securities * 100 if securities else None),
            },
            "meta": {
                "as_of": effective_as_of,
                "generated_at": datetime.now(timezone.utc),
                "methodology": "latest market date not later than as_of; moving averages use the latest 20/60 observations",
                "provenance": ["stock_daily", "limit_list_d"],
            },
        }

    def sector_rotation(
        self,
        provider: str,
        *,
        lookback_days: int = 60,
        as_of: date | None = None,
        limit: int = 20,
    ) -> dict[str, Any]:
        if provider not in {"ths", "dc", "tdx"}:
            raise InvalidQueryError("provider must be one of ths, dc or tdx")
        effective_as_of = as_of or business_now().date()
        catalog = self._data.list_sectors(
            provider=provider,
            as_of=effective_as_of,
            limit=1000,
        ).get("data", [])
        names = {item.get("sector_code"): item.get("name") for item in catalog}
        allowed_codes = [code for code in names if code]
        rows = (
            self._repository.sector_rotation(
                provider,
                as_of=effective_as_of,
                lookback_days=lookback_days,
                limit=max(len(allowed_codes), limit * 2),
                allowed_codes=allowed_codes,
            )
            if allowed_codes
            else []
        )
        enriched = [
            {
                **row,
                "name": names.get(row.get("ts_code")),
                "close": _number(row.get("close")),
                "start_close": _number(row.get("start_close")),
                "average_volume": _number(row.get("average_volume")),
                "average_daily_return": _number(row.get("average_daily_return")),
                "observations": int(row.get("observations") or 0),
                "period_return_pct": _round(_number(row.get("period_return_pct"))),
            }
            for row in rows
        ]
        effective_dates = [
            observed
            for row in rows
            if (observed := _day(row.get("trade_date"))) is not None
        ]
        effective_date = max(effective_dates, default=None)
        lag_days = (
            (effective_as_of - effective_date).days
            if effective_date is not None
            else None
        )
        leaders = enriched[:limit]
        laggards = list(reversed(enriched[-limit:]))
        return {
            "data": {"leaders": leaders, "laggards": laggards},
            "meta": {
                "provider": provider,
                "as_of": effective_as_of,
                "effective_date": effective_date,
                "lag_days": lag_days,
                "lookback_days": lookback_days,
                "generated_at": datetime.now(timezone.utc),
                "methodology": (
                    "compounded provider daily returns ranked within the active "
                    "provider sector catalog"
                ),
                "provenance": [f"{provider} sector catalog", f"{provider} sector daily"],
                "quality": {
                    "status": (
                        "ready"
                        if rows and lag_days is not None and lag_days <= 7
                        else "warning"
                    ),
                    "warnings": (
                        []
                        if rows and lag_days is not None and lag_days <= 7
                        else [
                            "provider sector data is missing or more than seven days behind as_of"
                        ]
                    ),
                },
            },
        }
