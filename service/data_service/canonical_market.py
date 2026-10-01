"""Canonical DB-first market data with bounded quota-source fallback."""

from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal, InvalidOperation
import re
from typing import Any

from service.data_service.models import InvalidQueryError, UpstreamFallbackError
from service.source_connectors.contracts import AcquisitionMode, ConnectorRequest
from service.source_connectors.financial_data_protocol import tabular_rows


_SECURITY_CODE = re.compile(r"^(\d{6})\.(SH|SZ|BJ)$")
_KLINE_ROUTE = "/api/v1/quote/kline-batch"
_TRADING_DAY_ROUTE = "/api/v1/common/trading-day"


def _number(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(Decimal(str(value)))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise UpstreamFallbackError(f"invalid numeric market value: {value!r}") from exc


def _iso_date(value: Any) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    for pattern in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%Y%m%d"):
        try:
            return datetime.strptime(text, pattern).date()
        except ValueError:
            continue
    raise UpstreamFallbackError(f"invalid market date: {value!r}")


def _pct_change(close: float | None, previous_close: float | None) -> float | None:
    if close is None or previous_close in (None, 0):
        return None
    return (close / previous_close - 1.0) * 100.0


class CanonicalMarketDataService:
    def __init__(self, data_service, query_broker):
        self._data = data_service
        self._broker = query_broker

    def _financial_rows(self, *, payload: dict, route: str) -> list[dict[str, Any]]:
        try:
            result = self._broker.query(ConnectorRequest(
                source_id="financial_data",
                endpoint_key="common_query",
                acquisition_mode=AcquisitionMode.QUERY_THROUGH,
                parameters=payload,
            ))
            if result.status != "complete" or not result.records:
                raise UpstreamFallbackError(
                    f"financial-data canonical fallback failed for {route}"
                )
            return tabular_rows(result.records[0], route=route)
        except UpstreamFallbackError:
            raise
        except Exception as exc:
            raise UpstreamFallbackError(
                f"financial-data canonical fallback failed for {route}: "
                f"{type(exc).__name__}"
            ) from exc

    @staticmethod
    def _validate_range(start_date: date, end_date: date) -> None:
        if start_date > end_date:
            raise InvalidQueryError("start_date must not be later than end_date")
        if (end_date - start_date).days > 365:
            raise InvalidQueryError("canonical market queries are limited to 366 days")

    @staticmethod
    def _validate_symbols(symbols: list[str]) -> list[str]:
        normalized = list(dict.fromkeys(symbol.strip().upper() for symbol in symbols))
        if not normalized or len(normalized) > 10:
            raise InvalidQueryError("symbols must contain between 1 and 10 values")
        invalid = []
        for symbol in normalized:
            match = _SECURITY_CODE.fullmatch(symbol)
            if not match:
                invalid.append(symbol)
                continue
            code, exchange = match.groups()
            if not (
                (exchange == "SH" and code.startswith("6"))
                or (exchange == "SZ" and code.startswith(("0", "3")))
                or (exchange == "BJ" and code.startswith(("4", "8", "9")))
            ):
                invalid.append(symbol)
        if invalid:
            raise InvalidQueryError(
                "phase-two canonical bars currently support A-share symbols only: "
                + ", ".join(invalid)
            )
        return normalized

    @staticmethod
    def _local_bar(row: dict[str, Any]) -> dict[str, Any]:
        close = _number(row.get("close"))
        previous_close = _number(row.get("pre_close"))
        volume_lots = _number(row.get("vol"))
        amount_thousand_cny = _number(row.get("amount"))
        return {
            "instrument_id": row.get("ts_code"),
            "asset_type": "stock",
            "period": "day",
            "period_start": _iso_date(row.get("trade_date")),
            "period_end": _iso_date(row.get("trade_date")),
            "adjustment": "none",
            "currency": "CNY",
            "open": _number(row.get("open")),
            "high": _number(row.get("high")),
            "low": _number(row.get("low")),
            "close": close,
            "previous_close": previous_close,
            "change": _number(row.get("change")),
            "return_pct": _number(row.get("pct_chg")),
            # Tushare A-share daily: vol=lots (100 shares), amount=thousand CNY.
            "volume": volume_lots * 100.0 if volume_lots is not None else None,
            "volume_unit": "share",
            "amount": (
                amount_thousand_cny * 1000.0
                if amount_thousand_cny is not None else None
            ),
            "amount_unit": "CNY",
            "source_id": "tushare",
            "source_dataset": "stock_daily",
        }

    @staticmethod
    def _financial_bar(row: dict[str, Any]) -> dict[str, Any]:
        if row.get("period") != "P_Day1" or row.get("adj_type") != "S_Unsplit":
            raise UpstreamFallbackError(
                "financial-data returned an unexpected period or adjustment"
            )
        close = _number(row.get("close"))
        previous_close = _number(row.get("previous_close"))
        return {
            "instrument_id": row.get("symbol"),
            "asset_type": "stock",
            "period": "day",
            "period_start": _iso_date(row.get("begin_date")),
            "period_end": _iso_date(row.get("date")),
            "adjustment": "none",
            "currency": "CNY",
            "open": _number(row.get("open")),
            "high": _number(row.get("high")),
            "low": _number(row.get("low")),
            "close": close,
            "previous_close": previous_close,
            "change": (
                close - previous_close
                if close is not None and previous_close is not None else None
            ),
            "return_pct": _pct_change(close, previous_close),
            # The Financial Data contract returns shares and CNY for A shares.
            "volume": _number(row.get("volume")),
            "volume_unit": "share",
            "amount": _number(row.get("amount")),
            "amount_unit": "CNY",
            "source_id": "financial_data",
            "source_dataset": _KLINE_ROUTE,
        }

    def daily_bars(
        self,
        *,
        symbols: list[str],
        start_date: date,
        end_date: date,
        allow_quota_fallback: bool = True,
    ) -> dict:
        self._validate_range(start_date, end_date)
        normalized = self._validate_symbols(symbols)
        records_by_key: dict[tuple[str, date], dict[str, Any]] = {}
        missing: list[str] = []
        coverage: dict[str, dict[str, int]] = {}
        calendar_response = self._data.query_dataset(
            "trade_calendar",
            exact_filters={"exchange": "SSE", "is_open": "1"},
            date_value=None,
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
            limit=400,
            offset=0,
            include_total=False,
        )
        expected_days = {
            _iso_date(row["cal_date"]) for row in calendar_response["data"]
        }
        for symbol in normalized:
            response = self._data.query_dataset(
                "stock_daily",
                exact_filters={"ts_code": symbol},
                date_value=None,
                start_date=start_date.isoformat(),
                end_date=end_date.isoformat(),
                limit=400,
                offset=0,
                include_total=False,
            )
            local_rows = response["data"]
            coverage[symbol] = {"local_rows": len(local_rows), "fallback_rows": 0}
            local_dates = set()
            for row in local_rows:
                bar = self._local_bar(row)
                local_dates.add(bar["period_end"])
                records_by_key[(symbol, bar["period_end"])] = bar
            # When the local calendar is available, fill missing open sessions.
            # Without calendar evidence, only an entirely empty local slice may
            # trigger quota fallback.
            if (expected_days and expected_days - local_dates) or not local_rows:
                missing.append(symbol)

        fallback_used = bool(missing and allow_quota_fallback)
        if fallback_used:
            payload = {
                "mode": "data",
                "requests": [{
                    "url": _KLINE_ROUTE,
                    "params": {
                        "symbols": missing,
                        "period": "P_Day1",
                        "split": "S_Unsplit",
                        "start_date": datetime.combine(start_date, time.min).strftime(
                            "%Y-%m-%d %H:%M:%S"
                        ),
                        "end_date": datetime.combine(end_date, time.max).strftime(
                            "%Y-%m-%d %H:%M:%S"
                        ),
                        "count": 400,
                    },
                }],
            }
            decoded = self._financial_rows(payload=payload, route=_KLINE_ROUTE)
            allowed = set(missing)
            for row in decoded:
                symbol = str(row.get("symbol") or "")
                if symbol not in allowed:
                    raise UpstreamFallbackError(
                        f"financial-data returned unrequested symbol: {symbol}"
                    )
                bar = self._financial_bar(row)
                # Existing scheduled data remains authoritative. The quota
                # source fills holes; it never overwrites a local DB row.
                records_by_key.setdefault((symbol, bar["period_end"]), bar)
                coverage[symbol]["fallback_rows"] += 1

        records = list(records_by_key.values())
        records.sort(key=lambda row: (row["instrument_id"], row["period_end"]))
        unresolved_open_dates = {
            symbol: sorted(
                day for day in expected_days
                if (symbol, day) not in records_by_key
            )
            for symbol in normalized
        }
        return {
            "data": records,
            "meta": {
                "contract": "canonical_market_bar.v1",
                "read_strategy": "local_db_first",
                "fallback_policy": (
                    "quota_if_local_empty" if allow_quota_fallback else "none"
                ),
                "fallback_used": fallback_used,
                "fallback_symbols": missing if fallback_used else [],
                "unresolved_symbols": [
                    symbol for symbol in missing
                    if coverage[symbol]["fallback_rows"] == 0
                ],
                "unresolved_open_dates": unresolved_open_dates,
                "coverage": coverage,
                "returned": len(records),
            },
        }

    def trading_days(
        self,
        *,
        symbol: str,
        start_date: date,
        end_date: date,
        allow_quota_fallback: bool = True,
    ) -> dict:
        self._validate_range(start_date, end_date)
        normalized_symbol = self._validate_symbols([symbol])[0]
        response = self._data.query_dataset(
            "trade_calendar",
            exact_filters={"exchange": "SSE", "is_open": "1"},
            date_value=None,
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
            limit=400,
            offset=0,
            include_total=False,
        )
        local_days = sorted({_iso_date(row["cal_date"]) for row in response["data"]})
        fallback_used = not local_days and allow_quota_fallback
        source_id = "tushare"
        days = local_days
        if fallback_used:
            payload = {
                "mode": "data",
                "requests": [{
                    "url": _TRADING_DAY_ROUTE,
                    "params": {
                        "symbols": [normalized_symbol],
                        "start_date": f"{start_date.isoformat()} 00:00:00",
                        "end_date": f"{end_date.isoformat()} 23:59:59",
                        "count": 0,
                        "reversed_order": False,
                    },
                }],
            }
            decoded = self._financial_rows(payload=payload, route=_TRADING_DAY_ROUTE)
            if len(decoded) != 1 or decoded[0].get("symbol") != normalized_symbol:
                raise UpstreamFallbackError("financial-data calendar symbol mismatch")
            raw_days = decoded[0].get("trading_days")
            if not isinstance(raw_days, list):
                raise UpstreamFallbackError("financial-data trading_days must be a list")
            days = sorted({_iso_date(item) for item in raw_days})
            source_id = "financial_data"

        return {
            "data": [{
                "market": "A_SHARE",
                "session_date": day,
                "is_open": True,
                "time_zone": "Asia/Shanghai",
                "source_id": source_id,
            } for day in days],
            "meta": {
                "contract": "canonical_trading_session.v1",
                "read_strategy": "local_db_first",
                "fallback_policy": (
                    "quota_if_local_empty" if allow_quota_fallback else "none"
                ),
                "fallback_used": fallback_used,
                "returned": len(days),
            },
        }
