"""Point-in-time financial members of the local 272-factor product.

The input cross-section is assembled only from statements whose announcement
date is not later than the logical trade date.  This module contains no SQL so
the formulas are independently testable and cannot accidentally introduce
look-ahead through a repository shortcut.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd


def _safe_div(left: pd.Series, right: pd.Series) -> pd.Series:
    return left.div(right.replace(0, np.nan)).replace([np.inf, -np.inf], np.nan)


def _rank(value: pd.Series) -> pd.Series:
    return value.replace([np.inf, -np.inf], np.nan).rank(pct=True)


@dataclass(slots=True)
class FinancialCrossSection:
    securities: pd.Index
    close: pd.Series
    total_mv: pd.Series
    current: dict[str, pd.Series] = field(default_factory=dict)
    previous: dict[str, pd.Series] = field(default_factory=dict)
    year_ago: dict[str, pd.Series] = field(default_factory=dict)
    previous_year_ago: dict[str, pd.Series] = field(default_factory=dict)
    ttm: dict[str, pd.Series] = field(default_factory=dict)
    ttm_previous: dict[str, pd.Series] = field(default_factory=dict)
    ttm_year_ago: dict[str, pd.Series] = field(default_factory=dict)
    annual: dict[str, pd.Series] = field(default_factory=dict)
    annual_year_ago: dict[str, pd.Series] = field(default_factory=dict)
    annual_five_year_ago: dict[str, pd.Series] = field(default_factory=dict)
    five_year_mean: dict[str, pd.Series] = field(default_factory=dict)
    dividend_cash_3y: pd.Series | None = None
    roe_ttm_lag63d: pd.Series | None = None

    def values(self, bucket: str, metric: str) -> pd.Series:
        mapping = getattr(self, bucket)
        value = mapping.get(metric)
        if value is None:
            return pd.Series(np.nan, index=self.securities, dtype=float)
        return value.reindex(self.securities).astype(float)


class FinancialFactorEvaluator:
    def __init__(self, panel: FinancialCrossSection):
        self.p = panel

    def v(self, bucket: str, metric: str) -> pd.Series:
        return self.p.values(bucket, metric)

    def _margin(self, bucket: str, numerator: str) -> pd.Series:
        return _safe_div(self.v(bucket, numerator), self.v(bucket, "revenue"))

    def _ratio_growth(
        self, numerator: str, denominator: str, *, ttm: bool = False,
    ) -> pd.Series:
        current_bucket = "ttm" if ttm else "current"
        previous_bucket = "ttm_year_ago" if ttm else "year_ago"
        current = _safe_div(
            self.v(current_bucket, numerator), self.v("current", denominator)
        )
        previous = _safe_div(
            self.v(previous_bucket, numerator), self.v("year_ago", denominator)
        )
        return _safe_div(current, previous) - 1

    def _growth(self, metric: str, current: str, base: str) -> pd.Series:
        return _safe_div(self.v(current, metric), self.v(base, metric)) - 1

    def _growth_factors(self) -> dict[str, pd.Series]:
        eps_ttm = _safe_div(
            self.v("ttm", "net_profit_parent"), self.v("current", "total_share")
        )
        eps_growth = self._growth("net_profit_parent", "ttm", "ttm_year_ago")
        pe = _safe_div(self.p.close, eps_ttm)
        net_asset_growth = self._growth("equity_parent", "current", "year_ago")
        roa = _safe_div(self.v("ttm", "net_profit"), self.v("current", "total_assets"))
        roa_yoy = _safe_div(
            roa,
            _safe_div(self.v("ttm_year_ago", "net_profit"), self.v("year_ago", "total_assets")),
        ) - 1
        roe = _safe_div(self.v("ttm", "net_profit_parent"), self.v("current", "equity"))
        roe_yoy = _safe_div(
            roe,
            _safe_div(self.v("ttm_year_ago", "net_profit_parent"), self.v("year_ago", "equity")),
        ) - 1
        gross_margin = (
            self.v("ttm", "revenue") - self.v("ttm", "oper_cost")
        ).pipe(lambda value: _safe_div(value, self.v("ttm", "revenue")))
        prior_gross_margin = (
            self.v("ttm_previous", "revenue") - self.v("ttm_previous", "oper_cost")
        ).pipe(lambda value: _safe_div(value, self.v("ttm_previous", "revenue")))
        sales_per_share = _safe_div(
            self.v("current", "revenue"), self.v("current", "total_share")
        )
        sales_per_share_yoy = _safe_div(
            self.v("year_ago", "revenue"), self.v("year_ago", "total_share")
        )
        prior_sales = _safe_div(
            self.v("previous", "revenue"), self.v("previous", "total_share")
        )
        prior_sales_yoy = _safe_div(
            self.v("previous_year_ago", "revenue"),
            self.v("previous_year_ago", "total_share"),
        )
        sales_growth = _safe_div(sales_per_share, sales_per_share_yoy) - 1
        prior_sales_growth = _safe_div(prior_sales, prior_sales_yoy) - 1
        eps_q = self.v("current", "basic_eps")
        eps_q_yoy = self.v("year_ago", "basic_eps")
        eps_prev = self.v("previous", "basic_eps")
        eps_prev_yoy = self.v("previous_year_ago", "basic_eps")
        eps_growth_q = _safe_div(eps_q, eps_q_yoy) - 1
        eps_growth_prev = _safe_div(eps_prev, eps_prev_yoy) - 1
        roa_growth = roa - _safe_div(
            self.v("ttm_year_ago", "net_profit"), self.v("year_ago", "total_assets")
        )
        prior_roa_growth = _safe_div(
            self.v("ttm_previous", "net_profit"), self.v("previous", "total_assets")
        ) - _safe_div(
            self.v("ttm_year_ago", "net_profit"), self.v("year_ago", "total_assets")
        )
        return {
            "peg_252d": _safe_div(pe, eps_growth * 100),
            "np_ttm_qoq": _rank(self._growth("net_profit", "ttm", "ttm_previous")),
            "yoy_net_profit": self._growth("net_profit", "ttm", "ttm_year_ago"),
            "yoy_ocf": _rank(self._growth("operating_cashflow", "ttm", "ttm_year_ago")),
            "sa": _rank(sales_growth - prior_sales_growth),
            "gross_margin_qoq": _rank(_safe_div(gross_margin, prior_gross_margin) - 1),
            "pa": _rank(roa_growth - prior_roa_growth),
            "yoy_roa": _rank(roa_yoy),
            "yoy_net_asset": _rank(net_asset_growth),
            "yoy_revenue": self._growth("revenue", "ttm", "ttm_year_ago"),
            "yoy_roe": _rank(roe_yoy),
            "yoy_total_asset": _rank(self._growth("total_assets", "current", "year_ago")),
            "eaa": _rank(eps_growth_q - eps_growth_prev),
            "eap": _rank(
                _safe_div(eps_q - eps_q_yoy, self.p.close)
                - _safe_div(eps_prev - eps_prev_yoy, self.p.close)
            ),
            "asset_growth_qoq": _rank(self._growth("total_assets", "current", "previous")),
        }

    def _quality_factors(self) -> dict[str, pd.Series]:
        current = lambda metric: self.v("current", metric)
        previous = lambda metric: self.v("previous", metric)
        year_ago = lambda metric: self.v("year_ago", metric)
        ttm = lambda metric: self.v("ttm", metric)
        ttm_prev = lambda metric: self.v("ttm_previous", metric)
        ttm_yoy = lambda metric: self.v("ttm_year_ago", metric)
        annual = lambda metric: self.v("annual", metric)
        assets = current("total_assets")
        equity = current("equity")
        equity_parent = current("equity_parent")
        revenue_ttm = ttm("revenue")
        gpm_ttm = _safe_div(revenue_ttm - ttm("oper_cost"), revenue_ttm)
        gpm_prev = _safe_div(
            ttm_prev("revenue") - ttm_prev("oper_cost"), ttm_prev("revenue")
        )
        gpm_yoy = _safe_div(
            ttm_yoy("revenue") - ttm_yoy("oper_cost"), ttm_yoy("revenue")
        )
        npm_ttm = _safe_div(ttm("net_profit"), revenue_ttm)
        npm_prev = _safe_div(ttm_prev("net_profit"), ttm_prev("revenue"))
        npm_yoy = _safe_div(ttm_yoy("net_profit"), ttm_yoy("revenue"))
        opm_ttm = _safe_div(ttm("operate_profit"), revenue_ttm)
        opm_yoy = _safe_div(ttm_yoy("operate_profit"), ttm_yoy("revenue"))
        current_ratio = _safe_div(current("total_cur_assets"), current("total_cur_liab"))
        current_ratio_yoy = _safe_div(year_ago("total_cur_assets"), year_ago("total_cur_liab"))
        quick_ratio = _safe_div(
            current("total_cur_assets") - current("inventories"), current("total_cur_liab")
        )
        quick_ratio_yoy = _safe_div(
            year_ago("total_cur_assets") - year_ago("inventories"),
            year_ago("total_cur_liab"),
        )
        cash_ratio = _safe_div(
            current("cash").fillna(0) + current("trad_asset").fillna(0),
            current("total_cur_liab"),
        )
        cash_ratio_yoy = _safe_div(
            year_ago("cash").fillna(0) + year_ago("trad_asset").fillna(0),
            year_ago("total_cur_liab"),
        )
        debt_equity = _safe_div(current("total_liab"), equity)
        debt_equity_yoy = _safe_div(year_ago("total_liab"), year_ago("equity"))
        roa = _safe_div(ttm("net_profit"), assets)
        roa_yoy = _safe_div(ttm_yoy("net_profit"), year_ago("total_assets"))
        roe = _safe_div(ttm("net_profit_parent"), equity)
        roe_yoy = _safe_div(ttm_yoy("net_profit_parent"), year_ago("equity"))
        asset_turnover = _safe_div(revenue_ttm, assets)
        asset_turnover_yoy = _safe_div(ttm_yoy("revenue"), year_ago("total_assets"))
        inventory_turnover = _safe_div(ttm("oper_cost"), current("inventories"))
        inventory_turnover_yoy = _safe_div(
            ttm_yoy("oper_cost"), year_ago("inventories")
        )
        operating_inflow = ttm("operating_cash_inflow")
        investing_inflow = ttm("investing_cash_inflow")
        quality = (
            _safe_div(ttm("total_profit"), assets)
            + _safe_div(ttm("net_profit"), equity)
            + roa
            + _safe_div(operating_inflow + investing_inflow, assets)
            + _safe_div(ttm("total_profit"), revenue_ttm)
            + _safe_div(ttm("net_profit"), operating_inflow + investing_inflow)
        )
        total_expenses = ttm("sell_exp") + ttm("admin_exp") + ttm("fin_exp")
        total_expenses_q = current("sell_exp") + current("admin_exp") + current("fin_exp")
        total_expenses_yoy = year_ago("sell_exp") + year_ago("admin_exp") + year_ago("fin_exp")
        npm_q = _safe_div(current("net_profit"), current("revenue"))
        npm_prev_q = _safe_div(previous("net_profit"), previous("revenue"))
        return {
            "roe_ttm_lag63d": (self.p.roe_ttm_lag63d.reindex(self.p.securities)
                if self.p.roe_ttm_lag63d is not None else pd.Series(np.nan, index=self.p.securities)),
            "debt_asset_ratio": _safe_div(current("total_liab"), assets),
            "eps_ttm": _rank(_safe_div(ttm("net_profit_parent"), current("total_share"))),
            "financial_leverage": _rank(_safe_div(assets, equity)),
            "gpm_ttm": _rank(gpm_ttm),
            "icr": _rank(_safe_div(ttm("ebit"), ttm("fin_exp"))),
            "income_tax_yoy": _rank(self._growth("income_tax", "ttm", "ttm_year_ago")),
            "np_to_inventory_yoy": _rank(self._ratio_growth("net_profit", "inventories")),
            "npm_q": _rank(npm_q),
            "quality_composite": quality,
            "ar_ap_to_revenue": _rank(_safe_div(
                current("adv_receipts").fillna(0)
                - current("prepayment").fillna(0),
                current("revenue"),
            )),
            "asset_turnover": _rank(asset_turnover),
            "delta_current_ratio": _rank(current_ratio - current_ratio_yoy),
            "delta_de": _rank(debt_equity - debt_equity_yoy),
            "gpm_q": _rank(_safe_div(current("revenue") - current("oper_cost"), current("revenue"))),
            "cash_profit_ratio": _rank(_safe_div(ttm("operating_cashflow") - ttm("net_profit"), ttm("net_profit"))),
            "delta_opm": _rank(opm_ttm - opm_yoy),
            "eps_q": _rank(current("basic_eps")),
            "eps_y": _rank(annual("basic_eps")),
            "delta_npm": _rank(npm_ttm - npm_yoy),
            "market_value_leverage": _rank(_safe_div(self.p.total_mv - current("total_ncl"), self.p.total_mv)),
            "npm_y": _rank(_safe_div(annual("net_profit"), annual("revenue"))),
            "opm_y": _rank(_safe_div(annual("operate_profit"), annual("revenue"))),
            "quick_ratio": quick_ratio,
            "delta_gpm": _rank(gpm_ttm - gpm_yoy),
            "gpm_y": _rank(_safe_div(annual("revenue") - annual("oper_cost"), annual("revenue"))),
            "np_to_total_expenses_yoy": _rank(_safe_div(_safe_div(current("net_profit"), total_expenses_q), _safe_div(year_ago("net_profit"), total_expenses_yoy)) - 1),
            "np_to_deferred_tax_yoy": _rank(self._ratio_growth("net_profit", "defer_tax_assets")),
            "roe_y": _safe_div(annual("net_profit_parent"), annual("equity")),
            "roa_q": _rank(_safe_div(current("net_profit"), assets)),
            "gpm_qoq": _rank(_safe_div(gpm_ttm, gpm_prev) - 1),
            "delta_inventory_turnover": _rank(inventory_turnover - inventory_turnover_yoy),
            "delta_roa": _rank(roa - roa_yoy),
            "fixed_asset_turnover": _rank(_safe_div(revenue_ttm, current("fix_assets"))),
            "npm_ttm": _rank(npm_ttm),
            "opm_ttm": _rank(opm_ttm),
            "receivable_turnover": _rank(_safe_div(revenue_ttm, current("accounts_receiv"))),
            "cfcr": _rank(_safe_div(ttm("operating_cashflow"), ttm("fin_exp"))),
            "delta_cash_ratio": _rank(cash_ratio - cash_ratio_yoy),
            "lra_yoy": _rank(self._growth("longterm_receivable", "current", "year_ago")),
            "np_to_fixed_assets_yoy": _rank(self._ratio_growth("net_profit", "fix_assets")),
            "np_to_salary_yoy": _rank(self._ratio_growth("net_profit", "staff_paid", ttm=True)),
            "npm_q_qoq": _rank(_safe_div(npm_q, npm_prev_q) - 1),
            "npm_tsh": _rank(_safe_div(ttm("net_profit_parent"), (equity + previous("equity")) / 2)),
            "npm_ttm_qoq": _rank(_safe_div(npm_ttm, npm_prev) - 1),
            "cash_ratio": _rank(cash_ratio),
            "current_ratio": current_ratio,
            "de": debt_equity,
            "delta_asset_turnover": _rank(asset_turnover - asset_turnover_yoy),
            "delta_quick_ratio": _rank(quick_ratio - quick_ratio_yoy),
            "delta_roe": _rank(roe - roe_yoy),
            "inventory_turnover": _rank(inventory_turnover),
            "roa_ttm": _rank(roa),
            "roe_ttm": roe,
            "tax_surcharge_yoy": _rank(self._growth("biz_tax_surchg", "ttm", "ttm_year_ago")),
            "equity_turnover": _rank(_safe_div(revenue_ttm, equity)),
            "expenses_to_equity_yoy": _rank(_safe_div(_safe_div(total_expenses_q, equity_parent), _safe_div(total_expenses_yoy, year_ago("equity_parent"))) - 1),
            "roa_y": _rank(_safe_div(annual("net_profit"), annual("total_assets"))),
            "opt_tpro": _rank(_safe_div(current("operate_profit"), current("total_profit"))),
        }

    def _value_factors(self) -> dict[str, pd.Series]:
        ttm = lambda metric: self.v("ttm", metric)
        current = lambda metric: self.v("current", metric)
        annual = lambda metric: self.v("annual", metric)
        annual5 = lambda metric: self.v("annual_five_year_ago", metric)
        mean5 = lambda metric: self.v("five_year_mean", metric)
        market = self.p.total_mv
        eps_ttm = _safe_div(ttm("net_profit_parent"), current("total_share"))
        eps_growth_5y = np.power(
            _safe_div(annual("basic_eps"), annual5("basic_eps")), 1 / 5
        ) - 1
        dividend = (
            self.p.dividend_cash_3y.reindex(self.p.securities)
            if self.p.dividend_cash_3y is not None
            else pd.Series(np.nan, index=self.p.securities)
        ).fillna(0)
        return {
            "dividend_yield_3y_avg": _safe_div(dividend / 3, self.p.close),
            "pegh5": -_rank(_safe_div(self.p.close, eps_growth_5y * eps_ttm)),
            "etp5": _rank(_safe_div(mean5("net_profit"), mean5("market_cap"))),
            "ncf_to_market": _safe_div(ttm("financing_cashflow") + ttm("investing_cashflow") + ttm("operating_cashflow"), market),
            "fcf_to_market": _safe_div(ttm("operating_cashflow") - ttm("investing_cash_outflow"), market),
            "ebitda_to_market": _safe_div(ttm("ebitda"), market),
            "earnings_to_price": _safe_div(ttm("net_profit_parent"), market),
            "book_to_market": _safe_div(current("equity_parent") + current("defer_tax_assets"), market),
            "earnings_cut_to_market": _safe_div(ttm("profit_dedt"), market),
            "ocf_to_market": _safe_div(ttm("operating_cashflow"), market),
            "sales_to_market": _safe_div(current("revenue"), market),
        }

    def evaluate_latest(self) -> dict[str, pd.Series]:
        values: dict[str, pd.Series] = {}
        for group in (
            self._growth_factors(), self._quality_factors(), self._value_factors(),
        ):
            duplicate = set(values).intersection(group)
            if duplicate:
                raise RuntimeError(f"duplicate financial factor producer: {sorted(duplicate)}")
            values.update(group)
        return {
            name: value.reindex(self.p.securities).replace([np.inf, -np.inf], np.nan)
            for name, value in values.items()
        }
