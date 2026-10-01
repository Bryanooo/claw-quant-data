"""Canonical DB-first index profiles and weighted constituents."""

from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal, InvalidOperation
import re
from typing import Any

from service.data_service.models import InvalidQueryError, UpstreamFallbackError
from service.source_connectors.contracts import AcquisitionMode, ConnectorRequest
from service.source_connectors.financial_data_protocol import tabular_rows


_INDEX = re.compile(r"^[0-9A-Z]{6,10}\.(SH|SZ)$")
_PROFILE_ROUTE = "/api/v1/index_fnd/index-profile-basic-info"
_CONSTITUENTS_ROUTE = "/api/v1/index_fnd/index-constituents-list-weight"


def _number(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(Decimal(str(value)))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise UpstreamFallbackError(f"invalid numeric index value: {value!r}") from exc


def _date(value: Any) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    for pattern in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%Y%m%d"):
        try:
            return datetime.strptime(str(value).strip(), pattern).date()
        except ValueError:
            continue
    raise UpstreamFallbackError(f"invalid index date: {value!r}")


class CanonicalIndexDataService:
    def __init__(self, data_service, query_broker):
        self._data = data_service
        self._broker = query_broker

    @staticmethod
    def _symbols(symbols: list[str]) -> list[str]:
        values = list(dict.fromkeys(str(item).strip().upper() for item in symbols))
        if not values or len(values) > 10:
            raise InvalidQueryError("symbols must contain between 1 and 10 values")
        invalid = [item for item in values if not _INDEX.fullmatch(item)]
        if invalid:
            raise InvalidQueryError("canonical index fallback supports SH/SZ index symbols only")
        return values

    def _provider(self, route: str, params: dict) -> list[dict[str, Any]]:
        try:
            result = self._broker.query(ConnectorRequest(
                source_id="financial_data", endpoint_key="common_query",
                acquisition_mode=AcquisitionMode.QUERY_THROUGH,
                parameters={"mode": "data", "requests": [{"url": route, "params": params}]},
            ))
            if result.status != "complete" or not result.records:
                raise UpstreamFallbackError(f"financial-data canonical fallback failed for {route}")
            return tabular_rows(result.records[0], route=route)
        except UpstreamFallbackError:
            raise
        except Exception as exc:
            raise UpstreamFallbackError(
                f"financial-data canonical fallback failed for {route}: {type(exc).__name__}"
            ) from exc

    def profiles(self, *, symbols: list[str], allow_quota_fallback: bool = True) -> dict:
        normalized = self._symbols(symbols)
        records: dict[str, dict[str, Any]] = {}
        missing = []
        for symbol in normalized:
            response = self._data.query_dataset(
                "index_basic", exact_filters={"ts_code": symbol},
                date_value=None, start_date=None, end_date=None,
                limit=2, offset=0, include_total=False,
            )
            if response["data"]:
                row = response["data"][0]
                records[symbol] = {
                    "index_id": symbol, "name": row.get("name"),
                    "full_name": None, "market": row.get("market"),
                    "publisher": row.get("publisher"),
                    "category": row.get("category"),
                    "publication_date": _date(row.get("list_date")),
                    "base_date": _date(row.get("base_date")),
                    "base_point": _number(row.get("base_point")),
                    "currency": "CNY", "description": None,
                    "source_id": "tushare", "source_dataset": "index_basic",
                }
            else:
                missing.append(symbol)
        if allow_quota_fallback and missing:
            fields = [
                "symbol", "short_name_zh", "cn_full_name", "main_compiler",
                "pub_org", "publish_date", "base_date", "base_point",
                "currency", "index_introd",
            ]
            for row in self._provider(_PROFILE_ROUTE, {"symbols": missing, "fields": fields}):
                symbol = str(row.get("symbol") or "")
                if symbol not in missing:
                    raise UpstreamFallbackError("financial-data returned unrequested index")
                records[symbol] = {
                    "index_id": symbol, "name": row.get("short_name_zh"),
                    "full_name": row.get("cn_full_name"), "market": None,
                    "publisher": row.get("pub_org") or row.get("main_compiler"),
                    "category": None,
                    "publication_date": _date(row.get("publish_date")),
                    "base_date": _date(row.get("base_date")),
                    "base_point": _number(row.get("base_point")),
                    "currency": row.get("currency") or "CNY",
                    "description": row.get("index_introd"),
                    "source_id": "financial_data", "source_dataset": _PROFILE_ROUTE,
                }
        data = [records[item] for item in normalized if item in records]
        return {
            "data": data,
            "meta": {
                "contract": "canonical_index_profile.v1",
                "read_strategy": "local_db_first",
                "fallback_used": bool(missing and allow_quota_fallback),
                "unresolved_symbols": [item for item in normalized if item not in records],
            },
        }

    def constituents(
        self, *, symbols: list[str], update_dates: list[date],
        allow_quota_fallback: bool = True,
    ) -> dict:
        normalized = self._symbols(symbols)
        dates = sorted(set(update_dates))
        if not dates or len(dates) > 20:
            raise InvalidQueryError("update_dates must contain between 1 and 20 values")
        requested = set(dates)
        records = []
        local_coverage = set()
        for symbol in normalized:
            response = self._data.query_dataset(
                "index_weight", exact_filters={"index_code": symbol},
                date_value=None, start_date=dates[0].isoformat(),
                end_date=dates[-1].isoformat(), limit=1000, offset=0,
                include_total=False,
            )
            for row in response["data"]:
                update_date = _date(row.get("trade_date"))
                if update_date not in requested:
                    continue
                local_coverage.add((symbol, update_date))
                records.append({
                    "index_id": symbol, "update_date": update_date,
                    "instrument_id": row.get("con_code"),
                    "instrument_name": None, "weight_pct": _number(row.get("weight")),
                    "source_id": "tushare", "source_dataset": "index_weight",
                })
        missing_symbols = [
            symbol for symbol in normalized
            if any((symbol, day) not in local_coverage for day in dates)
        ]
        if allow_quota_fallback and missing_symbols:
            fields = ["symbol", "update_date", "stock_symbol", "sec_name", "weight"]
            rows = self._provider(_CONSTITUENTS_ROUTE, {
                "symbols": missing_symbols,
                "start_date": datetime.combine(dates[0], time.min).strftime("%Y-%m-%d %H:%M:%S"),
                "end_date": datetime.combine(dates[-1], time.max).strftime("%Y-%m-%d %H:%M:%S"),
                "fields": fields,
            })
            for row in rows:
                symbol = str(row.get("symbol") or "")
                update_date = _date(row.get("update_date"))
                if symbol not in missing_symbols or update_date not in requested:
                    raise UpstreamFallbackError("financial-data returned index data outside request")
                if (symbol, update_date) in local_coverage:
                    continue
                records.append({
                    "index_id": symbol, "update_date": update_date,
                    "instrument_id": row.get("stock_symbol"),
                    "instrument_name": row.get("sec_name"),
                    "weight_pct": _number(row.get("weight")),
                    "source_id": "financial_data", "source_dataset": _CONSTITUENTS_ROUTE,
                })
        records.sort(key=lambda item: (item["index_id"], item["update_date"], -(item["weight_pct"] or 0)))
        returned = {(item["index_id"], item["update_date"]) for item in records}
        return {
            "data": records,
            "meta": {
                "contract": "canonical_index_constituent.v1",
                "read_strategy": "local_db_first_by_index_date",
                "fallback_used": bool(missing_symbols and allow_quota_fallback),
                "unresolved": [
                    {"index_id": symbol, "update_date": day}
                    for symbol in normalized for day in dates
                    if (symbol, day) not in returned
                ],
            },
        }
