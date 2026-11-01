"""Historical intraday replay from durable or freshly fetched minute facts."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from typing import Any

from service.intraday.analyzer import analyze_instrument, analyze_market
from service.intraday.collector import INDEX_PROXIES, PROXIES


CST = timezone(timedelta(hours=8))
CHECKPOINTS = (time(10, 30), time(11, 30), time(13, 30), time(15, 0))


def _number(value: Any) -> float | None:
    try:
        return float(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _as_snapshot(rows: list[dict], as_of: datetime) -> dict | None:
    available = sorted((row for row in rows if row["bar_time"] <= as_of), key=lambda row: row["bar_time"])
    if not available:
        return None
    first, latest = available[0], available[-1]
    highs = [_number(row.get("high")) for row in available]
    lows = [_number(row.get("low")) for row in available]
    volumes = [_number(row.get("volume")) for row in available]
    amounts = [_number(row.get("amount")) for row in available]
    return {
        "symbol": latest["symbol"], "name": latest.get("name"),
        "open": first.get("open"), "high": max(value for value in highs if value is not None),
        "low": min(value for value in lows if value is not None), "last": latest.get("close"),
        "close": latest.get("close"), "previous_close": first.get("previous_close"),
        "volume": sum(value for value in volumes if value is not None),
        "amount": sum(value for value in amounts if value is not None),
    }


def replay_day(batch: dict) -> list[dict]:
    grouped: dict[str, list[dict]] = {}
    for row in batch["quote_rows"]:
        grouped.setdefault(row["symbol"], []).append(row)
    results: list[dict] = []
    day: date = batch["day"]
    for checkpoint in CHECKPOINTS:
        as_of = datetime.combine(day, checkpoint, tzinfo=CST)
        snapshots = {
            symbol: snapshot
            for symbol, rows in grouped.items()
            if (snapshot := _as_snapshot(rows, as_of)) is not None
        }
        proxies = [snapshots[symbol] for symbol in PROXIES if symbol in snapshots]
        sectors = [
            snapshots[symbol] for symbol in batch["industry_symbols"]
            if symbol in snapshots
        ]
        # Provider rows are in chronological order for this route in current
        # contract; filter using the already normalized durable copy.
        normalized_flows = [
            raw for raw, saved in zip(batch["flow_source"], batch["flow_rows"])
            if saved["snapshot_time"] <= as_of
        ]
        market = analyze_market(
            as_of=as_of, proxies=proxies, sectors=sectors,
            flows=normalized_flows, expected_proxies=batch["expected_proxies"],
            expected_sectors=batch["expected_sectors"], timestamp_fresh=True,
        )
        analyses = [market]
        for symbol in PROXIES:
            if symbol in snapshots:
                analyses.append(analyze_instrument(as_of=as_of, row=snapshots[symbol], market=market, scope_type="etf"))
        for symbol in INDEX_PROXIES:
            if symbol in snapshots:
                analyses.append(analyze_instrument(as_of=as_of, row=snapshots[symbol], market=market, scope_type="index"))
        for symbol in batch["watch_symbols"]:
            if symbol in snapshots:
                analyses.append(analyze_instrument(as_of=as_of, row=snapshots[symbol], market=market, scope_type="stock"))
        results.append({"as_of": as_of, "analyses": analyses})
    return results
