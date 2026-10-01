"""Canonical DB-first A-share disclosure and shareholder event datasets."""

from __future__ import annotations

from datetime import date, datetime, time
from typing import Any

from service.data_service.canonical_equity import (
    CanonicalEquityDataService,
    _iso_date,
    _number,
)
from service.data_service.models import InvalidQueryError, UpstreamFallbackError


_FORECAST_ROUTE = "/api/v1/stock_fnd/performance-forecast"
_PRELIM_ROUTE = "/api/v1/stock_fnd/prelim-acc"
_DIVIDEND_ROUTE = "/api/v1/stock_fnd/dividend-details"
_REPURCHASE_ROUTE = "/api/v1/stock_fnd/buyback-plans"
_HOLDER_COUNT_ROUTE = "/api/v1/stock_fnd/holder-count"
_FINANCIAL_METRICS_ROUTE = "/api/v1/stock_fnd/growth-rates-acc"
_TTM_METRICS_ROUTE = "/api/v1/stock_fnd/metrics-ttm"
_BUSINESS_SEGMENT_ROUTES = {
    "business": "/api/v1/stock_fnd/main-business-business",
    "industry": "/api/v1/stock_fnd/main-business-industry",
    "product": "/api/v1/stock_fnd/main-business-product",
    "region": "/api/v1/stock_fnd/main-business-region",
}
_LOCAL_SEGMENT_CODES = {"industry": "I", "product": "P"}


def _provider_range(start_date: date, end_date: date) -> tuple[str, str]:
    return (
        datetime.combine(start_date, time.min).strftime("%Y-%m-%d %H:%M:%S"),
        datetime.combine(end_date, time.max).strftime("%Y-%m-%d %H:%M:%S"),
    )


def _amount_10k_cny(value: Any) -> float | None:
    number = _number(value)
    return number * 10_000.0 if number is not None else None


