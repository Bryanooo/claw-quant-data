"""Quota-aware batch collector for the five-minute observation loop."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import time
from typing import Any, Mapping

from service.source_connectors import SOURCE_CONNECTORS
from service.source_connectors.contracts import AcquisitionMode, ConnectorRequest
from service.source_connectors.financial_data import FinancialDataConnector, FinancialDataProtocolError
from service.source_connectors.ant_budget import budget_scope, ORIGIN


CST = timezone(timedelta(hours=8))
PROXIES = {
    "510300.SH": "沪深300ETF",
    "512100.SH": "中证1000ETF",
    "588000.SH": "科创50ETF",
    "159915.SZ": "创业板ETF",
}
INDEX_PROXIES = {
    # The Ant minute route currently returns 399001.SZ as provider alias
    # 2A01.SZ.  Shanghai index codes were probed and returned no rows, so they
    # are deliberately excluded instead of wasting quota on every backfill.
    "399001.SZ": "深证成指",
    "399006.SZ": "创业板指",
}
SYMBOL_ALIASES = {"2A01.SZ": "399001.SZ"}


def _chunks(items: list[str], size: int) -> list[list[str]]:
    return [items[index:index + size] for index in range(0, len(items), size)]


def _decode_item(item: Mapping[str, Any], route: str) -> list[dict]:
    if item.get("url") != route:
        raise FinancialDataProtocolError(
            f"financial-data result order drift: expected {route}, got {item.get('url')}"
        )
    meta, data = item.get("meta"), item.get("data")
    fields = meta.get("fields") if isinstance(meta, Mapping) else None
    if fields == [] and data == []:
        return []
    if not isinstance(fields, list) or not isinstance(data, list):
        raise FinancialDataProtocolError("financial-data tabular result is invalid")
    rows = []
    for raw in data:
        if isinstance(raw, Mapping):
            rows.append({field: raw.get(field) for field in fields})
        elif isinstance(raw, list) and len(raw) == len(fields):
            rows.append(dict(zip(fields, raw, strict=True)))
        else:
            raise FinancialDataProtocolError("financial-data row width is invalid")
    return rows


def _parse_time(value: Any, fallback: datetime) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=CST)
    if value:
        text = str(value).strip().replace("T", " ")
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y%m%d %H:%M:%S", "%Y-%m-%d %H:%M"):
            try:
                return datetime.strptime(text[:19], fmt).replace(tzinfo=CST)
            except ValueError:
                continue
    return fallback


def _scope(
    symbol: str,
    watch_symbols: set[str],
    industry_symbols: set[str],
    index_symbols: set[str],
) -> str:
    if symbol in watch_symbols:
        return "stock"
    if symbol in industry_symbols:
        return "industry"
    if symbol in index_symbols:
        return "index"
    return "etf"


class AntIntradayCollector:
    def __init__(
        self,
        connector: FinancialDataConnector | None = None,
        *,
        minimum_call_interval_seconds: float = 0.0,
    ):
        # Use the registered connector so common-query audit evidence follows
        # the same governed path as every other Ant request.
        self._connector = connector or SOURCE_CONNECTORS.get("financial_data")
        self._industry_cache: tuple[datetime, list[dict]] | None = None
        self._minimum_call_interval_seconds = max(0.0, minimum_call_interval_seconds)
        self._last_call_started_at: float | None = None
        self.usage = {"outer_calls": 0, "subrequests": 0, "fetched_rows": 0}

    def _call(self, tagged_requests: list[tuple[str, str, dict]]) -> dict[str, list[dict]]:
        if self._last_call_started_at is not None:
            remaining = (
                self._minimum_call_interval_seconds
                - (time.monotonic() - self._last_call_started_at)
            )
            if remaining > 0:
                time.sleep(remaining)
        self._last_call_started_at = time.monotonic()
        payload = {
            "mode": "data",
            "requests": [
                {"url": route, "params": params}
                for _, route, params in tagged_requests
            ],
        }
        self.usage["outer_calls"] += 1
        self.usage["subrequests"] += len(tagged_requests)
        with budget_scope(getattr(self, '_budget_category', ORIGIN.get())):
            result = self._connector.query(
                ConnectorRequest(
                    source_id="financial_data",
                    endpoint_key="common_query",
                    acquisition_mode=AcquisitionMode.QUERY_THROUGH,
                    parameters=payload,
                )
            )
        response = result.records[0]
        results = response.get("results") if isinstance(response, Mapping) else None
        if response.get("status") != "SUCCESS" or not isinstance(results, list):
            raise FinancialDataProtocolError("financial-data intraday batch failed")
        if len(results) != len(tagged_requests):
            raise FinancialDataProtocolError(
                f"financial-data returned {len(results)} results for {len(tagged_requests)} requests"
            )
        decoded: dict[str, list[dict]] = {}
        for (tag, route, _), item in zip(tagged_requests, results, strict=True):
            rows = _decode_item(item, route)
            decoded[tag] = rows
            self.usage["fetched_rows"] += len(rows)
        return decoded

    def _industries(self, now: datetime) -> list[dict]:
        if self._industry_cache and now - self._industry_cache[0] < timedelta(days=1):
            return self._industry_cache[1]
        result = self._call([(
            "industries", "/api/v1/sector/plate-list",
            {"plate_type": "plate_industry"},
        )])
        rows = [row for row in result["industries"] if row.get("sub_type") == "LEVEL1"]
        self._industry_cache = (now, rows)
        return rows

    def collect(self, *, now: datetime, watchlist: list[dict]) -> dict:
        self._budget_category = 'intraday'
        now = now.astimezone(CST)
        clock = now.time()
        if clock > datetime.strptime("15:00", "%H:%M").time():
            market_end = now.replace(hour=15, minute=0, second=0, microsecond=0)
        elif datetime.strptime("11:30", "%H:%M").time() < clock < datetime.strptime("13:00", "%H:%M").time():
            market_end = now.replace(hour=11, minute=30, second=0, microsecond=0)
        else:
            market_end = now
        industries = self._industries(now)
        industry_names = {
            str(row.get("plate_code")): str(row.get("plate_name"))
            for row in industries if row.get("plate_code")
        }
        industry_symbols = set(industry_names)
        watch_names = {str(row["symbol"]): str(row.get("name") or row["symbol"]) for row in watchlist}
        watch_symbols = set(watch_names)
        index_symbols = set(INDEX_PROXIES)
        quote_symbols = list(PROXIES) + list(INDEX_PROXIES) + sorted(watch_symbols) + sorted(industry_symbols)
        bar_symbols = list(PROXIES) + list(INDEX_PROXIES) + sorted(watch_symbols)
        start = (market_end - timedelta(minutes=20)).strftime("%Y-%m-%d %H:%M:%S")
        end = market_end.strftime("%Y-%m-%d %H:%M:%S")
        requests: list[tuple[str, str, dict]] = [(
            "snapshots", "/api/v1/quote/basic-snapshot", {"symbols": quote_symbols}
        )]
        for index, symbols in enumerate(_chunks(bar_symbols, 10)):
            requests.append((
                f"bars:{index}", "/api/v1/quote/kline-batch",
                {
                    "symbols": symbols, "period": "P_Min1", "split": "S_Unsplit",
                    "start_date": start, "end_date": end, "count": 20,
                },
            ))
        requests.extend([
            (
                "flow:399006.SZ", "/api/v1/quote/capital-flow-range",
                {"symbol": "399006.SZ", "period": "P_Min1", "start_date": now.strftime("%Y-%m-%d 09:25:00"), "end_date": end, "count": 300},
            ),
        ])
        decoded = self._call(requests)
        snapshots = decoded.pop("snapshots")
        # Daily ranked data stays in ant_norm_hot_plate_rank; do not imply
        # that yesterday's ranking is a realtime observation.
        hot = []
        for row in snapshots:
            original = str(row.get("symbol") or "")
            row["symbol"] = SYMBOL_ALIASES.get(original, original)
            symbol = row["symbol"]
            row["name"] = row.get("name") or PROXIES.get(symbol) or INDEX_PROXIES.get(symbol) or watch_names.get(symbol) or industry_names.get(symbol)
        returned = {str(row.get("symbol")) for row in snapshots}
        missing = sorted(set(quote_symbols) - returned)
        as_of = max(
            (_parse_time(row.get("latest_trade_time"), now) for row in snapshots),
            default=now,
        )
        # During continuous trading the business timestamp should trail the
        # collector by no more than one five-minute slot plus arrival grace.
        # At lunch and after close, the last session timestamp is expected.
        if clock < datetime.strptime("09:30", "%H:%M").time():
            timestamp_fresh = as_of.date() == now.date()
        elif clock <= datetime.strptime("11:30", "%H:%M").time() or datetime.strptime("13:00", "%H:%M").time() <= clock <= datetime.strptime("15:00", "%H:%M").time():
            timestamp_fresh = timedelta(0) <= now - as_of <= timedelta(minutes=7)
        elif clock < datetime.strptime("13:00", "%H:%M").time():
            timestamp_fresh = as_of.date() == now.date() and as_of.time() >= datetime.strptime("11:29", "%H:%M").time()
        else:
            timestamp_fresh = as_of.date() == now.date() and as_of.time() >= datetime.strptime("14:59", "%H:%M").time()
        quote_rows = []
        for row in snapshots:
            symbol = str(row.get("symbol"))
            quote_rows.append({
                "symbol": symbol,
                "bar_time": _parse_time(row.get("latest_trade_time"), as_of),
                "period": "snapshot",
                "scope_type": _scope(symbol, watch_symbols, industry_symbols, index_symbols),
                "name": row.get("name"),
                "open": row.get("open"), "high": row.get("high"), "low": row.get("low"),
                "close": row.get("last") or row.get("close"),
                "previous_close": row.get("previous_close"),
                "volume": row.get("volume"), "amount": row.get("amount"),
                "pct_chg": row.get("pct_chg"), "trade_status": row.get("trade_status"),
                "limit_status": row.get("limit_status"), "payload": row,
            })
        for tag, rows in decoded.items():
            if not tag.startswith("bars:"):
                continue
            for row in rows:
                symbol = SYMBOL_ALIASES.get(str(row.get("symbol") or ""), str(row.get("symbol") or ""))
                quote_rows.append({
                    "symbol": symbol, "bar_time": _parse_time(row.get("date"), as_of),
                    "period": str(row.get("period") or "P_Min1"),
                    "scope_type": _scope(symbol, watch_symbols, industry_symbols, index_symbols),
                    "name": PROXIES.get(symbol) or INDEX_PROXIES.get(symbol) or watch_names.get(symbol),
                    "open": row.get("open"), "high": row.get("high"), "low": row.get("low"),
                    "close": row.get("close"), "previous_close": row.get("previous_close"),
                    "volume": row.get("volume"), "amount": row.get("amount"),
                    "pct_chg": None, "trade_status": None, "limit_status": None,
                    "payload": row,
                })
        flow_source = decoded.get("flow:399006.SZ", [])
        flow_rows = [{
            "symbol": str(row.get("symbol") or "399006.SZ"),
            "snapshot_time": _parse_time(row.get("snapshot_date") or row.get("last_trade_time"), as_of),
            "period": str(row.get("period_type") or "P_Min1"),
            "main_in": row.get("main_in"), "main_out": row.get("main_out"),
            "main_net_inflow": row.get("main_net_inflow"),
            "retail_net_in": row.get("retail_net_in"),
            "total_net_in": row.get("total_net_in"), "payload": row,
        } for row in flow_source]
        return {
            "as_of": as_of,
            "snapshots": snapshots,
            "quote_rows": quote_rows,
            "flow_rows": flow_rows,
            "flow_source": flow_source,
            "hot_plates": hot,
            "proxy_symbols": set(PROXIES),
            "index_symbols": index_symbols,
            "industry_symbols": industry_symbols,
            "watch_symbols": watch_symbols,
            "expected_proxies": len(PROXIES),
            "expected_sectors": len(industry_symbols),
            "missing_symbols": missing,
            "timestamp_fresh": timestamp_fresh,
            "usage": dict(self.usage),
        }

    def collect_history_day(self, *, day: date, watchlist: list[dict]) -> dict:
        """Fetch one complete trading day in one batched provider call."""

        return self.collect_history_days(days=[day], watchlist=watchlist)[0]

    def collect_history_days(
        self,
        *,
        days: list[date],
        watchlist: list[dict],
    ) -> list[dict]:
        """Fetch one or two adjacent calendar days in one provider call.

        The P_Min1 route permits at most two natural days.  The provider also
        rejects ``count=600`` with an empty result; 500 safely covers the 484
        session bars for two normal A-share trading days.
        """

        if not days or len(days) > 2:
            raise ValueError("history batch must contain one or two days")
        self._budget_category = 'backfill'
        days = sorted(days)
        if len(days) == 2 and (days[1] - days[0]).days != 1:
            raise ValueError("two-day history batch must use adjacent calendar days")

        usage_before = dict(self.usage)
        anchors = {
            day: datetime.combine(
                day, datetime.strptime("15:00", "%H:%M").time(), tzinfo=CST,
            )
            for day in days
        }
        anchor = anchors[days[-1]]
        # Industry membership is reference data, not a per-day market fact.
        # Reuse it across every day in one backfill job instead of spending a
        # separate provider call on the same 31-code directory each day.
        industries = (
            self._industry_cache[1]
            if self._industry_cache is not None
            else self._industries(anchor)
        )
        industry_names = {
            str(row.get("plate_code")): str(row.get("plate_name"))
            for row in industries if row.get("plate_code")
        }
        industry_symbols = set(industry_names)
        watch_names = {str(row["symbol"]): str(row.get("name") or row["symbol"]) for row in watchlist}
        watch_symbols = set(watch_names)
        index_symbols = set(INDEX_PROXIES)
        symbols = list(PROXIES) + list(INDEX_PROXIES) + sorted(watch_symbols) + sorted(industry_symbols)
        start = f"{days[0].isoformat()} 09:25:00"
        end = f"{days[-1].isoformat()} 15:00:00"
        row_limit = 500 if len(days) == 2 else 300
        requests: list[tuple[str, str, dict]] = []
        for index, group in enumerate(_chunks(symbols, 10)):
            requests.append((
                f"bars:{index}", "/api/v1/quote/kline-batch",
                {
                    "symbols": group, "period": "P_Min1", "split": "S_Unsplit",
                    "start_date": start, "end_date": end, "count": row_limit,
                },
            ))
        requests.append((
            "flow:399006.SZ", "/api/v1/quote/capital-flow-range",
            {"symbol": "399006.SZ", "period": "P_Min1", "start_date": start, "end_date": end, "count": row_limit},
        ))
        decoded = self._call(requests)
        quote_rows_by_day: dict[date, list[dict]] = {day: [] for day in days}
        returned_by_day: dict[date, set[str]] = {day: set() for day in days}
        for tag, rows in decoded.items():
            if not tag.startswith("bars:"):
                continue
            for row in rows:
                raw_symbol = str(row.get("symbol") or "")
                symbol = SYMBOL_ALIASES.get(raw_symbol, raw_symbol)
                bar_time = _parse_time(row.get("date"), anchor)
                row_day = bar_time.astimezone(CST).date()
                if row_day not in quote_rows_by_day:
                    continue
                returned_by_day[row_day].add(symbol)
                quote_rows_by_day[row_day].append({
                    "symbol": symbol, "bar_time": bar_time,
                    "period": str(row.get("period") or "P_Min1"),
                    "scope_type": _scope(symbol, watch_symbols, industry_symbols, index_symbols),
                    "name": PROXIES.get(symbol) or INDEX_PROXIES.get(symbol) or watch_names.get(symbol) or industry_names.get(symbol),
                    "open": row.get("open"), "high": row.get("high"), "low": row.get("low"),
                    "close": row.get("close"), "previous_close": row.get("previous_close"),
                    "volume": row.get("volume"), "amount": row.get("amount"),
                    "pct_chg": None, "trade_status": None, "limit_status": None,
                    "payload": row,
                })
        flow_source_by_day: dict[date, list[dict]] = {day: [] for day in days}
        flow_rows_by_day: dict[date, list[dict]] = {day: [] for day in days}
        for row in decoded.get("flow:399006.SZ", []):
            snapshot_time = _parse_time(
                row.get("snapshot_date") or row.get("last_trade_time"), anchor,
            )
            row_day = snapshot_time.astimezone(CST).date()
            if row_day not in flow_source_by_day:
                continue
            flow_source_by_day[row_day].append(row)
            flow_rows_by_day[row_day].append({
                "symbol": str(row.get("symbol") or "399006.SZ"),
                "snapshot_time": snapshot_time,
                "period": str(row.get("period_type") or "P_Min1"),
                "main_in": row.get("main_in"), "main_out": row.get("main_out"),
                "main_net_inflow": row.get("main_net_inflow"),
                "retail_net_in": row.get("retail_net_in"),
                "total_net_in": row.get("total_net_in"), "payload": row,
            })
        total_usage = {
            key: self.usage[key] - usage_before[key]
            for key in self.usage
        }
        results = []
        for position, day in enumerate(days):
            results.append({
                "day": day, "anchor": anchors[day],
                "quote_rows": quote_rows_by_day[day],
                "flow_rows": flow_rows_by_day[day],
                "flow_source": flow_source_by_day[day],
                "proxy_symbols": set(PROXIES), "index_symbols": index_symbols,
                "industry_symbols": industry_symbols,
                "watch_symbols": watch_symbols, "watch_names": watch_names,
                "expected_proxies": len(PROXIES),
                "expected_sectors": len(industry_symbols),
                "missing_symbols": sorted(set(symbols) - returned_by_day[day]),
                # Attribute the shared provider call to the first persisted
                # day only, so run-ledger totals match actual quota usage.
                "usage": total_usage if position == 0 else {
                    "outer_calls": 0, "subrequests": 0, "fetched_rows": 0,
                },
            })
        return results
