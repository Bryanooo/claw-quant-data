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
