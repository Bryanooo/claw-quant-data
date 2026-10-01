"""Canonical DB-first A-share identity and valuation datasets."""

from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal, InvalidOperation
import json
import re
from typing import Any

from service.data_service.models import InvalidQueryError, UpstreamFallbackError
from service.source_connectors.contracts import AcquisitionMode, ConnectorRequest
from service.source_connectors.financial_data_protocol import tabular_rows


_A_SHARE = re.compile(r"^(\d{6})\.(SH|SZ|BJ)$")
_PROFILE_ROUTE = "/api/v1/stock_fnd/stock-basic-info"
_VALUATION_ROUTE = "/api/v1/stock/daily-valuation-indicators"
_INCOME_CASHFLOW_ROUTE = "/api/v1/stock_fnd/income-cashflow-acc"
_BALANCE_SHEET_ROUTE = "/api/v1/stock_fnd/balance-sheet"


def _number(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(Decimal(str(value)))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise UpstreamFallbackError(f"invalid numeric equity value: {value!r}") from exc


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
    raise UpstreamFallbackError(f"invalid equity date: {value!r}")


def _listing_status(value: Any) -> str:
    text = str(value or "").strip().upper()
    return {
        "L": "listed",
        "上市": "listed",
        "D": "delisted",
        "退市": "delisted",
        "P": "pre_listing",
        "发行": "pre_listing",
    }.get(text, "unknown")


def _provider_controller(value: Any) -> str | None:
    if value is None or value == "":
        return None
    if not isinstance(value, str):
        raise UpstreamFallbackError("financial-data actual_controller must be text")
    text = value.strip()
    if not text.startswith("{"):
        return text
    try:
        payload = json.loads(text)
        rows = payload.get("data")
        if not isinstance(rows, list):
            raise ValueError("data is not a list")
        names = [
            str(row["actual_controller_name"]).strip()
            for row in rows
            if isinstance(row, dict) and row.get("actual_controller_name")
        ]
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        raise UpstreamFallbackError(
            "financial-data actual_controller payload is invalid"
        ) from exc
    return ", ".join(dict.fromkeys(names)) or None


class CanonicalEquityDataService:
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
        invalid = []
        for symbol in normalized:
            match = _A_SHARE.fullmatch(symbol)
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
                "canonical equity queries currently support A-share symbols only: "
                + ", ".join(invalid)
            )
        return normalized

    @staticmethod
    def _validate_range(start_date: date, end_date: date) -> None:
        if start_date > end_date:
            raise InvalidQueryError("start_date must not be later than end_date")
        if (end_date - start_date).days > 365:
            raise InvalidQueryError("canonical equity queries are limited to 366 days")

    @staticmethod
    def _local_profile(row: dict[str, Any]) -> dict[str, Any]:
        return {
            "instrument_id": row.get("ts_code"),
            "ticker": row.get("symbol"),
            "name": row.get("name"),
            "full_name": row.get("fullname"),
            "english_name": row.get("enname"),
            "exchange": row.get("exchange"),
            "board": row.get("market"),
            "currency": row.get("curr_type") or "CNY",
            "listing_status": _listing_status(row.get("list_status")),
            "listing_date": _iso_date(row.get("list_date")),
            "region_name": row.get("area"),
            "industry_name": row.get("industry"),
            "industry_classification": "tushare_legacy",
            "actual_controller": row.get("act_name"),
            "source_id": "tushare",
            "source_dataset": "stock_basic",
        }

    @staticmethod
    def _financial_profile(row: dict[str, Any]) -> dict[str, Any]:
        return {
            "instrument_id": row.get("symbol"),
            "ticker": row.get("stock_code"),
            "name": row.get("stock_abbr"),
            "full_name": row.get("company_cn_name"),
            "english_name": row.get("company_en_name"),
            "exchange": row.get("exchange_en_abbr"),
            "board": row.get("listing_board"),
            "currency": "CNY",
            "listing_status": _listing_status(row.get("listing_status")),
            "listing_date": _iso_date(row.get("listing_date")),
            "region_name": row.get("province"),
            "industry_name": row.get("sw_second_industry_name"),
            "industry_classification": "sw_level_2",
            "actual_controller": _provider_controller(row.get("actual_controller")),
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
                "stock_basic",
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
            fields = [
                "symbol", "stock_code", "stock_abbr", "company_cn_name",
                "company_en_name", "exchange_en_abbr", "listing_board",
                "listing_status", "listing_date", "province",
                "sw_second_industry_name", "actual_controller",
            ]
            rows = self._financial_rows(
                payload={"mode": "data", "requests": [{
                    "url": _PROFILE_ROUTE,
                    "params": {"symbols": missing, "fields": fields},
                }]},
                route=_PROFILE_ROUTE,
            )
            for row in rows:
                symbol = str(row.get("symbol") or "")
                if symbol not in missing:
                    raise UpstreamFallbackError(
                        f"financial-data returned unrequested equity: {symbol}"
                    )
                records.setdefault(symbol, self._financial_profile(row))

        data = [records[symbol] for symbol in normalized if symbol in records]
        return {
            "data": data,
            "meta": {
                "contract": "canonical_equity_profile.v1",
                "read_strategy": "local_db_first",
                "fallback_policy": "quota_if_local_empty" if allow_quota_fallback else "none",
                "fallback_used": fallback_used,
                "fallback_symbols": missing if fallback_used else [],
                "unresolved_symbols": [s for s in normalized if s not in records],
                "returned": len(data),
            },
        }

    @staticmethod
    def _local_valuation(row: dict[str, Any]) -> dict[str, Any]:
        total_share = _number(row.get("total_share"))
        float_share = _number(row.get("float_share"))
        total_mv = _number(row.get("total_mv"))
        circ_mv = _number(row.get("circ_mv"))
        dividend_lyr = _number(row.get("dv_ratio"))
        dividend_ttm = _number(row.get("dv_ttm"))
        return {
            "instrument_id": row.get("ts_code"),
            "observation_date": _iso_date(row.get("trade_date")),
            "currency": "CNY",
            "close": _number(row.get("close")),
            "pe_lyr": _number(row.get("pe")),
            "pe_ttm": _number(row.get("pe_ttm")),
            "pb_mrq": _number(row.get("pb")),
            "ps_lyr": _number(row.get("ps")),
            "ps_ttm": _number(row.get("ps_ttm")),
            "dividend_yield_lyr_rate": dividend_lyr / 100.0 if dividend_lyr is not None else None,
            "dividend_yield_ttm_rate": dividend_ttm / 100.0 if dividend_ttm is not None else None,
            # Tushare daily_basic: share quantities are 10k shares; market caps are 10k CNY.
            "total_shares": total_share * 10_000.0 if total_share is not None else None,
            "float_shares": float_share * 10_000.0 if float_share is not None else None,
            "total_market_cap": total_mv * 10_000.0 if total_mv is not None else None,
            "float_market_cap": circ_mv * 10_000.0 if circ_mv is not None else None,
            "source_id": "tushare",
            "source_dataset": "stock_daily_basic",
        }

    @staticmethod
    def _financial_valuation(row: dict[str, Any]) -> dict[str, Any]:
        dividend_lyr = _number(row.get("dividend_yield_lyr"))
        dividend_ttm = _number(row.get("dividend_yield_ttm"))
        return {
            "instrument_id": row.get("symbol"),
            "observation_date": _iso_date(row.get("trading_day")),
            "currency": "CNY",
            "close": None,
            "pe_lyr": _number(row.get("pe_lyr")),
            "pe_ttm": _number(row.get("pe_ttm")),
            "pb_mrq": _number(row.get("pb_mrq")),
            "ps_lyr": _number(row.get("ps_lyr")),
            "ps_ttm": _number(row.get("ps_ttm")),
            "dividend_yield_lyr_rate": dividend_lyr / 100.0 if dividend_lyr is not None else None,
            "dividend_yield_ttm_rate": dividend_ttm / 100.0 if dividend_ttm is not None else None,
            "total_shares": None,
            "float_shares": None,
            "total_market_cap": _number(row.get("total_market_cap")),
            # ab_float_market_cap is not semantically identical to Tushare's
            # A-share circulation market cap for dual-listed securities.
            "float_market_cap": None,
            "source_id": "financial_data",
            "source_dataset": _VALUATION_ROUTE,
        }

    def valuations(
        self,
        *,
        symbols: list[str],
        start_date: date,
        end_date: date,
        allow_quota_fallback: bool = True,
    ) -> dict:
        self._validate_range(start_date, end_date)
        normalized = self._validate_symbols(symbols)
        calendar = self._data.query_dataset(
            "trade_calendar",
            exact_filters={"exchange": "SSE", "is_open": "1"},
            date_value=None,
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
            limit=400,
            offset=0,
            include_total=False,
        )
        expected_dates = {_iso_date(row.get("cal_date")) for row in calendar["data"]}
        records: dict[tuple[str, date], dict[str, Any]] = {}
        fallback_symbols: list[str] = []
        coverage: dict[str, dict[str, int]] = {}
        for symbol in normalized:
            response = self._data.query_dataset(
                "stock_daily_basic",
                exact_filters={"ts_code": symbol},
                date_value=None,
                start_date=start_date.isoformat(),
                end_date=end_date.isoformat(),
                limit=400,
                offset=0,
                include_total=False,
            )
            local_dates: set[date] = set()
            coverage[symbol] = {"local_rows": len(response["data"]), "fallback_rows": 0}
            for row in response["data"]:
                item = self._local_valuation(row)
                local_dates.add(item["observation_date"])
                records[(symbol, item["observation_date"])] = item
            if (expected_dates and expected_dates - local_dates) or not response["data"]:
                fallback_symbols.append(symbol)

        fallback_used = bool(fallback_symbols and allow_quota_fallback)
        if fallback_used:
            fields = [
                "symbol", "trading_day", "total_market_cap", "pe_lyr",
                "pe_ttm", "pb_mrq", "ps_lyr", "ps_ttm",
                "dividend_yield_lyr", "dividend_yield_ttm",
            ]
            rows = self._financial_rows(
                payload={"mode": "data", "requests": [{
                    "url": _VALUATION_ROUTE,
                    "params": {
                        "symbols": fallback_symbols,
                        "start_date": datetime.combine(start_date, time.min).strftime("%Y-%m-%d %H:%M:%S"),
                        "end_date": datetime.combine(end_date, time.max).strftime("%Y-%m-%d %H:%M:%S"),
                        "fields": fields,
                    },
                }]},
                route=_VALUATION_ROUTE,
            )
            for row in rows:
                symbol = str(row.get("symbol") or "")
                if symbol not in fallback_symbols:
                    raise UpstreamFallbackError(
                        f"financial-data returned unrequested equity: {symbol}"
                    )
                item = self._financial_valuation(row)
                observation_date = item["observation_date"]
                if observation_date is None or not start_date <= observation_date <= end_date:
                    raise UpstreamFallbackError(
                        "financial-data returned valuation outside requested range"
                    )
                records.setdefault((symbol, observation_date), item)
                coverage[symbol]["fallback_rows"] += 1

        data = sorted(records.values(), key=lambda item: (item["instrument_id"], item["observation_date"]))
        unresolved = {
            symbol: sorted(
                day for day in expected_dates if (symbol, day) not in records
            )
            for symbol in normalized
        }
        return {
            "data": data,
            "meta": {
                "contract": "canonical_equity_valuation.v1",
                "read_strategy": "local_db_first",
                "fallback_policy": "quota_for_missing_open_sessions" if allow_quota_fallback else "none",
                "fallback_used": fallback_used,
                "fallback_symbols": fallback_symbols if fallback_used else [],
                "unresolved_open_dates": unresolved,
                "coverage": coverage,
                "returned": len(data),
            },
        }

    @staticmethod
    def _validate_report_dates(report_dates: list[date]) -> list[date]:
        normalized = sorted(set(report_dates))
        if not normalized or len(normalized) > 20:
            raise InvalidQueryError(
                "report_dates must contain between 1 and 20 values"
            )
        invalid = [
            value for value in normalized
            if (value.month, value.day) not in {
                (3, 31), (6, 30), (9, 30), (12, 31)
            }
        ]
        if invalid:
            raise InvalidQueryError(
                "A-share financial report_dates must be calendar quarter ends: "
                + ", ".join(value.isoformat() for value in invalid)
            )
        return normalized

    @staticmethod
    def _preferred_local_rows(
        rows: list[dict[str, Any]],
        *,
        report_dates: set[date],
    ) -> dict[date, dict[str, Any]]:
        """Select one current statement per period without hiding its disclosure."""
        candidates: dict[date, list[dict[str, Any]]] = {}
        for row in rows:
            report_period = _iso_date(row.get("end_date"))
            if report_period in report_dates:
                candidates.setdefault(report_period, []).append(row)

        selected: dict[date, dict[str, Any]] = {}
        for report_period, period_rows in candidates.items():
            def rank(row: dict[str, Any]) -> tuple[int, int, int]:
                disclosure = _iso_date(row.get("f_ann_date") or row.get("ann_date"))
                report_type = str(row.get("report_type") or "")
                update_flag = str(row.get("update_flag") or "")
                return (
                    disclosure.toordinal() if disclosure else 0,
                    1 if report_type == "1" else 0,
                    1 if update_flag == "1" else 0,
                )

            selected[report_period] = max(period_rows, key=rank)
        return selected

    @staticmethod
    def _local_income(row: dict[str, Any]) -> dict[str, Any]:
        return {
            "total_revenue": _number(row.get("total_revenue")),
            "revenue": _number(row.get("revenue")),
            "operating_profit": _number(row.get("operate_profit")),
            "total_profit": _number(row.get("total_profit")),
            "net_profit": _number(row.get("n_income")),
            "parent_net_profit": _number(row.get("n_income_attr_p")),
        }

    @staticmethod
    def _local_cash_flow(row: dict[str, Any]) -> dict[str, Any]:
        return {
            "operating_cash_flow": _number(row.get("n_cashflow_act")),
            "investing_cash_flow": _number(row.get("n_cashflow_inv_act")),
            "financing_cash_flow": _number(row.get("n_cash_flows_fnc_act")),
            "capital_expenditure_cash_paid": _number(
                row.get("c_pay_acq_const_fiolta")
            ),
        }

    @staticmethod
    def _local_balance_sheet(row: dict[str, Any]) -> dict[str, Any]:
        return {
            "total_assets": _number(row.get("total_assets")),
            "total_liabilities": _number(row.get("total_liab")),
            "total_equity": _number(row.get("total_hldr_eqy_inc_min_int")),
            "monetary_capital": _number(row.get("money_cap")),
            "inventories": _number(row.get("inventories")),
            "accounts_receivable": _number(row.get("accounts_receiv")),
            "accounts_payable": _number(row.get("acct_payable")),
        }

    @staticmethod
    def _provider_income(row: dict[str, Any]) -> dict[str, Any]:
        return {
            "total_revenue": _number(row.get("total_operating_revenue")),
            "revenue": _number(row.get("operating_revenue")),
            "operating_profit": _number(row.get("operating_profit")),
            "total_profit": _number(row.get("total_profit")),
            "net_profit": _number(row.get("net_profit")),
            "parent_net_profit": _number(row.get("npoc")),
        }

    @staticmethod
    def _provider_cash_flow(row: dict[str, Any]) -> dict[str, Any]:
        return {
            "operating_cash_flow": _number(row.get("cfo_net")),
            "investing_cash_flow": _number(row.get("cfi_net")),
            "financing_cash_flow": _number(row.get("cff_net")),
            "capital_expenditure_cash_paid": _number(
                row.get("cash_pay_acq_const_fiolta")
            ),
        }

    @staticmethod
    def _provider_balance_sheet(row: dict[str, Any]) -> dict[str, Any]:
        return {
            "total_assets": _number(row.get("total_assets")),
            "total_liabilities": _number(row.get("total_liab")),
            "total_equity": _number(row.get("total_equity")),
            "monetary_capital": _number(row.get("monetary_capital")),
            "inventories": _number(row.get("inventories")),
            "accounts_receivable": _number(row.get("acct_receivable")),
            "accounts_payable": _number(row.get("acct_payable")),
        }

    @staticmethod
    def _section_source(
        *, source_id: str, source_dataset: str, disclosure_date: date | None
    ) -> dict[str, Any]:
        return {
            "source_id": source_id,
            "source_dataset": source_dataset,
            "disclosure_date": disclosure_date,
        }

    def financial_periods(
        self,
        *,
        symbols: list[str],
        report_dates: list[date],
        allow_quota_fallback: bool = True,
    ) -> dict:
        """Return audited cumulative statement facts for explicit report periods.

        Report periods are explicit rather than inferred. This prevents an
        unpublished current quarter from being misclassified as missing and
        lets the response distinguish each statement section's source.
        """
        normalized_symbols = self._validate_symbols(symbols)
        normalized_dates = self._validate_report_dates(report_dates)
        requested_dates = set(normalized_dates)
        start_date = normalized_dates[0].isoformat()
        end_date = normalized_dates[-1].isoformat()

        records: dict[tuple[str, date], dict[str, Any]] = {
            (symbol, report_period): {
                "instrument_id": symbol,
                "report_period": report_period,
                "disclosure_date": None,
                "currency": "CNY",
                "income": None,
                "cash_flow": None,
                "balance_sheet": None,
                "source_sections": {
                    "income": None,
                    "cash_flow": None,
                    "balance_sheet": None,
                },
            }
            for symbol in normalized_symbols
            for report_period in normalized_dates
        }
        coverage: dict[str, dict[str, int]] = {}

        for symbol in normalized_symbols:
            local_sections: dict[str, dict[date, dict[str, Any]]] = {}
            for section, dataset in (
                ("income", "income"),
                ("cash_flow", "cashflow"),
                ("balance_sheet", "balancesheet"),
            ):
                response = self._data.query_dataset(
                    dataset,
                    exact_filters={"ts_code": symbol},
                    date_value=None,
                    start_date=start_date,
                    end_date=end_date,
                    limit=1000,
                    offset=0,
                    include_total=False,
                )
                local_sections[section] = self._preferred_local_rows(
                    response["data"], report_dates=requested_dates
                )

            coverage[symbol] = {
                "requested_periods": len(normalized_dates),
                "local_income_periods": len(local_sections["income"]),
                "local_cash_flow_periods": len(local_sections["cash_flow"]),
                "local_balance_sheet_periods": len(
                    local_sections["balance_sheet"]
                ),
                "fallback_income_periods": 0,
                "fallback_cash_flow_periods": 0,
                "fallback_balance_sheet_periods": 0,
            }
            for section, rows in local_sections.items():
                dataset = {
                    "income": "income",
                    "cash_flow": "cashflow",
                    "balance_sheet": "balancesheet",
                }[section]
                mapper = {
                    "income": self._local_income,
                    "cash_flow": self._local_cash_flow,
                    "balance_sheet": self._local_balance_sheet,
                }[section]
                for report_period, row in rows.items():
                    disclosure = _iso_date(
                        row.get("f_ann_date") or row.get("ann_date")
                    )
                    item = records[(symbol, report_period)]
                    item[section] = mapper(row)
                    item["source_sections"][section] = self._section_source(
                        source_id="tushare",
                        source_dataset=dataset,
                        disclosure_date=disclosure,
                    )

        missing_income_cash = {
            symbol for symbol in normalized_symbols
            if any(
                records[(symbol, report_period)][section] is None
                for report_period in normalized_dates
                for section in ("income", "cash_flow")
            )
        }
        missing_balance = {
            symbol for symbol in normalized_symbols
            if any(
                records[(symbol, report_period)]["balance_sheet"] is None
                for report_period in normalized_dates
            )
        }
        fallback_used = bool(
            allow_quota_fallback and (missing_income_cash or missing_balance)
        )
        provider_start = datetime.combine(normalized_dates[0], time.min).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        provider_end = datetime.combine(normalized_dates[-1], time.max).strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        if allow_quota_fallback and missing_income_cash:
            fields = [
                "symbol", "report_period", "disclosure_date",
                "total_operating_revenue", "operating_revenue",
                "operating_profit", "total_profit", "net_profit", "npoc",
                "cfo_net", "cfi_net", "cff_net",
                "cash_pay_acq_const_fiolta",
            ]
            rows = self._financial_rows(
                payload={"mode": "data", "requests": [{
                    "url": _INCOME_CASHFLOW_ROUTE,
                    "params": {
                        "symbols": sorted(missing_income_cash),
                        "start_date": provider_start,
                        "end_date": provider_end,
                        "fields": fields,
                    },
                }]},
                route=_INCOME_CASHFLOW_ROUTE,
            )
            for row in rows:
                symbol = str(row.get("symbol") or "")
                if symbol not in missing_income_cash:
                    raise UpstreamFallbackError(
                        f"financial-data returned unrequested equity: {symbol}"
                    )
                report_period = _iso_date(
                    row.get("report_period") or row.get("report_period_end")
                )
                if report_period not in requested_dates:
                    continue
                disclosure = _iso_date(row.get("disclosure_date"))
                item = records[(symbol, report_period)]
                if item["income"] is None:
                    item["income"] = self._provider_income(row)
                    item["source_sections"]["income"] = self._section_source(
                        source_id="financial_data",
                        source_dataset=_INCOME_CASHFLOW_ROUTE,
                        disclosure_date=disclosure,
                    )
                    coverage[symbol]["fallback_income_periods"] += 1
                if item["cash_flow"] is None:
                    item["cash_flow"] = self._provider_cash_flow(row)
                    item["source_sections"]["cash_flow"] = self._section_source(
                        source_id="financial_data",
                        source_dataset=_INCOME_CASHFLOW_ROUTE,
                        disclosure_date=disclosure,
                    )
                    coverage[symbol]["fallback_cash_flow_periods"] += 1

        if allow_quota_fallback and missing_balance:
            fields = [
                "symbol", "report_period", "disclosure_date", "total_liab",
                "total_assets", "monetary_capital", "total_equity",
                "acct_payable", "acct_receivable", "inventories",
            ]
            rows = self._financial_rows(
                payload={"mode": "data", "requests": [{
                    "url": _BALANCE_SHEET_ROUTE,
                    "params": {
                        "symbols": sorted(missing_balance),
                        "start_date": provider_start,
                        "end_date": provider_end,
                        "fields": fields,
                    },
                }]},
                route=_BALANCE_SHEET_ROUTE,
            )
            for row in rows:
                symbol = str(row.get("symbol") or "")
                if symbol not in missing_balance:
                    raise UpstreamFallbackError(
                        f"financial-data returned unrequested equity: {symbol}"
                    )
                report_period = _iso_date(
                    row.get("report_period") or row.get("report_period_end")
                )
                if report_period not in requested_dates:
                    continue
                item = records[(symbol, report_period)]
                if item["balance_sheet"] is not None:
                    continue
                disclosure = _iso_date(row.get("disclosure_date"))
                item["balance_sheet"] = self._provider_balance_sheet(row)
                item["source_sections"]["balance_sheet"] = self._section_source(
                    source_id="financial_data",
                    source_dataset=_BALANCE_SHEET_ROUTE,
                    disclosure_date=disclosure,
                )
                coverage[symbol]["fallback_balance_sheet_periods"] += 1

        unresolved: list[dict[str, Any]] = []
        data: list[dict[str, Any]] = []
        for key in sorted(records):
            item = records[key]
            disclosures = [
                source["disclosure_date"]
                for source in item["source_sections"].values()
                if source and source["disclosure_date"]
            ]
            item["disclosure_date"] = max(disclosures) if disclosures else None
            missing_sections = [
                section for section in ("income", "cash_flow", "balance_sheet")
                if item[section] is None
            ]
            if missing_sections:
                unresolved.append({
                    "instrument_id": item["instrument_id"],
                    "report_period": item["report_period"],
                    "missing_sections": missing_sections,
                })
            if any(item[section] is not None for section in (
                "income", "cash_flow", "balance_sheet"
            )):
                data.append(item)

        return {
            "data": data,
            "meta": {
                "contract": "canonical_equity_financial_period.v1",
                "statement_basis": "cumulative_year_to_date",
                "read_strategy": "local_db_first",
                "fallback_policy": (
                    "quota_for_explicit_missing_statement_sections"
                    if allow_quota_fallback else "none"
                ),
                "fallback_used": fallback_used,
                "coverage": coverage,
                "unresolved": unresolved,
                "returned": len(data),
            },
        }