def _forecast_direction(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return "unknown"
    if any(token in text for token in ("预增", "略增", "续盈", "扭亏", "减亏")):
        return "positive"
    if any(token in text for token in ("预减", "略减", "首亏", "续亏", "增亏", "预亏", "预降")):
        return "negative"
    if any(token in text for token in ("预平", "持平")):
        return "flat"
    return "uncertain"


class CanonicalEquityEventService(CanonicalEquityDataService):
    @staticmethod
    def _validate_event_range(start_date: date, end_date: date) -> None:
        if start_date > end_date:
            raise InvalidQueryError("start_date must not be later than end_date")
        if (end_date - start_date).days > 3650:
            raise InvalidQueryError("canonical event queries are limited to 3651 days")

    def _local_exact_periods(
        self,
        *,
        dataset: str,
        symbol: str,
        report_dates: list[date],
        use_date_range: bool = False,
    ) -> list[dict[str, Any]]:
        if use_date_range:
            response = self._data.query_dataset(
                dataset,
                exact_filters={"ts_code": symbol},
                date_value=None,
                start_date=report_dates[0].isoformat(),
                end_date=report_dates[-1].isoformat(),
                limit=1000,
                offset=0,
                include_total=False,
            )
            requested = set(report_dates)
            return [
                row for row in response["data"]
                if _iso_date(row.get("end_date")) in requested
            ]
        rows: list[dict[str, Any]] = []
        for report_date in report_dates:
            response = self._data.query_dataset(
                dataset,
                exact_filters={
                    "ts_code": symbol,
                    "end_date": report_date.isoformat(),
                },
                date_value=None,
                start_date=None,
                end_date=None,
                limit=100,
                offset=0,
                include_total=False,
            )
            rows.extend(response["data"])
        return rows

    @staticmethod
    def _local_forecast(row: dict[str, Any]) -> dict[str, Any]:
        category = row.get("type")
        return {
            "instrument_id": row.get("ts_code"),
            "report_period": _iso_date(row.get("end_date")),
            "publication_date": _iso_date(row.get("ann_date")),
            "update_type": "forecast",
            "accumulation_basis": "cumulative",
            "forecast_category": category,
            "forecast_direction": _forecast_direction(category),
            "revenue_lower": None,
            "revenue_upper": None,
            "parent_net_profit_lower": _amount_10k_cny(row.get("net_profit_min")),
            "parent_net_profit_upper": _amount_10k_cny(row.get("net_profit_max")),
            "parent_net_profit_yoy_lower_pct": _number(row.get("p_change_min")),
            "parent_net_profit_yoy_upper_pct": _number(row.get("p_change_max")),
            "basic_eps_lower": None,
            "basic_eps_upper": None,
            "reported_revenue": None,
            "reported_parent_net_profit": None,
            "reported_operating_cash_flow": None,
            "reported_basic_eps": None,
            "reported_roe_pct": None,
            "summary": row.get("summary"),
            "reason": row.get("change_reason"),
            "currency": "CNY",
            "source_id": "tushare",
            "source_dataset": "forecast",
        }

    @staticmethod
    def _provider_forecast(row: dict[str, Any]) -> dict[str, Any]:
        category = row.get("forecast_type_profit")
        return {
            "instrument_id": row.get("symbol"),
            "report_period": _iso_date(row.get("end_date")),
            "publication_date": _iso_date(row.get("info_publ_date")),
            "update_type": "forecast",
            "accumulation_basis": row.get("accumulate_type") or "unknown",
            "forecast_category": category,
            "forecast_direction": _forecast_direction(category),
            "revenue_lower": _number(row.get("revenue_lower")),
            "revenue_upper": _number(row.get("revenue_upper")),
            "parent_net_profit_lower": _number(row.get("net_profit_lower")),
            "parent_net_profit_upper": _number(row.get("net_profit_upper")),
            "parent_net_profit_yoy_lower_pct": _number(
                row.get("growth_lower_disclosed_profit")
            ),
            "parent_net_profit_yoy_upper_pct": _number(
                row.get("growth_upper_disclosed_profit")
            ),
            "basic_eps_lower": _number(row.get("eps_lower")),
            "basic_eps_upper": _number(row.get("eps_upper")),
            "reported_revenue": None,
            "reported_parent_net_profit": None,
            "reported_operating_cash_flow": None,
            "reported_basic_eps": None,
            "reported_roe_pct": None,
            "summary": row.get("forecast_content_profit"),
            "reason": row.get("result_statement_profit"),
            "currency": "CNY",
            "source_id": "financial_data",
            "source_dataset": _FORECAST_ROUTE,
        }

    @staticmethod
    def _local_preliminary(row: dict[str, Any]) -> dict[str, Any]:
        return {
            "instrument_id": row.get("ts_code"),
            "report_period": _iso_date(row.get("end_date")),
            "publication_date": _iso_date(row.get("ann_date")),
            "update_type": "preliminary",
            "accumulation_basis": "cumulative",
            "forecast_category": None,
            "forecast_direction": "unknown",
            "revenue_lower": None,
            "revenue_upper": None,
            "parent_net_profit_lower": None,
            "parent_net_profit_upper": None,
            "parent_net_profit_yoy_lower_pct": None,
            "parent_net_profit_yoy_upper_pct": None,
            "basic_eps_lower": None,
            "basic_eps_upper": None,
            "reported_revenue": _amount_10k_cny(row.get("revenue")),
            "reported_parent_net_profit": _amount_10k_cny(row.get("n_income")),
            "reported_operating_cash_flow": None,
            "reported_basic_eps": _number(row.get("diluted_eps")),
            "reported_roe_pct": _number(row.get("diluted_roe")),
            "summary": row.get("perf_summary"),
            "reason": None,
            "currency": "CNY",
            "source_id": "tushare",
            "source_dataset": "express",
        }

    @staticmethod
    def _provider_preliminary(row: dict[str, Any]) -> dict[str, Any]:
        return {
            "instrument_id": row.get("symbol"),
            "report_period": _iso_date(
                row.get("report_period") or row.get("report_period_end")
            ),
            "publication_date": _iso_date(row.get("disclosure_date")),
            "update_type": "preliminary",
            "accumulation_basis": "cumulative",
            "forecast_category": None,
            "forecast_direction": "unknown",
            "revenue_lower": None,
            "revenue_upper": None,
            "parent_net_profit_lower": None,
            "parent_net_profit_upper": None,
            "parent_net_profit_yoy_lower_pct": None,
            "parent_net_profit_yoy_upper_pct": None,
            "basic_eps_lower": None,
            "basic_eps_upper": None,
            "reported_revenue": _number(row.get("prel_operating_revenue")),
            "reported_parent_net_profit": _number(row.get("prel_npoc")),
            "reported_operating_cash_flow": _number(row.get("prel_cfo_net")),
            "reported_basic_eps": _number(row.get("prel_basic_eps")),
            "reported_roe_pct": _number(row.get("prel_roe_diluted")),
            "summary": None,
            "reason": None,
            "currency": "CNY",
            "source_id": "financial_data",
            "source_dataset": _PRELIM_ROUTE,
        }

    def performance_updates(
        self,
        *,
        symbols: list[str],
        report_dates: list[date],
        allow_quota_fallback: bool = True,
    ) -> dict:
        normalized_symbols = self._validate_symbols(symbols)
        normalized_dates = self._validate_report_dates(report_dates)
        requested_dates = set(normalized_dates)
        records: list[dict[str, Any]] = []
        local_coverage: dict[str, dict[str, set[date]]] = {}

        for symbol in normalized_symbols:
            forecasts = self._local_exact_periods(
                dataset="forecast", symbol=symbol, report_dates=normalized_dates
            )
            preliminary = self._local_exact_periods(
                dataset="express", symbol=symbol, report_dates=normalized_dates
            )
            records.extend(self._local_forecast(row) for row in forecasts)
            records.extend(self._local_preliminary(row) for row in preliminary)
            local_coverage[symbol] = {
                "forecast": {
                    _iso_date(row.get("end_date")) for row in forecasts
                },
                "preliminary": {
                    _iso_date(row.get("end_date")) for row in preliminary
                },
            }

        provider_start, provider_end = _provider_range(
            normalized_dates[0], normalized_dates[-1]
        )
        fallback_calls: list[str] = []
        for update_type, route, mapper, fields in (
            (
                "forecast", _FORECAST_ROUTE, self._provider_forecast,
                [
                    "symbol", "end_date", "accumulate_type", "info_publ_date",
                    "forecast_type_profit", "result_statement_profit",
                    "forecast_content_profit", "growth_lower_disclosed_profit",
                    "growth_upper_disclosed_profit", "net_profit_lower",
                    "net_profit_upper", "revenue_lower", "revenue_upper",
                    "eps_lower", "eps_upper",
                ],
            ),
            (
                "preliminary", _PRELIM_ROUTE, self._provider_preliminary,
                [
                    "symbol", "report_period", "disclosure_date",
                    "prel_operating_revenue", "prel_npoc", "prel_cfo_net",
                    "prel_basic_eps", "prel_roe_diluted",
                ],
            ),
        ):
            missing_symbols = [
                symbol for symbol in normalized_symbols
                if requested_dates - local_coverage[symbol][update_type]
            ]
            if not allow_quota_fallback or not missing_symbols:
                continue
            fallback_calls.append(route)
            rows = self._financial_rows(
                payload={"mode": "data", "requests": [{
                    "url": route,
                    "params": {
                        "symbols": missing_symbols,
                        "start_date": provider_start,
                        "end_date": provider_end,
                        "fields": fields,
                    },
                }]},
                route=route,
            )
            for row in rows:
                symbol = str(row.get("symbol") or "")
                if symbol not in missing_symbols:
                    raise UpstreamFallbackError(
                        f"financial-data returned unrequested equity: {symbol}"
                    )
                item = mapper(row)
                report_period = item["report_period"]
                if report_period not in requested_dates:
                    continue
                if report_period in local_coverage[symbol][update_type]:
                    continue
                records.append(item)

        records.sort(key=lambda item: (
            item["instrument_id"], item["report_period"],
            item["publication_date"] or date.min, item["update_type"],
        ))
        returned_periods = {
            (item["instrument_id"], item["update_type"], item["report_period"])
            for item in records
        }
        unresolved = [
            {
                "instrument_id": symbol,
                "report_period": report_period,
                "missing_update_types": [
                    update_type for update_type in ("forecast", "preliminary")
                    if (symbol, update_type, report_period) not in returned_periods
                ],
            }
            for symbol in normalized_symbols
            for report_period in normalized_dates
            if any(
                (symbol, update_type, report_period) not in returned_periods
                for update_type in ("forecast", "preliminary")
            )
        ]
        return {
            "data": records,
            "meta": {
                "contract": "canonical_equity_performance_update.v1",
                "read_strategy": "local_db_first",
                "fallback_policy": (
                    "quota_for_explicit_missing_report_periods"
                    if allow_quota_fallback else "none"
                ),
                "fallback_used": bool(fallback_calls),
                "fallback_routes": fallback_calls,
                "unresolved": unresolved,
                "returned": len(records),
            },
        }

    @staticmethod
    def _local_financial_metrics(row: dict[str, Any]) -> dict[str, Any]:
        return {
            "instrument_id": row.get("ts_code"),
            "report_period": _iso_date(row.get("end_date")),
            "disclosure_date": _iso_date(row.get("ann_date")),
            "basic_eps": _number(row.get("eps")),
            "diluted_eps": _number(row.get("dt_eps")),
            "book_value_per_share": _number(row.get("bps")),
            "operating_cash_flow_per_share": _number(row.get("ocfps")),
            "revenue_per_share": _number(row.get("revenue_ps")),
            "roe_diluted_pct": _number(row.get("roe")),
            "roe_weighted_pct": _number(row.get("roe_waa")),
            "roe_deducted_pct": _number(row.get("roe_dt")),
            "roa_pct": _number(row.get("roa")),
            "roic_pct": _number(row.get("roic")),
            "gross_margin_pct": _number(row.get("grossprofit_margin")),
            "net_margin_pct": _number(row.get("netprofit_margin")),
            "current_ratio": _number(row.get("current_ratio")),
            "quick_ratio": _number(row.get("quick_ratio")),
            "debt_to_assets_pct": _number(row.get("debt_to_assets")),
            "interest_coverage_ratio": _number(row.get("ebit_to_interest")),
            "receivables_turnover": _number(row.get("ar_turn")),
            "inventory_turnover": _number(row.get("inv_turn")),
            "asset_turnover": _number(row.get("assets_turn")),
            "operating_revenue_yoy_pct": None,
            "parent_net_profit_yoy_pct": None,
            "deducted_parent_net_profit_yoy_pct": None,
            "operating_cash_flow_to_revenue": _number(
                row.get("salescash_to_or")
            ),
            "source_id": "tushare",
            "source_dataset": "financial_indicator",
        }

    @staticmethod
    def _provider_financial_metrics(row: dict[str, Any]) -> dict[str, Any]:
        return {
            "instrument_id": row.get("symbol"),
            "report_period": _iso_date(
                row.get("report_period") or row.get("report_period_end")
            ),
            "disclosure_date": _iso_date(row.get("disclosure_date")),
            "basic_eps": _number(row.get("basic_eps")),
            "diluted_eps": _number(row.get("diluted_eps")),
            "book_value_per_share": None,
            "operating_cash_flow_per_share": _number(row.get("cfps")),
            "revenue_per_share": _number(row.get("total_rev_ps")),
            "roe_diluted_pct": _number(row.get("roe_diluted")),
            "roe_weighted_pct": _number(row.get("roe_avg")),
            "roe_deducted_pct": _number(row.get("roe_deducted")),
            "roa_pct": _number(row.get("roa")),
            "roic_pct": _number(row.get("roic")),
            "gross_margin_pct": _number(row.get("gross_profit_margin")),
            "net_margin_pct": _number(row.get("net_profit_margin")),
            "current_ratio": None,
            "quick_ratio": None,
            "debt_to_assets_pct": None,
            "interest_coverage_ratio": _number(
                row.get("interest_coverage_ratio")
            ),
            "receivables_turnover": None,
            "inventory_turnover": None,
            "asset_turnover": _number(row.get("total_asset_turnover_rate")),
            "operating_revenue_yoy_pct": _number(
                row.get("operating_revenue_yoy")
            ),
            "parent_net_profit_yoy_pct": _number(row.get("npoc_yoy")),
            "deducted_parent_net_profit_yoy_pct": _number(
                row.get("npoc_deducted_yoy")
            ),
            "operating_cash_flow_to_revenue": _number(
                row.get("cfo_to_oper_rev")
            ),
            "source_id": "financial_data",
            "source_dataset": _FINANCIAL_METRICS_ROUTE,
        }

    def financial_metrics(
        self,
        *,
        symbols: list[str],
        report_dates: list[date],
        allow_quota_fallback: bool = True,
    ) -> dict:
        normalized_symbols = self._validate_symbols(symbols)
        normalized_dates = self._validate_report_dates(report_dates)
        requested_dates = set(normalized_dates)
        records: dict[tuple[str, date], dict[str, Any]] = {}
        for symbol in normalized_symbols:
            rows = self._local_exact_periods(
                dataset="financial_indicator",
                symbol=symbol,
                report_dates=normalized_dates,
                use_date_range=True,
            )
            selected = self._preferred_local_rows(
                rows, report_dates=requested_dates
            )
            for report_period, row in selected.items():
                records[(symbol, report_period)] = self._local_financial_metrics(row)

        missing_symbols = [
            symbol for symbol in normalized_symbols
            if any((symbol, value) not in records for value in normalized_dates)
        ]
        fallback_used = bool(allow_quota_fallback and missing_symbols)
        if fallback_used:
            provider_start, provider_end = _provider_range(
                normalized_dates[0], normalized_dates[-1]
            )
            fields = [
                "symbol", "report_period", "disclosure_date", "basic_eps",
                "diluted_eps", "cfps", "total_rev_ps", "roe_diluted",
                "roe_avg", "roe_deducted", "roa", "roic",
                "gross_profit_margin", "net_profit_margin",
                "interest_coverage_ratio", "total_asset_turnover_rate",
                "operating_revenue_yoy", "npoc_yoy", "npoc_deducted_yoy",
                "cfo_to_oper_rev",
            ]
            rows = self._financial_rows(
                payload={"mode": "data", "requests": [{
                    "url": _FINANCIAL_METRICS_ROUTE,
                    "params": {
                        "symbols": missing_symbols,
                        "start_date": provider_start,
                        "end_date": provider_end,
                        "fields": fields,
                    },
                }]},
                route=_FINANCIAL_METRICS_ROUTE,
            )
            for row in rows:
                symbol = str(row.get("symbol") or "")
                if symbol not in missing_symbols:
                    raise UpstreamFallbackError(
                        f"financial-data returned unrequested equity: {symbol}"
                    )
                item = self._provider_financial_metrics(row)
                report_period = item["report_period"]
                if report_period not in requested_dates:
                    continue
                records.setdefault((symbol, report_period), item)

        data = [records[key] for key in sorted(records)]
        unresolved = [
            {"instrument_id": symbol, "report_period": report_period}
            for symbol in normalized_symbols
            for report_period in normalized_dates
            if (symbol, report_period) not in records
        ]
        return {
            "data": data,
            "meta": {
                "contract": "canonical_equity_financial_metric.v1",
                "read_strategy": "local_db_first",
                "fallback_policy": (
                    "quota_for_explicit_missing_report_periods"
                    if allow_quota_fallback else "none"
                ),
                "fallback_used": fallback_used,
                "unresolved": unresolved,
                "returned": len(data),
            },
        }

    @staticmethod
    def _prior_year_period(value: date) -> date:
        return value.replace(year=value.year - 1)

    @staticmethod
    def _ttm_value(
        current: Any, prior_annual: Any, prior_same_period: Any,
        *, is_annual: bool,
    ) -> float | None:
        current_number = _number(current)
        if is_annual:
            return current_number
        annual_number = _number(prior_annual)
        prior_number = _number(prior_same_period)
        if None in (current_number, annual_number, prior_number):
            return None
        return annual_number + current_number - prior_number

    @staticmethod
    def _provider_ttm(row: dict[str, Any]) -> dict[str, Any]:
        revenue = _number(row.get("operating_revenue_ttm"))
        parent_profit = _number(row.get("npoc_ttm"))
        operating_cash = _number(row.get("cfo_net_ttm"))
        capital_expenditure = _number(row.get("capex_ttm"))
        return {
            "instrument_id": row.get("symbol"),
            "report_period": _iso_date(
                row.get("report_period") or row.get("report_period_end")
            ),
            "disclosure_date": _iso_date(row.get("disclosure_date")),
            "total_revenue_ttm": _number(row.get("total_operating_revenue_ttm")),
            "revenue_ttm": revenue,
            "parent_net_profit_ttm": parent_profit,
            "operating_cash_flow_ttm": operating_cash,
            "capital_expenditure_ttm": capital_expenditure,
            "free_cash_flow_ttm": (
                operating_cash - capital_expenditure
                if operating_cash is not None and capital_expenditure is not None
                else None
            ),
            "net_margin_ttm_pct": _number(row.get("net_profit_margin_ttm")),
            "gross_margin_ttm_pct": _number(row.get("gross_profit_margin_ttm")),
            "roe_ttm_pct": _number(row.get("roe_ttm")),
            "roa_ttm_pct": _number(row.get("roa_ttm")),
            "roic_ttm_pct": _number(row.get("roic_ttm")),
            "basic_eps_ttm": _number(row.get("basic_eps_ttm")),
            "source_id": "financial_data",
            "source_dataset": _TTM_METRICS_ROUTE,
            "calculation": "provider_reported_ttm",
        }

    def ttm_financials(
        self,
        *,
        symbols: list[str],
        report_dates: list[date],
        allow_quota_fallback: bool = True,
    ) -> dict:
        normalized_symbols = self._validate_symbols(symbols)
        normalized_dates = self._validate_report_dates(report_dates)
        if len(normalized_dates) > 6:
            raise InvalidQueryError(
                "ttm_financials accepts at most 6 explicit report_dates"
            )
        required_dates: set[date] = set()
        for report_period in normalized_dates:
            required_dates.add(report_period)
            if (report_period.month, report_period.day) != (12, 31):
                required_dates.add(date(report_period.year - 1, 12, 31))
                required_dates.add(self._prior_year_period(report_period))

        base = self.financial_periods(
            symbols=normalized_symbols,
            report_dates=sorted(required_dates),
            allow_quota_fallback=False,
        )
        statements = {
            (row["instrument_id"], row["report_period"]): row
            for row in base["data"]
        }
        records: dict[tuple[str, date], dict[str, Any]] = {}
        for symbol in normalized_symbols:
            for report_period in normalized_dates:
                current = statements.get((symbol, report_period), {})
                is_annual = (report_period.month, report_period.day) == (12, 31)
                prior_annual = (
                    current if is_annual else statements.get(
                        (symbol, date(report_period.year - 1, 12, 31)), {}
                    )
                )
                prior_same = (
                    current if is_annual else statements.get(
                        (symbol, self._prior_year_period(report_period)), {}
                    )
                )
                current_income = current.get("income") or {}
                annual_income = prior_annual.get("income") or {}
                prior_income = prior_same.get("income") or {}
                current_cash = current.get("cash_flow") or {}
                annual_cash = prior_annual.get("cash_flow") or {}
                prior_cash = prior_same.get("cash_flow") or {}
                total_revenue = self._ttm_value(
                    current_income.get("total_revenue"),
                    annual_income.get("total_revenue"),
                    prior_income.get("total_revenue"),
                    is_annual=is_annual,
                )
                revenue = self._ttm_value(
                    current_income.get("revenue"), annual_income.get("revenue"),
                    prior_income.get("revenue"), is_annual=is_annual,
                )
                parent_profit = self._ttm_value(
                    current_income.get("parent_net_profit"),
                    annual_income.get("parent_net_profit"),
                    prior_income.get("parent_net_profit"),
                    is_annual=is_annual,
                )
                operating_cash = self._ttm_value(
                    current_cash.get("operating_cash_flow"),
                    annual_cash.get("operating_cash_flow"),
                    prior_cash.get("operating_cash_flow"),
                    is_annual=is_annual,
                )
                capex = self._ttm_value(
                    current_cash.get("capital_expenditure_cash_paid"),
                    annual_cash.get("capital_expenditure_cash_paid"),
                    prior_cash.get("capital_expenditure_cash_paid"),
                    is_annual=is_annual,
                )
                if all(value is None for value in (
                    total_revenue, revenue, parent_profit, operating_cash, capex
                )):
                    continue
                records[(symbol, report_period)] = {
                    "instrument_id": symbol,
                    "report_period": report_period,
                    "disclosure_date": current.get("disclosure_date"),
                    "total_revenue_ttm": total_revenue,
                    "revenue_ttm": revenue,
                    "parent_net_profit_ttm": parent_profit,
                    "operating_cash_flow_ttm": operating_cash,
                    "capital_expenditure_ttm": capex,
                    "free_cash_flow_ttm": (
                        operating_cash - capex
                        if operating_cash is not None and capex is not None else None
                    ),
                    "net_margin_ttm_pct": (
                        parent_profit / revenue * 100
                        if parent_profit is not None and revenue not in (None, 0)
                        else None
                    ),
                    "gross_margin_ttm_pct": None,
                    "roe_ttm_pct": None,
                    "roa_ttm_pct": None,
                    "roic_ttm_pct": None,
                    "basic_eps_ttm": None,
                    "source_id": "tushare",
                    "source_dataset": "derived:income+cashflow",
                    "calculation": (
                        "annual_reported" if is_annual
                        else "prior_annual+current_ytd-prior_ytd"
                    ),
                }

        missing_symbols = [
            symbol for symbol in normalized_symbols
            if any((symbol, period) not in records for period in normalized_dates)
        ]
        fallback_used = bool(allow_quota_fallback and missing_symbols)
        if fallback_used:
            provider_start, provider_end = _provider_range(
                normalized_dates[0], normalized_dates[-1]
            )
            fields = [
                "symbol", "report_period", "disclosure_date",
                "total_operating_revenue_ttm", "operating_revenue_ttm",
                "npoc_ttm", "cfo_net_ttm", "capex_ttm",
                "net_profit_margin_ttm", "gross_profit_margin_ttm",
                "roe_ttm", "roa_ttm", "roic_ttm", "basic_eps_ttm",
            ]
            rows = self._financial_rows(
                payload={"mode": "data", "requests": [{
                    "url": _TTM_METRICS_ROUTE,
                    "params": {
                        "symbols": missing_symbols,
                        "start_date": provider_start,
                        "end_date": provider_end,
                        "fields": fields,
                    },
                }]},
                route=_TTM_METRICS_ROUTE,
            )
            requested = set(normalized_dates)
            for row in rows:
                symbol = str(row.get("symbol") or "")
                if symbol not in missing_symbols:
                    raise UpstreamFallbackError(
                        f"financial-data returned unrequested equity: {symbol}"
                    )
                item = self._provider_ttm(row)
                report_period = item["report_period"]
                if report_period not in requested:
                    continue
                records.setdefault((symbol, report_period), item)

        data = [records[key] for key in sorted(records)]
        unresolved = [
            {"instrument_id": symbol, "report_period": report_period}
            for symbol in normalized_symbols
            for report_period in normalized_dates
            if (symbol, report_period) not in records
        ]
        return {
            "data": data,
            "meta": {
                "contract": "canonical_equity_ttm_financial.v1",
                "read_strategy": "local_derived_first",
                "fallback_policy": (
                    "quota_for_unresolved_explicit_report_periods"
                    if allow_quota_fallback else "none"
                ),
                "fallback_used": fallback_used,
                "formula": "prior annual + current YTD - prior-year YTD",
                "unresolved": unresolved,
                "returned": len(data),
            },
        }

    @staticmethod
    def _segment_row(
        row: dict[str, Any], *, classification: str, source_id: str,
        source_dataset: str,
    ) -> dict[str, Any]:
        if source_id == "tushare":
            revenue = _number(row.get("bz_sales"))
            cost = _number(row.get("bz_cost"))
            profit = _number(row.get("bz_profit"))
            name = row.get("bz_item")
            source_information = None
            revenue_share = None
        else:
            revenue = _number(row.get("main_oper_income"))
            cost = _number(row.get("main_oper_cost"))
            profit = _number(row.get("main_oper_profit"))
            name = row.get("segment_name")
            source_information = row.get("information_source")
            revenue_share = _number(row.get("main_oper_income_ratio"))
        return {
            "instrument_id": row.get("ts_code") or row.get("symbol"),
            "report_period": _iso_date(
                row.get("end_date") or row.get("report_period")
                or row.get("report_period_end")
            ),
            "classification": classification,
            "segment_name": name,
            "revenue": revenue,
            "cost": cost,
            "profit": profit,
            "gross_margin_pct": (
                profit / revenue * 100
                if profit is not None and revenue not in (None, 0)
                else _number(row.get("main_gross_margin"))
            ),
            "revenue_share_pct": revenue_share,
            "revenue_yoy_pct": _number(row.get("main_oper_income_yoy")),
            "source_information": source_information,
            "currency": "CNY",
            "source_id": source_id,
            "source_dataset": source_dataset,
        }

    @staticmethod
    def _fill_local_segment_shares(records: list[dict[str, Any]]) -> None:
        totals: dict[tuple[str, date, str], float] = {}
        for item in records:
            if item["source_id"] != "tushare":
                continue
            key = (
                item["instrument_id"], item["report_period"],
                item["classification"],
            )
            # Rows literally named 产品/行业 are source-provided totals.  Use
            # them when present instead of summing overlapping detailed rows.
            if item["segment_name"] in {"产品", "行业", "业务", "地区"}:
                if item["revenue"] is not None:
                    totals[key] = item["revenue"]
        for item in records:
            if item["source_id"] != "tushare":
                continue
            key = (
                item["instrument_id"], item["report_period"],
                item["classification"],
            )
            total = totals.get(key)
            if total not in (None, 0) and item["revenue"] is not None:
                item["revenue_share_pct"] = item["revenue"] / total * 100

    def business_segments(
        self,
        *,
        symbols: list[str],
        report_dates: list[date],
        classifications: list[str],
        allow_quota_fallback: bool = True,
    ) -> dict:
        normalized_symbols = self._validate_symbols(symbols)
        normalized_dates = self._validate_report_dates(report_dates)
        normalized_classes = list(dict.fromkeys(
            str(value).strip().lower() for value in classifications
        ))
        invalid = sorted(set(normalized_classes) - set(_BUSINESS_SEGMENT_ROUTES))
        if not normalized_classes or invalid:
            raise InvalidQueryError(
                "classifications must use business, industry, product or region"
            )
        requested_dates = set(normalized_dates)
        records: list[dict[str, Any]] = []
        local_coverage: set[tuple[str, date, str]] = set()
        for symbol in normalized_symbols:
            response = self._data.query_dataset(
                "fina_mainbz",
                exact_filters={"ts_code": symbol},
                date_value=None,
                start_date=normalized_dates[0].isoformat(),
                end_date=normalized_dates[-1].isoformat(),
                limit=1000,
                offset=0,
                include_total=False,
            )
            for row in response["data"]:
                report_period = _iso_date(row.get("end_date"))
                if report_period not in requested_dates:
                    continue
                code = str(row.get("bz_code") or "").upper()
                classification = next((
                    name for name, expected in _LOCAL_SEGMENT_CODES.items()
                    if code == expected
                ), None)
                if classification not in normalized_classes:
                    continue
                item = self._segment_row(
                    row, classification=classification, source_id="tushare",
                    source_dataset="fina_mainbz",
                )
                records.append(item)
                local_coverage.add((symbol, report_period, classification))
        self._fill_local_segment_shares(records)

        fallback_routes: list[str] = []
        for classification in normalized_classes:
            missing_symbols = [
                symbol for symbol in normalized_symbols
                if any(
                    (symbol, report_period, classification) not in local_coverage
                    for report_period in normalized_dates
                )
            ]
            if not allow_quota_fallback or not missing_symbols:
                continue
            route = _BUSINESS_SEGMENT_ROUTES[classification]
            fallback_routes.append(route)
            provider_start, provider_end = _provider_range(
                normalized_dates[0], normalized_dates[-1]
            )
            fields = [
                "symbol", "report_period", "information_source",
                "main_classification", "segment_name", "main_oper_income",
                "main_oper_cost", "main_oper_profit", "main_gross_margin",
                "main_oper_income_ratio", "main_oper_income_yoy",
            ]
            rows = self._financial_rows(
                payload={"mode": "data", "requests": [{
                    "url": route,
                    "params": {
                        "symbols": missing_symbols,
                        "start_date": provider_start,
                        "end_date": provider_end,
                        "fields": fields,
                    },
                }]},
                route=route,
            )
            for row in rows:
                symbol = str(row.get("symbol") or "")
                if symbol not in missing_symbols:
                    raise UpstreamFallbackError(
                        f"financial-data returned unrequested equity: {symbol}"
                    )
                item = self._segment_row(
                    row, classification=classification,
                    source_id="financial_data", source_dataset=route,
                )
                report_period = item["report_period"]
                if report_period not in requested_dates:
                    continue
                if (symbol, report_period, classification) in local_coverage:
                    continue
                records.append(item)

        records.sort(key=lambda item: (
            item["instrument_id"], item["report_period"],
            item["classification"], -(item["revenue"] or 0),
            str(item["segment_name"] or ""),
        ))
        returned = {
            (item["instrument_id"], item["report_period"], item["classification"])
            for item in records
        }
        unresolved = [
            {
                "instrument_id": symbol,
                "report_period": report_period,
                "classification": classification,
            }
            for symbol in normalized_symbols
            for report_period in normalized_dates
            for classification in normalized_classes
            if (symbol, report_period, classification) not in returned
        ]
        return {
            "data": records,
            "meta": {
                "contract": "canonical_equity_business_segment.v1",
                "read_strategy": "local_db_first_by_classification",
                "fallback_policy": (
                    "quota_for_explicit_missing_report_period_classification"
                    if allow_quota_fallback else "none"
                ),
                "fallback_used": bool(fallback_routes),
                "fallback_routes": fallback_routes,
                "unresolved": unresolved,
                "returned": len(records),
            },
        }

    @staticmethod
    def _local_dividend(row: dict[str, Any]) -> dict[str, Any]:
        return {
            "instrument_id": row.get("ts_code"),
            "report_period": _iso_date(row.get("end_date")),
            "proposal_publication_date": _iso_date(row.get("ann_date")),
            "record_date": _iso_date(row.get("record_date")),
            "ex_dividend_date": _iso_date(row.get("ex_date")),
            "payment_date": _iso_date(row.get("pay_date")),
            "status": row.get("div_proc"),
            "cash_per_share_before_tax": _number(row.get("cash_div_tax")),
            "cash_per_share_after_tax": _number(row.get("cash_div")),
            "total_cash_dividend": None,
            "equity_base_shares": _number(row.get("base_share")),
            "bonus_shares_per_share": _number(row.get("stk_bo_rate")),
            "capitalization_shares_per_share": _number(row.get("stk_co_rate")),
            "description": None,
            "currency": "CNY",
            "source_id": "tushare",
            "source_dataset": "dividend",
        }

    @staticmethod
    def _provider_dividend(row: dict[str, Any]) -> dict[str, Any]:
        total = _number(row.get("total_cash_dividend_cny"))
        base = _number(row.get("dividend_equity_base"))
        return {
            "instrument_id": row.get("symbol"),
            "report_period": _iso_date(row.get("dividend_end_date")),
            "proposal_publication_date": _iso_date(
                row.get("dividend_proposal_publish_date")
            ),
            "record_date": _iso_date(row.get("dividend_record_date")),
            "ex_dividend_date": _iso_date(row.get("ex_rights_div_date")),
            "payment_date": None,
            "status": row.get("dividend_scheme_type"),
            "cash_per_share_before_tax": (
                total / base if total is not None and base not in (None, 0) else None
            ),
            "cash_per_share_after_tax": None,
            "total_cash_dividend": total,
            "equity_base_shares": base,
            "bonus_shares_per_share": None,
            "capitalization_shares_per_share": None,
            "description": row.get("dividend_scheme"),
            "currency": "CNY",
            "source_id": "financial_data",
            "source_dataset": _DIVIDEND_ROUTE,
        }

    def dividends(
        self,
        *,
        symbols: list[str],
        report_dates: list[date],
        allow_quota_fallback: bool = True,
    ) -> dict:
        normalized_symbols = self._validate_symbols(symbols)
        normalized_dates = self._validate_report_dates(report_dates)
        requested_dates = set(normalized_dates)
        records: list[dict[str, Any]] = []
        local_periods: dict[str, set[date]] = {}
        for symbol in normalized_symbols:
            rows = self._local_exact_periods(
                dataset="dividend", symbol=symbol, report_dates=normalized_dates
            )
            records.extend(self._local_dividend(row) for row in rows)
            local_periods[symbol] = {
                _iso_date(row.get("end_date")) for row in rows
            }

        missing_symbols = [
            symbol for symbol in normalized_symbols
            if requested_dates - local_periods[symbol]
        ]
        fallback_used = bool(allow_quota_fallback and missing_symbols)
        if fallback_used:
            provider_start, provider_end = _provider_range(
                normalized_dates[0], normalized_dates[-1]
            )
            fields = [
                "symbol", "dividend_end_date", "dividend_scheme_type",
                "dividend_proposal_publish_date", "dividend_record_date",
                "ex_rights_div_date", "dividend_equity_base",
                "total_cash_dividend_cny", "dividend_scheme",
            ]
            rows = self._financial_rows(
                payload={"mode": "data", "requests": [{
                    "url": _DIVIDEND_ROUTE,
                    "params": {
                        "symbols": missing_symbols,
                        "start_date": provider_start,
                        "end_date": provider_end,
                        "fields": fields,
                    },
                }]},
                route=_DIVIDEND_ROUTE,
            )
            for row in rows:
                symbol = str(row.get("symbol") or "")
                if symbol not in missing_symbols:
                    raise UpstreamFallbackError(
                        f"financial-data returned unrequested equity: {symbol}"
                    )
                item = self._provider_dividend(row)
                if item["report_period"] not in requested_dates:
                    continue
                if item["report_period"] in local_periods[symbol]:
                    continue
                records.append(item)

        records.sort(key=lambda item: (
            item["instrument_id"], item["report_period"],
            item["proposal_publication_date"] or date.min,
        ))
        returned = {(item["instrument_id"], item["report_period"]) for item in records}
        unresolved = [
            {"instrument_id": symbol, "report_period": report_period}
            for symbol in normalized_symbols
            for report_period in normalized_dates
            if (symbol, report_period) not in returned
        ]
        return {
            "data": records,
            "meta": {
                "contract": "canonical_equity_dividend.v1",
                "read_strategy": "local_db_first",
                "fallback_policy": (
                    "quota_for_explicit_missing_report_periods"
                    if allow_quota_fallback else "none"
                ),
                "fallback_used": fallback_used,
                "unresolved": unresolved,
                "returned": len(records),
            },
        }

    @staticmethod
    def _local_repurchase(row: dict[str, Any]) -> dict[str, Any]:
        return {
            "instrument_id": row.get("ts_code"),
            "event_date": _iso_date(row.get("ann_date")),
            "progress_status": row.get("proc"),
            "deadline": _iso_date(row.get("exp_date")),
            "current_shares": _number(row.get("vol")),
            "current_amount": _number(row.get("amount")),
            "current_average_price": None,
            "current_low_price": _number(row.get("low_limit")),
            "current_high_price": _number(row.get("high_limit")),
            "cumulative_shares": None,
            "cumulative_amount": None,
            "planned_amount_lower": None,
            "planned_amount_upper": None,
            "purpose": None,
            "currency": "CNY",
            "source_id": "tushare",
            "source_dataset": "repurchase",
        }

    @staticmethod
    def _provider_repurchase(row: dict[str, Any]) -> dict[str, Any]:
        return {
            "instrument_id": row.get("symbol"),
            "event_date": _iso_date(row.get("end_date")),
            "progress_status": row.get("repurchase_event_progress_description"),
            "deadline": _iso_date(row.get("repurchase_period_end_date")),
            "current_shares": _number(row.get("current_repurchase_shares")),
            "current_amount": _number(row.get("current_repurchase_amount")),
            "current_average_price": _number(
                row.get("current_repurchase_avg_price")
            ),
            "current_low_price": _number(row.get("current_repurchase_low_price")),
            "current_high_price": _number(row.get("current_repurchase_high_price")),
            "cumulative_shares": _number(row.get("cumulative_repurchase_shares")),
            "cumulative_amount": _number(row.get("cumulative_repurchase_amount")),
            "planned_amount_lower": _number(
                row.get("planned_repurchase_amount_lower_limit")
            ),
            "planned_amount_upper": _number(
                row.get("planned_repurchase_amount_upper_limit")
            ),
            "purpose": row.get("repurchase_purpose_description") or row.get(
                "repurchase_purpose"
            ),
            "currency": "CNY",
            "source_id": "financial_data",
            "source_dataset": _REPURCHASE_ROUTE,
        }

    @staticmethod
    def _local_holder_count(row: dict[str, Any]) -> dict[str, Any]:
        return {
            "instrument_id": row.get("ts_code"),
            "observation_date": _iso_date(row.get("end_date")),
            "publication_date": _iso_date(row.get("ann_date")),
            "total_shareholders": _number(row.get("holder_num")),
            "shareholder_change": None,
            "shareholder_change_pct": None,
            "average_holding_shares": None,
            "average_holding_market_value": None,
            "a_share_shareholders": None,
            "currency": "CNY",
            "source_id": "tushare",
            "source_dataset": "stk_holdernumber",
        }

    @staticmethod
    def _provider_holder_count(row: dict[str, Any]) -> dict[str, Any]:
        return {
            "instrument_id": row.get("symbol"),
            "observation_date": _iso_date(row.get("end_date")),
            "publication_date": None,
            "total_shareholders": _number(row.get("total_shareholder_number")),
            "shareholder_change": _number(row.get("shareholder_number_change")),
            "shareholder_change_pct": _number(
                row.get("shareholder_number_change_ratio")
            ),
            "average_holding_shares": _number(row.get("avg_hold_shares")),
            "average_holding_market_value": _number(row.get("avg_hold_mv")),
            "a_share_shareholders": _number(row.get("a_share_shareholder_number")),
            "currency": "CNY",
            "source_id": "financial_data",
            "source_dataset": _HOLDER_COUNT_ROUTE,
        }

    def _range_events(
        self,
        *,
        symbols: list[str],
        start_date: date,
        end_date: date,
        dataset: str,
        route: str,
        fields: list[str],
        local_mapper,
        provider_mapper,
        date_field: str,
        contract: str,
        allow_quota_fallback: bool,
    ) -> dict:
        self._validate_event_range(start_date, end_date)
        normalized_symbols = self._validate_symbols(symbols)
        records: list[dict[str, Any]] = []
        fallback_symbols: list[str] = []
        for symbol in normalized_symbols:
            response = self._data.query_dataset(
                dataset,
                exact_filters={"ts_code": symbol},
                date_value=None,
                start_date=start_date.isoformat(),
                end_date=end_date.isoformat(),
                limit=1000,
                offset=0,
                include_total=False,
            )
            records.extend(local_mapper(row) for row in response["data"])
            if not response["data"]:
                fallback_symbols.append(symbol)

        fallback_used = bool(allow_quota_fallback and fallback_symbols)
        if fallback_used:
            provider_start, provider_end = _provider_range(start_date, end_date)
            rows = self._financial_rows(
                payload={"mode": "data", "requests": [{
                    "url": route,
                    "params": {
                        "symbols": fallback_symbols,
                        "start_date": provider_start,
                        "end_date": provider_end,
                        "fields": fields,
                    },
                }]},
                route=route,
            )
            for row in rows:
                symbol = str(row.get("symbol") or "")
                if symbol not in fallback_symbols:
                    raise UpstreamFallbackError(
                        f"financial-data returned unrequested equity: {symbol}"
                    )
                item = provider_mapper(row)
                observed = item[date_field]
                if observed is None or not start_date <= observed <= end_date:
                    raise UpstreamFallbackError(
                        f"financial-data returned {contract} outside requested range"
                    )
                records.append(item)

        records.sort(key=lambda item: (
            item["instrument_id"], item[date_field] or date.min
        ))
        return {
            "data": records,
            "meta": {
                "contract": contract,
                "read_strategy": "local_db_first",
                "fallback_policy": (
                    "quota_if_local_symbol_slice_empty"
                    if allow_quota_fallback else "none"
                ),
                "fallback_used": fallback_used,
                "fallback_symbols": fallback_symbols if fallback_used else [],
                "unresolved_symbols": [
                    symbol for symbol in normalized_symbols
                    if not any(item["instrument_id"] == symbol for item in records)
                ],
                "returned": len(records),
            },
        }

    def repurchases(
        self, *, symbols: list[str], start_date: date, end_date: date,
        allow_quota_fallback: bool = True,
    ) -> dict:
        return self._range_events(
            symbols=symbols, start_date=start_date, end_date=end_date,
            dataset="repurchase", route=_REPURCHASE_ROUTE,
            fields=[
                "symbol", "end_date", "current_repurchase_shares",
                "current_repurchase_amount", "current_repurchase_avg_price",
                "current_repurchase_low_price", "current_repurchase_high_price",
                "cumulative_repurchase_shares", "cumulative_repurchase_amount",
                "repurchase_period_end_date",
                "repurchase_event_progress_description",
                "planned_repurchase_amount_lower_limit",
                "planned_repurchase_amount_upper_limit", "repurchase_purpose",
                "repurchase_purpose_description",
            ],
            local_mapper=self._local_repurchase,
            provider_mapper=self._provider_repurchase,
            date_field="event_date",
            contract="canonical_equity_repurchase.v1",
            allow_quota_fallback=allow_quota_fallback,
        )

    def holder_counts(
        self, *, symbols: list[str], start_date: date, end_date: date,
        allow_quota_fallback: bool = True,
    ) -> dict:
        return self._range_events(
            symbols=symbols, start_date=start_date, end_date=end_date,
            dataset="stk_holdernumber", route=_HOLDER_COUNT_ROUTE,
            fields=[
                "symbol", "end_date", "total_shareholder_number",
                "shareholder_number_change", "shareholder_number_change_ratio",
                "avg_hold_shares", "avg_hold_mv", "a_share_shareholder_number",
            ],
            local_mapper=self._local_holder_count,
            provider_mapper=self._provider_holder_count,
            date_field="observation_date",
            contract="canonical_equity_holder_count.v1",
            allow_quota_fallback=allow_quota_fallback,
        )
