"""Deterministic, versioned intraday indicators and observation signals."""

from __future__ import annotations

from datetime import datetime
from statistics import median
from typing import Any, Iterable, Mapping


RULE_VERSION = "intraday-observation-v2"


def _number(value: Any) -> float | None:
    try:
        return float(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _pct(last: Any, base: Any) -> float | None:
    last_value, base_value = _number(last), _number(base)
    if last_value is None or not base_value:
        return None
    return (last_value / base_value - 1) * 100


def _median(values: Iterable[float | None]) -> float | None:
    clean = [value for value in values if value is not None]
    return median(clean) if clean else None


def _quality(*, expected: int, observed: int, timestamp_ok: bool = True) -> dict:
    coverage = observed / expected if expected else 0.0
    status = "complete" if coverage >= 0.95 and timestamp_ok else "partial"
    return {
        "status": status,
        "coverage": round(coverage, 4),
        "expected": expected,
        "observed": observed,
        "timestamp_fresh": timestamp_ok,
    }


def analyze_market(
    *,
    as_of: datetime,
    proxies: list[Mapping[str, Any]],
    sectors: list[Mapping[str, Any]],
    flows: list[Mapping[str, Any]],
    expected_proxies: int,
    expected_sectors: int,
    timestamp_fresh: bool = True,
) -> dict:
    """Classify the market from price, rebound, breadth and flow evidence."""

    proxy_pct = [
        _number(row.get("pct_chg"))
        if _number(row.get("pct_chg")) is not None
        else _pct(row.get("last") or row.get("close"), row.get("previous_close"))
        for row in proxies
    ]
    rebounds = [
        _pct(row.get("last") or row.get("close"), row.get("low"))
        for row in proxies
    ]
    market_pct = _median(proxy_pct)
    rebound = _median(rebounds)
    sector_pct = [
        _number(row.get("pct_chg"))
        if _number(row.get("pct_chg")) is not None
        else _pct(row.get("last") or row.get("close"), row.get("previous_close"))
        for row in sectors
    ]
    valid_sectors = [value for value in sector_pct if value is not None]
    breadth = (
        sum(value > 0 for value in valid_sectors) / len(valid_sectors)
        if valid_sectors else None
    )
    flow_values = [
        _number(row.get("main_net_inflow")) for row in flows
        if _number(row.get("main_net_inflow")) is not None
    ]
    flow_latest = flow_values[-1] if flow_values else None
    flow_recovery = (
        flow_latest - min(flow_values) if flow_latest is not None else None
    )

    signals: list[str] = []
    if market_pct is not None and breadth is not None and market_pct >= 2 and breadth >= 0.7:
        state, score = "strong_uptrend", 88.0
    elif market_pct is not None and breadth is not None and market_pct >= 0.5 and breadth >= 0.55:
        state, score = "uptrend", 72.0
    elif market_pct is not None and breadth is not None and market_pct <= -2 and breadth <= 0.3:
        state, score = "strong_downtrend", 88.0
    elif market_pct is not None and breadth is not None and market_pct <= -0.5 and breadth <= 0.45:
        state, score = "downtrend", 72.0
    else:
        state, score = "range", 52.0

    event_state = "none"
    if market_pct is not None and market_pct <= -1.5:
        event_state = "selloff"
        signals.append("broad_price_selloff")
    if rebound is not None and rebound >= 1.5:
        event_state = "reversal_watch"
        score = max(score, 68 + min(rebound * 2, 12))
        signals.append("low_price_recovery")
    if (
        rebound is not None and rebound >= 2
        and market_pct is not None and market_pct > 0
        and breadth is not None and breadth >= 0.65
        and (flow_recovery is None or flow_recovery > 0)
    ):
        event_state, score = "reversal_confirmed", max(score, 82 + min(rebound, 6))
        signals.extend(["price_reversal_confirmed", "breadth_confirmation"])
    elif (
        market_pct is not None and market_pct >= 0.8
        and breadth is not None and breadth >= 0.65
    ):
        event_state, score = "broad_risk_on", max(score, 78 + min(market_pct * 2, 8))
        signals.append("broad_risk_on")
    elif market_pct is not None and market_pct > 0.5 and breadth is not None and breadth < 0.55:
        event_state, score = "style_rotation", max(score, 62)
        signals.append("narrow_market_advance")

    quality = _quality(
        expected=expected_proxies + expected_sectors,
        observed=len(proxies) + len(valid_sectors),
        timestamp_ok=timestamp_fresh,
    )
    if quality["status"] != "complete":
        score = min(score, 69)
    confidence = "high" if quality["coverage"] >= 0.95 else "medium" if quality["coverage"] >= 0.7 else "low"

    metrics = {
        "proxy_median_pct": market_pct,
        "median_low_rebound_pct": rebound,
        "sector_up_ratio": breadth,
        "sector_up_count": sum(value > 0 for value in valid_sectors),
        "sector_count": len(valid_sectors),
        "main_flow_latest": flow_latest,
        "main_flow_recovery": flow_recovery,
        "trend_state": state,
        "event_state": event_state,
    }
    evidence = []
    if market_pct is not None:
        evidence.append(f"核心宽基中位涨跌幅 {market_pct:+.2f}%")
    if rebound is not None:
        evidence.append(f"核心宽基从日内低点中位反弹 {rebound:.2f}%")
    if breadth is not None:
        evidence.append(f"行业上涨比例 {breadth * 100:.1f}%（{metrics['sector_up_count']}/{metrics['sector_count']}）")
    if flow_recovery is not None:
        evidence.append(f"主力净流入较日内低点改善 {flow_recovery / 100_000_000:.2f} 亿元")

    trend_descriptions = {
        "strong_uptrend": "市场处于强上涨趋势",
        "uptrend": "市场处于上涨趋势",
        "range": "市场处于震荡状态",
        "downtrend": "市场处于下跌趋势",
        "strong_downtrend": "市场处于强下跌趋势",
    }
    event_descriptions = {
        "selloff": "盘中仍有急跌压力",
        "reversal_watch": "同时出现止跌回升迹象，进入反转观察",
        "reversal_confirmed": "盘中反转已获得价格、行业广度与资金变化共同确认",
        "broad_risk_on": "宽基与行业广度同步转强",
        "style_rotation": "但行业扩散不足，更接近结构性轮动",
        "none": "暂未触发额外的盘中事件",
    }
    return {
        "as_of": as_of,
        "scope_type": "market",
        "scope_code": "CN_A_SHARE",
        "scope_name": "A股市场",
        "state": state,
        "score": round(max(0, min(score, 100)), 1),
        "confidence": confidence,
        "conclusion": f"{trend_descriptions[state]}；{event_descriptions[event_state]}。",
        "metrics": metrics,
        "signals": signals,
        "evidence": evidence,
        "data_quality": quality,
        "rule_version": RULE_VERSION,
    }


def analyze_instrument(
    *,
    as_of: datetime,
    row: Mapping[str, Any],
    market: Mapping[str, Any],
    scope_type: str,
) -> dict:
    pct = _number(row.get("pct_chg"))
    if pct is None:
        pct = _pct(row.get("last") or row.get("close"), row.get("previous_close"))
    rebound = _pct(row.get("last") or row.get("close"), row.get("low"))
    market_pct = _number(market.get("metrics", {}).get("proxy_median_pct")) or 0.0
    relative = pct - market_pct if pct is not None else None
    if pct is not None and pct >= 4:
        state, score = "strong_uptrend", 86.0
    elif pct is not None and pct >= 1:
        state, score = "uptrend", 70.0
    elif pct is not None and pct <= -4:
        state, score = "strong_downtrend", 86.0
    elif pct is not None and pct <= -1:
        state, score = "downtrend", 70.0
    else:
        state, score = "range", 50.0
    signals = []
    event_state = "none"
    if relative is not None and relative >= 2:
        event_state, score = "relative_strength", max(score, 72 + min(relative * 3, 15))
        signals.append("relative_strength")
    elif relative is not None and relative <= -2:
        event_state, score = "relative_weakness", max(score, 72 + min(abs(relative) * 3, 15))
        signals.append("relative_weakness")
    if rebound is not None and rebound >= 3 and pct is not None and pct > 0:
        event_state, score = "leading_reversal", max(score, 82)
        signals.append("leading_reversal")
    if row.get("limit_status") in {"DOWN", "LIMIT_DOWN"}:
        state, event_state, score, signals = "strong_downtrend", "risk_alert", 95, ["limit_down_risk"]
    quality = _quality(expected=1, observed=1 if pct is not None else 0)
    name = str(row.get("name") or row.get("symbol") or "未知标的")
    trend_text = {
        "strong_uptrend": "强上涨", "uptrend": "上涨", "range": "震荡",
        "downtrend": "下跌", "strong_downtrend": "强下跌",
    }[state]
    event_text = {
        "relative_strength": "，并且明显强于市场",
        "relative_weakness": "，并且明显弱于市场",
        "leading_reversal": "，同时形成领先反转",
        "risk_alert": "，并触发交易风险提示",
        "none": "",
    }[event_state]
    conclusion = f"{name}处于{trend_text}状态{event_text}。"
    return {
        "as_of": as_of,
        "scope_type": scope_type,
        "scope_code": str(row.get("symbol")),
        "scope_name": name,
        "state": state,
        "score": round(max(0, min(score, 100)), 1),
        "confidence": "high" if quality["status"] == "complete" else "low",
        "conclusion": conclusion,
        "metrics": {"pct_chg": pct, "low_rebound_pct": rebound, "relative_strength_pct": relative, "trend_state": state, "event_state": event_state},
        "signals": signals,
        "evidence": [
            f"当日涨跌幅 {pct:+.2f}%" if pct is not None else "缺少有效涨跌幅",
            f"相对市场 {relative:+.2f}%" if relative is not None else "无法计算相对强弱",
        ],
        "data_quality": quality,
        "rule_version": RULE_VERSION,
    }
