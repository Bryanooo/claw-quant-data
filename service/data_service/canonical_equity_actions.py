"""Canonical DB-first A-share ownership, supply and trading-status events."""

from __future__ import annotations

from datetime import date
from typing import Any

from service.data_service.canonical_equity import CanonicalEquityDataService, _iso_date, _number
from service.data_service.canonical_equity_events import _provider_range
from service.data_service.models import InvalidQueryError, UpstreamFallbackError


_SHAREHOLDER_ROUTE = "/api/v1/stock_fnd/shareholder-list"
_RELEASE_ROUTE = "/api/v1/stock_fnd/restricted-release-calendar"
_PLEDGE_ROUTE = "/api/v1/stock_sh_equity/freeze-pledge"
_RISK_ROUTE = "/api/v1/stock/risk-alerts"
_SUSPEND_ROUTE = "/api/v1/stock/suspend-resumption"


class CanonicalEquityActionService(CanonicalEquityDataService):
    @staticmethod
    def _validate_long_range(start_date: date, end_date: date) -> None:
        if start_date > end_date:
            raise InvalidQueryError("start_date must not be later than end_date")
        if (end_date - start_date).days > 3650:
            raise InvalidQueryError("canonical action queries are limited to 3651 days")

    def _local_range(
        self, dataset: str, symbol: str, start_date: date, end_date: date
    ) -> list[dict[str, Any]]:
        return self._data.query_dataset(
            dataset,
            exact_filters={"ts_code": symbol},
            date_value=None,
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
            limit=1000,
            offset=0,
            include_total=False,
        )["data"]

    def _provider_rows(
        self, *, route: str, symbols: list[str], start_date: date,
        end_date: date, fields: list[str],
    ) -> list[dict[str, Any]]:
        provider_start, provider_end = _provider_range(start_date, end_date)
        return self._financial_rows(
            route=route,
            payload={"mode": "data", "requests": [{
                "url": route,
                "params": {
                    "symbols": symbols,
                    "start_date": provider_start,
                    "end_date": provider_end,
                    "fields": fields,
                },
            }]},
        )

    def shareholders(
        self, *, symbols: list[str], report_dates: list[date],
        allow_quota_fallback: bool = True,
    ) -> dict:
        normalized_symbols = self._validate_symbols(symbols)
        normalized_dates = sorted(set(report_dates))
        if not normalized_dates or len(normalized_dates) > 20:
            raise InvalidQueryError("report_dates must contain between 1 and 20 values")
        requested = set(normalized_dates)
        records: list[dict[str, Any]] = []
        local_coverage: set[tuple[str, date]] = set()
        for symbol in normalized_symbols:
            for dataset, scope in (
                ("top10_holders", "total"),
                ("top10_floatholders", "float"),
            ):
                for row in self._local_range(
                    dataset, symbol, normalized_dates[0], normalized_dates[-1]
                ):
                    report_period = _iso_date(row.get("end_date"))
                    if report_period not in requested:
                        continue
                    local_coverage.add((symbol, report_period))
                    records.append({
                        "instrument_id": symbol,
                        "report_period": report_period,
                        "publication_date": _iso_date(row.get("ann_date")),
                        "scope": scope,
                        "rank": None,
                        "shareholder_name": row.get("holder_name"),
                        "shareholder_type": row.get("holder_type"),
                        "holding_shares": _number(row.get("hold_amount")),
                        "holding_pct_total": _number(row.get("hold_ratio")),
                        "holding_pct_float": _number(row.get("hold_float_ratio")),
                        "holding_change_shares": _number(row.get("hold_change")),
                        "pledged_shares": None,
                        "frozen_shares": None,
                        "source_id": "tushare",
                        "source_dataset": dataset,
                    })
        missing_symbols = [
            symbol for symbol in normalized_symbols
            if any((symbol, period) not in local_coverage for period in normalized_dates)
        ]
        if allow_quota_fallback and missing_symbols:
            fields = [
                "symbol", "end_date", "shareholder_ranking", "shareholder_name",
                "shareholder_type", "total_shares_held", "holding_type",
                "holding_change_shares", "pct_to_total_shares",
                "pct_to_float_a_shares", "pledged_shares", "frozen_shares",
            ]
            for row in self._provider_rows(
                route=_SHAREHOLDER_ROUTE, symbols=missing_symbols,
                start_date=normalized_dates[0], end_date=normalized_dates[-1],
                fields=fields,
            ):
                symbol = str(row.get("symbol") or "")
                if symbol not in missing_symbols:
                    raise UpstreamFallbackError("financial-data returned unrequested equity")
                report_period = _iso_date(row.get("end_date"))
                if report_period not in requested or (symbol, report_period) in local_coverage:
                    continue
                records.append({
                    "instrument_id": symbol,
                    "report_period": report_period,
                    "publication_date": None,
                    "scope": "reported",
                    "rank": int(row["shareholder_ranking"]) if row.get("shareholder_ranking") is not None else None,
                    "shareholder_name": row.get("shareholder_name"),
                    "shareholder_type": row.get("shareholder_type"),
                    "holding_shares": _number(row.get("total_shares_held")),
                    "holding_pct_total": _number(row.get("pct_to_total_shares")),
                    "holding_pct_float": _number(row.get("pct_to_float_a_shares")),
                    "holding_change_shares": _number(row.get("holding_change_shares")),
                    "pledged_shares": _number(row.get("pledged_shares")),
                    "frozen_shares": _number(row.get("frozen_shares")),
                    "source_id": "financial_data",
                    "source_dataset": _SHAREHOLDER_ROUTE,
                })
        records.sort(key=lambda item: (
            item["instrument_id"], item["report_period"], item["scope"],
            item["rank"] or 999, -(item["holding_shares"] or 0),
        ))
        returned = {(x["instrument_id"], x["report_period"]) for x in records}
        return {
            "data": records,
            "meta": self._meta(
                "canonical_equity_shareholder.v1", normalized_symbols,
                normalized_dates, returned, bool(missing_symbols and allow_quota_fallback),
            ),
        }

    @staticmethod
    def _meta(contract, symbols, periods, returned, fallback_used):
        return {
            "contract": contract,
            "read_strategy": "local_db_first",
            "fallback_policy": "quota_only_after_explicit_local_miss",
            "fallback_used": fallback_used,
            "unresolved": [
                {"instrument_id": symbol, "period": period}
                for symbol in symbols for period in periods
                if (symbol, period) not in returned
            ],
        }

    def restricted_releases(
        self, *, symbols: list[str], start_date: date, end_date: date,
        allow_quota_fallback: bool = True,
    ) -> dict:
        normalized_symbols = self._validate_symbols(symbols)
        self._validate_long_range(start_date, end_date)
        records = []
        local_symbols = set()
        for symbol in normalized_symbols:
            for row in self._local_range("share_float", symbol, start_date, end_date):
                local_symbols.add(symbol)
                records.append({
                    "instrument_id": symbol,
                    "release_date": _iso_date(row.get("float_date")),
                    "publication_date": _iso_date(row.get("ann_date")),
                    "restricted_start_date": None,
                    "shareholder_name": row.get("holder_name"),
                    "release_shares": _number(row.get("float_share")),
                    "release_pct_total": _number(row.get("float_ratio")),
                    "release_type": row.get("share_type"),
                    "source_id": "tushare", "source_dataset": "share_float",
                })
        missing = [x for x in normalized_symbols if x not in local_symbols]
        if allow_quota_fallback and missing:
            fields = [
                "symbol", "release_date", "restricted_start_date",
                "shareholder_name", "release_share_volume",
                "release_share_ratio", "release_type",
            ]
            for row in self._provider_rows(
                route=_RELEASE_ROUTE, symbols=missing, start_date=start_date,
                end_date=end_date, fields=fields,
            ):
                symbol = str(row.get("symbol") or "")
                if symbol not in missing:
                    raise UpstreamFallbackError("financial-data returned unrequested equity")
                records.append({
                    "instrument_id": symbol,
                    "release_date": _iso_date(row.get("release_date")),
                    "publication_date": None,
                    "restricted_start_date": _iso_date(row.get("restricted_start_date")),
                    "shareholder_name": row.get("shareholder_name"),
                    "release_shares": _number(row.get("release_share_volume")),
                    "release_pct_total": _number(row.get("release_share_ratio")),
                    "release_type": row.get("release_type"),
                    "source_id": "financial_data", "source_dataset": _RELEASE_ROUTE,
                })
        records.sort(key=lambda x: (x["release_date"], x["instrument_id"], str(x["shareholder_name"] or "")))
        return {
            "data": records,
            "meta": {
                "contract": "canonical_equity_restricted_release.v1",
                "read_strategy": "local_db_first_by_symbol_range",
                "fallback_used": bool(missing and allow_quota_fallback),
                "unresolved_symbols": [x for x in missing if not any(r["instrument_id"] == x for r in records)],
            },
        }

    def pledges(
        self, *, symbols: list[str], start_date: date, end_date: date,
        allow_quota_fallback: bool = True,
    ) -> dict:
        normalized_symbols = self._validate_symbols(symbols)
        self._validate_long_range(start_date, end_date)
        records = []
        local_symbols = set()
        for symbol in normalized_symbols:
            for row in self._local_range("pledge_detail", symbol, start_date, end_date):
                local_symbols.add(symbol)
                records.append({
                    "instrument_id": symbol,
                    "publication_date": _iso_date(row.get("ann_date")),
                    "event_date": _iso_date(row.get("start_date")) or _iso_date(row.get("ann_date")),
                    "event_type": "share_pledge",
                    "shareholder_name": row.get("holder_name"),
                    "receiver_name": row.get("pledgor"),
                    "involved_shares": _number(row.get("pledge_amount")),
                    "pct_of_total_shares": _number(row.get("p_total_ratio")),
                    "pct_of_pledger": _number(row.get("h_total_ratio")),
                    "end_date": _iso_date(row.get("end_date")),
                    "release_date": _iso_date(row.get("release_date")),
                    "is_released": str(row.get("is_release") or "").upper() in {"Y", "YES", "是", "1", "TRUE"},
                    "reason": None, "statement": None,
                    "source_id": "tushare", "source_dataset": "pledge_detail",
                })
        missing = [x for x in normalized_symbols if x not in local_symbols]
        if allow_quota_fallback and missing:
            fields = [
                "symbol", "information_publish_date", "event_date", "event_type",
                "shareholder_name", "receiver_name", "involved_shares",
                "pct_of_total_shares", "pct_of_pledger", "end_date",
                "estimated_release_date", "is_completely_released",
                "freeze_pledge_reason", "statement",
            ]
            for row in self._provider_rows(
                route=_PLEDGE_ROUTE, symbols=missing, start_date=start_date,
                end_date=end_date, fields=fields,
            ):
                symbol = str(row.get("symbol") or "")
                if symbol not in missing:
                    raise UpstreamFallbackError("financial-data returned unrequested equity")
                records.append({
                    "instrument_id": symbol,
                    "publication_date": _iso_date(row.get("information_publish_date")),
                    "event_date": _iso_date(row.get("event_date")),
                    "event_type": row.get("event_type"),
                    "shareholder_name": row.get("shareholder_name"),
                    "receiver_name": row.get("receiver_name"),
                    "involved_shares": _number(row.get("involved_shares")),
                    "pct_of_total_shares": _number(row.get("pct_of_total_shares")),
                    "pct_of_pledger": _number(row.get("pct_of_pledger")),
                    "end_date": _iso_date(row.get("end_date")),
                    "release_date": _iso_date(row.get("estimated_release_date")),
                    "is_released": str(row.get("is_completely_released") or "") == "是",
                    "reason": row.get("freeze_pledge_reason"),
                    "statement": row.get("statement"),
                    "source_id": "financial_data", "source_dataset": _PLEDGE_ROUTE,
                })
        records.sort(key=lambda x: (x["event_date"], x["instrument_id"], str(x["shareholder_name"] or "")))
        return {
            "data": records,
            "meta": {
                "contract": "canonical_equity_pledge_event.v1",
                "read_strategy": "local_db_first_by_symbol_range",
                "fallback_used": bool(missing and allow_quota_fallback),
                "unresolved_symbols": [x for x in missing if not any(r["instrument_id"] == x for r in records)],
            },
        }

    def risk_alerts(
        self, *, symbols: list[str], start_date: date, end_date: date,
        allow_quota_fallback: bool = True,
    ) -> dict:
        normalized_symbols = self._validate_symbols(symbols)
        self._validate_long_range(start_date, end_date)
        records = []
        local_symbols = set()
        for symbol in normalized_symbols:
            episode_rows = self._local_range("stk_alert", symbol, start_date, end_date)
            snapshot_rows = (
                [] if episode_rows else
                self._local_range("stock_st", symbol, start_date, end_date)
            )
            for row in episode_rows:
                local_symbols.add(symbol)
                records.append({
                    "instrument_id": symbol,
                    "instrument_name": row.get("name"),
                    "effective_date": _iso_date(row.get("start_date")),
                    "removal_date": _iso_date(row.get("end_date")),
                    "publication_date": None,
                    "risk_type": row.get("type"),
                    "is_in_risk_alert_board": None,
                    "reason": None,
                    "description": None,
                    "source_id": "tushare", "source_dataset": "stk_alert",
                })
            for row in snapshot_rows:
                local_symbols.add(symbol)
                records.append({
                    "instrument_id": symbol,
                    "instrument_name": row.get("name"),
                    "effective_date": _iso_date(row.get("imp_date")) or _iso_date(row.get("trade_date")),
                    "removal_date": None,
                    "publication_date": _iso_date(row.get("pub_date")),
                    "risk_type": row.get("st_type") or row.get("type_name") or row.get("type"),
                    "is_in_risk_alert_board": True,
                    "reason": row.get("st_reason"),
                    "description": row.get("st_explain"),
                    "source_id": "tushare", "source_dataset": "stock_st",
                })
        missing = [x for x in normalized_symbols if x not in local_symbols]
        if allow_quota_fallback and missing:
            fields = [
                "symbol", "implement_date", "is_in_risk_alert_board",
                "implement_reason", "implementation_announcement_date",
                "remove_date", "risk_alert_type",
            ]
            for row in self._provider_rows(
                route=_RISK_ROUTE, symbols=missing, start_date=start_date,
                end_date=end_date, fields=fields,
            ):
                symbol = str(row.get("symbol") or "")
                if symbol not in missing:
                    raise UpstreamFallbackError("financial-data returned unrequested equity")
                board = str(row.get("is_in_risk_alert_board") or "").strip()
                records.append({
                    "instrument_id": symbol,
                    "instrument_name": None,
                    "effective_date": _iso_date(row.get("implement_date")),
                    "removal_date": _iso_date(row.get("remove_date")),
                    "publication_date": _iso_date(row.get("implementation_announcement_date")),
                    "risk_type": row.get("risk_alert_type"),
                    "is_in_risk_alert_board": (
                        True if board == "是" else False if board == "否" else None
                    ),
                    "reason": row.get("implement_reason"),
                    "description": None,
                    "source_id": "financial_data", "source_dataset": _RISK_ROUTE,
                })
        records.sort(key=lambda x: (x["effective_date"], x["instrument_id"]))
        return {
            "data": records,
            "meta": {
                "contract": "canonical_equity_risk_alert.v1",
                "read_strategy": "local_db_first_by_symbol_range",
                "fallback_used": bool(missing and allow_quota_fallback),
                "unresolved_symbols": [x for x in missing if not any(r["instrument_id"] == x for r in records)],
            },
        }

    def suspensions(
        self, *, symbols: list[str], start_date: date, end_date: date,
        allow_quota_fallback: bool = True,
    ) -> dict:
        normalized_symbols = self._validate_symbols(symbols)
        self._validate_long_range(start_date, end_date)
        records = []
        local_symbols = set()
        for symbol in normalized_symbols:
            for row in self._local_range("stock_suspend", symbol, start_date, end_date):
                local_symbols.add(symbol)
                records.append({
                    "instrument_id": symbol,
                    "suspend_date": _iso_date(row.get("trade_date")),
                    "resumption_date": None,
                    "suspend_time": row.get("suspend_timing"),
                    "resumption_time": None,
                    "suspend_type": row.get("suspend_type"),
                    "publication_date": None,
                    "reason": None,
                    "statement": None,
                    "source_information": None,
                    "source_id": "tushare", "source_dataset": "stock_suspend",
                })
        missing = [x for x in normalized_symbols if x not in local_symbols]
        if allow_quota_fallback and missing:
            fields = [
                "symbol", "suspend_date", "resumption_date", "suspend_type",
                "information_publish_date", "information_source",
                "resumption_time", "suspend_reason", "suspend_statement",
                "suspend_time",
            ]
            for row in self._provider_rows(
                route=_SUSPEND_ROUTE, symbols=missing, start_date=start_date,
                end_date=end_date, fields=fields,
            ):
                symbol = str(row.get("symbol") or "")
                if symbol not in missing:
                    raise UpstreamFallbackError("financial-data returned unrequested equity")
                records.append({
                    "instrument_id": symbol,
                    "suspend_date": _iso_date(row.get("suspend_date")),
                    "resumption_date": _iso_date(row.get("resumption_date")),
                    "suspend_time": row.get("suspend_time"),
                    "resumption_time": row.get("resumption_time"),
                    "suspend_type": row.get("suspend_type"),
                    "publication_date": _iso_date(row.get("information_publish_date")),
                    "reason": row.get("suspend_reason"),
                    "statement": row.get("suspend_statement"),
                    "source_information": row.get("information_source"),
                    "source_id": "financial_data", "source_dataset": _SUSPEND_ROUTE,
                })
        records.sort(key=lambda x: (x["suspend_date"], x["instrument_id"]))
        return {
            "data": records,
            "meta": {
                "contract": "canonical_equity_suspension.v1",
                "read_strategy": "local_db_first_by_symbol_range",
                "fallback_used": bool(missing and allow_quota_fallback),
                "unresolved_symbols": [x for x in missing if not any(r["instrument_id"] == x for r in records)],
            },
        }
