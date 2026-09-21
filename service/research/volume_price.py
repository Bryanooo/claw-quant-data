"""Deterministic daily-bar volume/price research calculations.

The module deliberately separates what daily OHLCV can prove from intraday
claims that require minute, trade or order-book observations.  Its anchored
VWAP values are daily-bar proxies based on typical price, never represented as
session VWAP or a true price-volume profile.
"""

from __future__ import annotations

from datetime import date, datetime
from statistics import mean, pstdev
from typing import Any


def _number(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _round(value: float | None, digits: int = 4) -> float | None:
    return None if value is None else round(value, digits)


def _day(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if not value:
        return None
    text = str(value).strip().replace("-", "")[:8]
    try:
        return datetime.strptime(text, "%Y%m%d").date()
    except ValueError:
        return None


def _ema(values: list[float], window: int) -> float | None:
    if not values:
        return None
    alpha = 2 / (window + 1)
    current = values[0]
    for value in values[1:]:
        current = alpha * value + (1 - alpha) * current
    return current


def _series(rows: list[dict]) -> dict[str, list[float]]:
    closes = [float(_number(row.get("close"))) for row in rows]
    highs = [float(_number(row.get("high"))) for row in rows]
    lows = [float(_number(row.get("low"))) for row in rows]
    volumes = [float(_number(row.get("vol")) or 0) for row in rows]
    obv = [0.0]
    accumulation_distribution: list[float] = []
    pvt = [0.0]
    force = [0.0]
    ad_value = 0.0
    ease: list[float] = [0.0]
    for index, (high, low, close, volume) in enumerate(
        zip(highs, lows, closes, volumes)
    ):
        spread = high - low
        close_location = ((2 * close - high - low) / spread) if spread else 0.0
        ad_value += close_location * volume
        accumulation_distribution.append(ad_value)
        if index == 0:
            continue
        previous_close = closes[index - 1]
        obv.append(
            obv[-1] + volume
            if close > previous_close
            else obv[-1] - volume if close < previous_close else obv[-1]
        )
        pvt.append(
            pvt[-1] + volume * (close / previous_close - 1)
            if previous_close else pvt[-1]
        )
        force.append((close - previous_close) * volume)
        midpoint_move = (high + low - highs[index - 1] - lows[index - 1]) / 2
        ease.append(midpoint_move * spread / volume if volume else 0.0)
    return {
        "closes": closes,
        "highs": highs,
        "lows": lows,
        "volumes": volumes,
        "obv": obv,
        "ad": accumulation_distribution,
        "pvt": pvt,
        "force": force,
        "ease": ease,
    }


def _window_change(values: list[float], window: int) -> float | None:
    if len(values) <= window:
        return None
    start = values[-window - 1]
    return values[-1] - start


def _divergence(
    closes: list[float], indicator: list[float], window: int,
) -> dict[str, Any]:
    if len(closes) <= window or len(indicator) <= window:
        return {"status": "insufficient_history", "window": window}
    start_close = closes[-window - 1]
    price_change = (closes[-1] / start_close - 1) * 100 if start_close else None
    indicator_change = _window_change(indicator, window)
    classification = "none"
    if price_change is not None and price_change >= 2 and indicator_change is not None and indicator_change < 0:
        classification = "bearish_candidate"
    elif price_change is not None and price_change <= -2 and indicator_change is not None and indicator_change > 0:
        classification = "bullish_candidate"
    return {
        "status": "ready",
        "window": window,
        "classification": classification,
        "price_change_pct": _round(price_change),
        "indicator_change": _round(indicator_change),
        "method": "candidate only: price must move at least 2% while the cumulative volume indicator moves oppositely",
    }


def _weighted_typical_price(rows: list[dict]) -> float | None:
    numerator = denominator = 0.0
    for row in rows:
        high = _number(row.get("high"))
        low = _number(row.get("low"))
        close = _number(row.get("close"))
        volume = _number(row.get("vol"))
        if None in (high, low, close, volume) or not volume:
            continue
        numerator += ((high + low + close) / 3) * volume
        denominator += volume
    return numerator / denominator if denominator else None


def _anchored_vwap_proxies(rows: list[dict], latest_close: float) -> dict[str, Any]:
    latest_day = _day(rows[-1].get("trade_date")) if rows else None
    year_rows = (
        [row for row in rows if _day(row.get("trade_date")) and _day(row.get("trade_date")).year == latest_day.year]
        if latest_day else []
    )
    anchors: dict[str, Any] = {}
    for name, selected in (
        ("20_period", rows[-20:]),
        ("60_period", rows[-60:]),
        ("120_period", rows[-120:]),
        ("year_to_date", year_rows),
    ):
        value = _weighted_typical_price(selected)
        anchors[name] = {
            "value": _round(value),
            "observations": len(selected),
            "distance_from_close_pct": _round(
                (latest_close / value - 1) * 100 if value else None
            ),
        }
    return {
        "status": "ready" if any(item["value"] is not None for item in anchors.values()) else "missing_volume",
        "anchors": anchors,
        "basis": "daily-bar proxy: volume-weighted typical price (H+L+C)/3; not intraday session VWAP",
    }


def _turnover_analysis(rows: list[dict]) -> dict[str, Any]:
    ordered = sorted(rows, key=lambda row: _day(row.get("trade_date")) or date.min)
    free_turnover = [
        value for row in ordered
        if (value := _number(row.get("turnover_rate_f"))) is not None
    ]
    total_turnover = [
        value for row in ordered
        if (value := _number(row.get("turnover_rate"))) is not None
    ]
    volume_ratios = [
        value for row in ordered
        if (value := _number(row.get("volume_ratio"))) is not None
    ]
    if not free_turnover and not total_turnover:
        return {"status": "missing"}
    values = free_turnover or total_turnover
    latest = values[-1]
    history = values[-250:]
    return {
        "status": "ready",
        "basis": "free_float" if free_turnover else "circulating_float",
        "latest_pct": _round(latest),
        "average_20_pct": _round(mean(values[-20:]) if len(values) >= 20 else None),
        "percentile_250": _round(
            sum(value <= latest for value in history) / len(history) * 100
            if history else None
        ),
        "provider_volume_ratio": _round(volume_ratios[-1] if volume_ratios else None),
        "method": "turnover normalizes traded volume by the reported free or circulating share base",
    }


def volume_price_analysis(
    rows: list[dict], *, turnover_rows: list[dict] | None = None,
) -> dict[str, Any]:
    """Return auditable daily/weekly/monthly bar volume-price evidence."""

    ordered = sorted(rows, key=lambda row: _day(row.get("trade_date")) or date.min)
    valid = [
        row for row in ordered
        if all(_number(row.get(field)) is not None for field in ("high", "low", "close", "vol"))
    ]
    if len(valid) < 2:
        return {"status": "insufficient_history", "observations": len(valid)}
    values = _series(valid)
    closes = values["closes"]
    highs = values["highs"]
    lows = values["lows"]
    volumes = values["volumes"]
    latest_volume = volumes[-1]
    volume_5 = mean(volumes[-5:]) if len(volumes) >= 5 else None
    volume_20 = mean(volumes[-20:]) if len(volumes) >= 20 else None
    ratio = volume_5 / volume_20 if volume_5 is not None and volume_20 else None
    baseline = volumes[-120:]
    deviation = pstdev(baseline) if len(baseline) > 1 else None
    zscore = (latest_volume - mean(baseline)) / deviation if deviation else None
    history = volumes[-250:]
    percentile = sum(value <= latest_volume for value in history) / len(history) * 100
    latest_return = (closes[-1] / closes[-2] - 1) * 100 if closes[-2] else None
    activity = "expanding" if ratio is not None and ratio >= 1.2 else "contracting" if ratio is not None and ratio <= 0.8 else "normal"
    price_direction = "up" if latest_return is not None and latest_return > 0 else "down" if latest_return is not None and latest_return < 0 else "flat"
    regime = {
        ("up", "expanding"): "bullish_confirmation",
        ("down", "expanding"): "bearish_distribution",
        ("up", "contracting"): "weak_rally",
        ("down", "contracting"): "selling_exhaustion_candidate",
    }.get((price_direction, activity), "neutral")

    breakout: dict[str, Any] = {"status": "insufficient_history"}
    if len(valid) >= 21:
        prior_high = max(highs[-21:-1])
        prior_low = min(lows[-21:-1])
        latest_to_prior_volume = latest_volume / mean(volumes[-21:-1]) if mean(volumes[-21:-1]) else None
        direction = "up" if closes[-1] > prior_high else "down" if closes[-1] < prior_low else "none"
        confirmed = direction != "none" and latest_to_prior_volume is not None and latest_to_prior_volume >= 1.2
        breakout = {
            "status": "ready",
            "direction": direction,
            "confirmed_by_volume": confirmed,
            "prior_20_high": _round(prior_high),
            "prior_20_low": _round(prior_low),
            "latest_to_prior_20_volume_ratio": _round(latest_to_prior_volume),
            "rule": "close outside the prior 20-bar range; volume confirmation requires at least 1.2x prior-20 average",
        }

    force_13 = _ema(values["force"][-60:], 13)
    ease_14 = mean(values["ease"][-14:]) if len(values["ease"]) >= 14 else None
    return {
        "status": "ready",
        "observations": len(valid),
        "observation": {
            "trade_date": valid[-1].get("trade_date"),
            "close": _round(closes[-1]),
            "period_complete": valid[-1].get("period_complete", True),
        },
        "activity": {
            "latest_volume": _round(latest_volume),
            "average_5": _round(volume_5),
            "average_20": _round(volume_20),
            "average_5_to_20_ratio": _round(ratio),
            "zscore_120": _round(zscore),
            "percentile_250": _round(percentile),
            "state": activity,
        },
        "price_volume_regime": {
            "price_direction": price_direction,
            "latest_return_pct": _round(latest_return),
            "volume_state": activity,
            "classification": regime,
            "method": "descriptive four-quadrant classification; exhaustion is a candidate, not a reversal signal",
        },
        "breakout_confirmation": breakout,
        "indicators": {
            "obv": _round(values["obv"][-1]),
            "accumulation_distribution": _round(values["ad"][-1]),
            "price_volume_trend": _round(values["pvt"][-1]),
            "force_index_13": _round(force_13),
            "ease_of_movement_14": _round(ease_14, 8),
            "comparability_note": "raw indicator levels are instrument-specific; compare direction and history, not levels across assets",
        },
        "divergence": {
            "obv_20": _divergence(closes, values["obv"], 20),
            "obv_60": _divergence(closes, values["obv"], 60),
            "ad_20": _divergence(closes, values["ad"], 20),
            "ad_60": _divergence(closes, values["ad"], 60),
        },
        "anchored_vwap_proxy": _anchored_vwap_proxies(valid, closes[-1]),
        "turnover": _turnover_analysis(turnover_rows or []),
        "limitations": [
            "volume is actual traded quantity and is not adjustment-factor normalized",
            "true intraday VWAP, volume profile, CVD and order imbalance require minute, trade or Level-2 data",
        ],
    }
