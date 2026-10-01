"""Canonical DB-first fund datasets with bounded quota-source fallback."""

from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal, InvalidOperation
import re
from typing import Any

from service.data_service.models import InvalidQueryError, UpstreamFallbackError
from service.source_connectors.contracts import AcquisitionMode, ConnectorRequest
from service.source_connectors.financial_data_protocol import tabular_rows


_FUND_CODE = re.compile(r"^\d{6}\.(OF|SH|SZ)$")
_PROFILE_ROUTE = "/api/v1/fund/fund-archive"
_NAV_ROUTE = "/api/v1/fund/net-value"
_HOLDINGS_ROUTE = "/api/v1/fund/stock-portfolio"
_DIVIDEND_ROUTE = "/api/v1/fund/dividend"
_MANAGER_ROUTE = "/api/v1/fund/fund-manager"


def _number(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(Decimal(str(value)))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise UpstreamFallbackError(f"invalid numeric fund value: {value!r}") from exc


def _iso_date(value: Any) -> date | None:
    if value is None or value == "":
        return None
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
    raise UpstreamFallbackError(f"invalid fund date: {value!r}")


def _rate(value: Any) -> float | None:
    """Normalize a percent display/value to a decimal rate."""
    if value is None or value == "":
        return None
    text = str(value).strip()
    if text.endswith("%"):
        return _number(text[:-1]) / 100.0
    # Tushare's m_fee/c_fee contract expresses percent points (1.2 == 1.2%).
    return _number(text) / 100.0


class CanonicalFundDataService:
    """Expose only reviewed common fund semantics across both providers."""

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
    def _validate_symbols(symbols: list[str]) -> list[str]:
        normalized = list(dict.fromkeys(symbol.strip().upper() for symbol in symbols))
        if not normalized or len(normalized) > 10:
            raise InvalidQueryError("symbols must contain between 1 and 10 values")
        invalid = [symbol for symbol in normalized if not _FUND_CODE.fullmatch(symbol)]
        if invalid:
            raise InvalidQueryError(
                "canonical fund queries require six-digit OF/SH/SZ symbols: "
                + ", ".join(invalid)
            )
        return normalized

    @staticmethod
    def _validate_range(start_date: date, end_date: date) -> None:
        if start_date > end_date:
            raise InvalidQueryError("start_date must not be later than end_date")
        if (end_date - start_date).days > 365:
            raise InvalidQueryError("canonical fund NAV queries are limited to 366 days")

    @staticmethod
    def _local_profile(row: dict[str, Any]) -> dict[str, Any]:
        minimum = _number(row.get("min_amount"))
        return {
            "fund_id": row.get("ts_code"),
            "name": row.get("name"),
            "management_company": row.get("management"),
            "custodian": row.get("custodian"),
            "fund_type": row.get("fund_type") or row.get("type"),
            "investment_style": row.get("invest_type"),
            "establishment_date": _iso_date(row.get("found_date")),
            "minimum_purchase_amount": minimum * 10_000.0 if minimum is not None else None,
            "amount_currency": "CNY",
            "management_fee_rate": _rate(row.get("m_fee")),
            "custodian_fee_rate": _rate(row.get("c_fee")),
            "source_id": "tushare",
            "source_dataset": "fund_basic",
        }

    @staticmethod
    def _financial_profile(row: dict[str, Any]) -> dict[str, Any]:
        return {
            "fund_id": row.get("symbol"),
            "name": row.get("fund_name"),
            "management_company": row.get("fund_mgmt_company"),
            "custodian": None,
            "fund_type": None,
            "investment_style": None,
            "establishment_date": _iso_date(row.get("establishment_date")),
            "minimum_purchase_amount": _number(row.get("min_purchase_amount")),
            "amount_currency": row.get("currency") or "CNY",
            "management_fee_rate": _rate(row.get("mgmt_fee_rate")),
            "custodian_fee_rate": _rate(row.get("custodian_fee_rate")),
            "source_id": "financial_data",
            "source_dataset": _PROFILE_ROUTE,
        }

    def profiles(
        self,
        *,
        symbols: list[str],
        allow_quota_fallback: bool = True,
    ) -> dict:
        normalized = self._validate_symbols(symbols)
        records: dict[str, dict[str, Any]] = {}
        missing: list[str] = []
        for symbol in normalized:
            response = self._data.query_dataset(
                "fund_basic",
                exact_filters={"ts_code": symbol},
                date_value=None,
                start_date=None,
                end_date=None,
                limit=2,
                offset=0,
                include_total=False,
            )
            if response["data"]:
                records[symbol] = self._local_profile(response["data"][0])
            else:
                missing.append(symbol)

        fallback_used = bool(missing and allow_quota_fallback)
        if fallback_used:
            rows = self._financial_rows(
                payload={"mode": "data", "requests": [{
                    "url": _PROFILE_ROUTE,
                    "params": {"symbols": missing},
                }]},
                route=_PROFILE_ROUTE,
            )
            for row in rows:
                symbol = str(row.get("symbol") or "")
                if symbol not in missing:
                    raise UpstreamFallbackError(
                        f"financial-data returned unrequested fund: {symbol}"
                    )
                records.setdefault(symbol, self._financial_profile(row))

        data = [records[symbol] for symbol in normalized if symbol in records]
        unresolved = [symbol for symbol in normalized if symbol not in records]
        return {
            "data": data,
            "meta": {
                "contract": "canonical_fund_profile.v1",
                "read_strategy": "local_db_first",
                "fallback_policy": "quota_if_local_empty" if allow_quota_fallback else "none",
                "fallback_used": fallback_used,
                "fallback_symbols": missing if fallback_used else [],
                "unresolved_symbols": unresolved,
                "returned": len(data),
            },
        }

    def dividends(
        self,
        *,
        symbols: list[str],
        start_date: date,
        end_date: date,
        allow_quota_fallback: bool = True,
    ) -> dict:
        self._validate_range(start_date, end_date)
        normalized = self._validate_symbols(symbols)
        records: list[dict[str, Any]] = []
        local_symbols: set[str] = set()
        for symbol in normalized:
            response = self._data.query_dataset(
                "fund_div", exact_filters={"ts_code": symbol}, date_value=None,
                start_date=start_date.isoformat(), end_date=end_date.isoformat(),
                limit=1000, offset=0, include_total=False,
            )
            for row in response["data"]:
                local_symbols.add(symbol)
                records.append({
                    "fund_id": symbol,
                    "announcement_date": _iso_date(row.get("ann_date")),
                    "record_date": _iso_date(row.get("record_date")),
                    "ex_dividend_date": _iso_date(row.get("ex_date")),
                    "payment_date": _iso_date(row.get("pay_date")),
                    "cash_per_unit": _number(row.get("div_cash")),
                    "distribution_base_units": _number(row.get("base_unit")),
                    "status": row.get("div_proc"),
                    "currency": "CNY",
                    "source_id": "tushare", "source_dataset": "fund_div",
                })
        missing = [symbol for symbol in normalized if symbol not in local_symbols]
        if allow_quota_fallback and missing:
            fields = [
                "symbol", "ex_dividend_date", "record_date",
                "dividend_pay_date", "dist_per_10_units",
            ]
            rows = self._financial_rows(
                payload={"mode": "data", "requests": [{
                    "url": _DIVIDEND_ROUTE,
                    "params": {
                        "symbols": missing,
                        "start_date": datetime.combine(start_date, time.min).strftime("%Y-%m-%d %H:%M:%S"),
                        "end_date": datetime.combine(end_date, time.max).strftime("%Y-%m-%d %H:%M:%S"),
                        "fields": fields,
                    },
                }]}, route=_DIVIDEND_ROUTE,
            )
            for row in rows:
                symbol = str(row.get("symbol") or "")
                if symbol not in missing:
                    raise UpstreamFallbackError("financial-data returned unrequested fund")
                per_ten = _number(row.get("dist_per_10_units"))
                records.append({
                    "fund_id": symbol,
                    "announcement_date": None,
                    "record_date": _iso_date(row.get("record_date")),
                    "ex_dividend_date": _iso_date(row.get("ex_dividend_date")),
                    "payment_date": _iso_date(row.get("dividend_pay_date")),
                    "cash_per_unit": per_ten / 10.0 if per_ten is not None else None,
                    "distribution_base_units": None,
                    "status": None,
                    "currency": "CNY",
                    "source_id": "financial_data", "source_dataset": _DIVIDEND_ROUTE,
                })
        records.sort(key=lambda item: (item["fund_id"], item["ex_dividend_date"] or date.min))
        return {
            "data": records,
            "meta": {
                "contract": "canonical_fund_dividend.v1",
                "read_strategy": "local_db_first_by_symbol_range",
                "fallback_used": bool(missing and allow_quota_fallback),
                "unresolved_symbols": [
                    symbol for symbol in missing
                    if not any(row["fund_id"] == symbol for row in records)
                ],
            },
        }

    def managers(
        self, *, symbols: list[str], allow_quota_fallback: bool = True,
    ) -> dict:
        normalized = self._validate_symbols(symbols)
        records: list[dict[str, Any]] = []
        local_symbols: set[str] = set()
        for symbol in normalized:
            response = self._data.query_dataset(
                "fund_manager", exact_filters={"ts_code": symbol},
                date_value=None, start_date=None, end_date=None,
                limit=1000, offset=0, include_total=False,
            )
            for row in response["data"]:
                local_symbols.add(symbol)
                records.append({
                    "fund_id": symbol,
                    "manager_name": row.get("name"),
                    "tenure_start_date": _iso_date(row.get("begin_date")),
                    "tenure_end_date": _iso_date(row.get("end_date")),
                    "tenure_return_rate": None,
                    "career_start_date": None,
                    "background": row.get("resume"),
                    "education": row.get("edu"),
                    "source_id": "tushare", "source_dataset": "fund_manager",
                })
        missing = [symbol for symbol in normalized if symbol not in local_symbols]
        if allow_quota_fallback and missing:
            fields = [
                "symbol", "tenure_return", "tenure_start_date", "manager_name",
                "career_start_date", "tenure_end_date", "background",
            ]
            rows = self._financial_rows(
                payload={"mode": "data", "requests": [{
                    "url": _MANAGER_ROUTE,
                    "params": {"symbols": missing, "fields": fields},
                }]}, route=_MANAGER_ROUTE,
            )
            for row in rows:
                symbol = str(row.get("symbol") or "")
                if symbol not in missing:
                    raise UpstreamFallbackError("financial-data returned unrequested fund")
                records.append({
                    "fund_id": symbol,
                    "manager_name": row.get("manager_name"),
                    "tenure_start_date": _iso_date(row.get("tenure_start_date")),
                    "tenure_end_date": _iso_date(row.get("tenure_end_date")),
                    "tenure_return_rate": _number(row.get("tenure_return")),
                    "career_start_date": _iso_date(row.get("career_start_date")),
                    "background": row.get("background"),
                    "education": None,
                    "source_id": "financial_data", "source_dataset": _MANAGER_ROUTE,
                })
        records.sort(key=lambda item: (item["fund_id"], item["tenure_start_date"] or date.min, str(item["manager_name"] or "")))
        return {
            "data": records,
            "meta": {
                "contract": "canonical_fund_manager.v1",
                "read_strategy": "local_db_first_by_fund",
                "fallback_used": bool(missing and allow_quota_fallback),
                "unresolved_symbols": [
                    symbol for symbol in missing
                    if not any(row["fund_id"] == symbol for row in records)
                ],
            },
        }

    @staticmethod
    def _local_nav(row: dict[str, Any]) -> dict[str, Any]:
        return {
            "fund_id": row.get("ts_code"),
            "nav_date": _iso_date(row.get("nav_date")),
            "announcement_date": _iso_date(row.get("ann_date")),
            "unit_nav": _number(row.get("unit_nav")),
            "cumulative_nav": _number(row.get("accum_nav")),
            "adjusted_nav": _number(row.get("adj_nav")),
            "daily_return_rate": None,
            "annualized_yield_7d_rate": None,
            "daily_profit_per_10k": None,
            "currency": "CNY",
            "source_id": "tushare",
            "source_dataset": "fund_nav",
        }

    @staticmethod
    def _financial_nav(row: dict[str, Any]) -> dict[str, Any]:
        annualized_yield = _number(row.get("annualized_yield_7d"))
        return {
            "fund_id": row.get("symbol"),
            "nav_date": _iso_date(row.get("nav_date")),
            "announcement_date": None,
            "unit_nav": _number(row.get("unit_nav")),
            "cumulative_nav": _number(row.get("cumulative_nav")),
            "adjusted_nav": _number(row.get("adj_nav")),
            # Provider values are decimal rates despite the inventory's "%" label.
            "daily_return_rate": _number(row.get("pct_chg_1d")),
            # The provider emits 0.844 for 0.844%, unlike pct_chg_1d which is
            # already a decimal return. Normalize the named rate to 0.00844.
            "annualized_yield_7d_rate": (
                annualized_yield / 100.0
                if annualized_yield is not None else None
            ),
            "daily_profit_per_10k": _number(row.get("daily_profit_per_10k")),
            "currency": "CNY",
            "source_id": "financial_data",
            "source_dataset": _NAV_ROUTE,
        }

    def nav(
        self,
        *,
        symbols: list[str],
        start_date: date,
        end_date: date,
        allow_quota_fallback: bool = True,
    ) -> dict:
        self._validate_range(start_date, end_date)
        normalized = self._validate_symbols(symbols)
        records: dict[tuple[str, date], dict[str, Any]] = {}
        missing: list[str] = []
        coverage: dict[str, dict[str, int]] = {}
        for symbol in normalized:
            response = self._data.query_dataset(
                "fund_nav",
                exact_filters={"ts_code": symbol},
                date_value=None,
                start_date=start_date.isoformat(),
                end_date=end_date.isoformat(),
                limit=1000,
                offset=0,
                include_total=False,
            )
            coverage[symbol] = {"local_rows": len(response["data"]), "fallback_rows": 0}
            for row in response["data"]:
                item = self._local_nav(row)
                records[(symbol, item["nav_date"])] = item
            # Fund NAV publication calendars differ. Never infer a daily gap;
            # only an entirely empty requested slice may consume quota.
            if not response["data"]:
                missing.append(symbol)

        fallback_used = bool(missing and allow_quota_fallback)
        if fallback_used:
            rows = self._financial_rows(
                payload={"mode": "data", "requests": [{
                    "url": _NAV_ROUTE,
                    "params": {
                        "symbols": missing,
                        "start_date": datetime.combine(start_date, time.min).strftime("%Y-%m-%d %H:%M:%S"),
                        "end_date": datetime.combine(end_date, time.max).strftime("%Y-%m-%d %H:%M:%S"),
                    },
                }]},
                route=_NAV_ROUTE,
            )
            for row in rows:
                symbol = str(row.get("symbol") or "")
                if symbol not in missing:
                    raise UpstreamFallbackError(
                        f"financial-data returned unrequested fund: {symbol}"
                    )
                item = self._financial_nav(row)
                nav_date = item["nav_date"]
                if nav_date is None or not start_date <= nav_date <= end_date:
                    raise UpstreamFallbackError("financial-data returned NAV outside requested range")
                records.setdefault((symbol, nav_date), item)
                coverage[symbol]["fallback_rows"] += 1

        data = sorted(records.values(), key=lambda item: (item["fund_id"], item["nav_date"]))
        return {
            "data": data,
            "meta": {
                "contract": "canonical_fund_nav.v1",
                "read_strategy": "local_db_first",
                "fallback_policy": "quota_if_local_slice_empty" if allow_quota_fallback else "none",
                "fallback_used": fallback_used,
                "fallback_symbols": missing if fallback_used else [],
                "unresolved_symbols": [s for s in missing if coverage[s]["fallback_rows"] == 0],
                "gap_semantics": "no daily-gap inference; fund publication calendars vary",
                "coverage": coverage,
                "returned": len(data),
            },
        }

    @staticmethod
    def _validate_report_dates(report_dates: list[date]) -> list[date]:
        normalized = list(dict.fromkeys(report_dates))
        if not normalized or len(normalized) > 8:
            raise InvalidQueryError("report_dates must contain between 1 and 8 values")
        valid_month_days = {(3, 31), (6, 30), (9, 30), (12, 31)}
        invalid = [item for item in normalized if (item.month, item.day) not in valid_month_days]
        if invalid:
            raise InvalidQueryError("fund holding report dates must be calendar quarter ends")
        return normalized

    @staticmethod
    def _local_holding(row: dict[str, Any]) -> dict[str, Any]:
        return {
            "fund_id": row.get("ts_code"),
            "report_date": _iso_date(row.get("end_date")),
            "announcement_date": _iso_date(row.get("ann_date")),
            "instrument_id": row.get("symbol"),
            "instrument_name": None,
            "holding_shares": _number(row.get("amount")),
            "holding_market_value": _number(row.get("mkv")),
            "market_value_currency": "CNY",
            "weight_pct": _number(row.get("stk_mkv_ratio")),
            "source_id": "tushare",
            "source_dataset": "fund_portfolio",
        }

    @staticmethod
    def _financial_holding(row: dict[str, Any]) -> dict[str, Any]:
        market = str(row.get("secu_market") or "").upper()
        code = str(row.get("stock_symbol") or "")
        if market not in {"SH", "SZ", "BJ"} or not re.fullmatch(r"\d{6}", code):
            raise UpstreamFallbackError("financial-data returned invalid holding instrument")
        weight = _number(row.get("pct_to_nav"))
        return {
            "fund_id": row.get("symbol"),
            "report_date": _iso_date(row.get("report_period")),
            "announcement_date": None,
            "instrument_id": f"{code}.{market}",
            "instrument_name": row.get("stock_name"),
            "holding_shares": _number(row.get("holding_shares")),
            "holding_market_value": _number(row.get("holding_mv")),
            "market_value_currency": "CNY",
            # Provider pct_to_nav is a decimal ratio (0.0645 == 6.45%).
            "weight_pct": weight * 100.0 if weight is not None else None,
            "source_id": "financial_data",
            "source_dataset": _HOLDINGS_ROUTE,
        }

    def stock_holdings(
        self,
        *,
        symbols: list[str],
        report_dates: list[date],
        allow_quota_fallback: bool = True,
    ) -> dict:
        normalized = self._validate_symbols(symbols)
        periods = self._validate_report_dates(report_dates)
        records: dict[tuple[str, date, str], dict[str, Any]] = {}
        missing: list[tuple[str, date]] = []
        coverage: dict[str, dict[str, int]] = {}
        for symbol in normalized:
            for period in periods:
                key = f"{symbol}@{period.isoformat()}"
                response = self._data.query_dataset(
                    "fund_portfolio",
                    exact_filters={"ts_code": symbol},
                    date_value=period.isoformat(),
                    start_date=None,
                    end_date=None,
                    limit=1000,
                    offset=0,
                    include_total=False,
                )
                coverage[key] = {"local_rows": len(response["data"]), "fallback_rows": 0}
                for row in response["data"]:
                    item = self._local_holding(row)
                    records[(symbol, period, item["instrument_id"])] = item
                if not response["data"]:
                    missing.append((symbol, period))

        fallback_used = bool(missing and allow_quota_fallback)
        if fallback_used:
            # Group by fund instead of sending a Cartesian symbol/period batch:
            # this avoids consuming quota for locally complete partitions.
            periods_by_symbol: dict[str, list[date]] = {}
            for symbol, period in missing:
                periods_by_symbol.setdefault(symbol, []).append(period)
            for requested_symbol, requested_periods in periods_by_symbol.items():
                rows = self._financial_rows(
                    payload={"mode": "data", "requests": [{
                        "url": _HOLDINGS_ROUTE,
                        "params": {
                            "symbols": [requested_symbol],
                            "report_dates": [
                                period.isoformat() for period in requested_periods
                            ],
                        },
                    }]},
                    route=_HOLDINGS_ROUTE,
                )
                allowed = {(requested_symbol, period) for period in requested_periods}
                for row in rows:
                    item = self._financial_holding(row)
                    pair = (str(item["fund_id"] or ""), item["report_date"])
                    if pair not in allowed:
                        raise UpstreamFallbackError(
                            "financial-data returned an unrequested fund/report period"
                        )
                    records.setdefault((*pair, item["instrument_id"]), item)
                    coverage[f"{pair[0]}@{pair[1].isoformat()}"]["fallback_rows"] += 1

        data = sorted(
            records.values(),
            key=lambda item: (item["fund_id"], item["report_date"], item["instrument_id"]),
        )
        unresolved = [
            f"{symbol}@{period.isoformat()}"
            for symbol, period in missing
            if coverage[f"{symbol}@{period.isoformat()}"]["fallback_rows"] == 0
        ]
        return {
            "data": data,
            "meta": {
                "contract": "canonical_fund_stock_holding.v1",
                "read_strategy": "local_db_first",
                "fallback_policy": "quota_if_local_period_empty" if allow_quota_fallback else "none",
                "fallback_scope": "provider_top_10_holdings_only",
                "fallback_used": fallback_used,
                "fallback_partitions": [
                    f"{symbol}@{period.isoformat()}" for symbol, period in missing
                ] if fallback_used else [],
                "unresolved_partitions": unresolved,
                "coverage": coverage,
                "returned": len(data),
            },
        }
