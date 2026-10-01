"""Public service-to-data lineage used by API discovery and the dashboard.

This module deliberately describes *business service* dependencies.  It is
not a second dataset registry: dataset source ownership still comes from the
registry and is joined at catalog-build time.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from service.research.readiness import RESEARCH_DATA_CONTRACTS


def _lineage(
    datasets: Iterable[str] = (),
    *,
    fallback_routes: Iterable[str] = (),
    derivation: str | None = None,
    origin: str = "canonical_db",
    read_strategy: str = "local_db_first",
    dependency_scope: str = "fixed",
) -> dict[str, Any]:
    return {
        "data_origin": origin,
        "local_datasets": sorted(set(datasets)),
        "fallback_routes": list(fallback_routes),
        "derivation": derivation,
        "read_strategy": read_strategy,
        "dependency_scope": dependency_scope,
        # Financial Data has a quota. Research services never silently query
        # it; only reviewed canonical adapters may perform bounded fallback.
        "runtime_external_query": bool(fallback_routes),
    }


CANONICAL_ENDPOINT_LINEAGE: dict[str, dict[str, Any]] = {
    "/api/v1/data/canonical/market-bars": _lineage(
        ["stock_daily"], fallback_routes=["/api/v1/quote/kline-batch"]
    ),
    "/api/v1/data/canonical/trading-sessions": _lineage(
        ["trade_calendar"], fallback_routes=["/api/v1/common/trading-day"]
    ),
    "/api/v1/data/canonical/equity-profiles": _lineage(
        ["stock_basic"], fallback_routes=["/api/v1/stock_fnd/stock-basic-info"]
    ),
    "/api/v1/data/canonical/equity-valuations": _lineage(
        ["stock_daily_basic"],
        fallback_routes=["/api/v1/stock/daily-valuation-indicators"],
    ),
    "/api/v1/data/canonical/equity-financial-periods": _lineage(
        ["income", "balancesheet", "cashflow"],
        fallback_routes=[
            "/api/v1/stock_fnd/income-cashflow-acc",
            "/api/v1/stock_fnd/balance-sheet",
        ],
        derivation="merge cumulative income, balance-sheet and cash-flow facts by report period",
    ),
    "/api/v1/data/canonical/equity-performance-updates": _lineage(
        ["forecast", "express"],
        fallback_routes=[
            "/api/v1/stock_fnd/performance-forecast",
            "/api/v1/stock_fnd/prelim-acc",
        ],
    ),
    "/api/v1/data/canonical/equity-financial-metrics": _lineage(
        ["financial_indicator"],
        fallback_routes=["/api/v1/stock_fnd/growth-rates-acc"],
    ),
    "/api/v1/data/canonical/equity-ttm-financials": _lineage(
        ["income", "cashflow", "financial_indicator"],
        fallback_routes=["/api/v1/stock_fnd/metrics-ttm"],
        derivation="derive trailing-twelve-month facts from point-in-time cumulative reports",
    ),
    "/api/v1/data/canonical/equity-dividends": _lineage(
        ["dividend"], fallback_routes=["/api/v1/stock_fnd/dividend-details"]
    ),
    "/api/v1/data/canonical/equity-repurchases": _lineage(
        ["repurchase"], fallback_routes=["/api/v1/stock_fnd/buyback-plans"]
    ),
    "/api/v1/data/canonical/equity-holder-counts": _lineage(
        ["stk_holdernumber"], fallback_routes=["/api/v1/stock_fnd/holder-count"]
    ),
    "/api/v1/data/canonical/equity-business-segments": _lineage(
        ["fina_mainbz"],
        fallback_routes=[
            "/api/v1/stock_fnd/main-business-business",
            "/api/v1/stock_fnd/main-business-industry",
            "/api/v1/stock_fnd/main-business-product",
            "/api/v1/stock_fnd/main-business-region",
        ],
    ),
    "/api/v1/data/canonical/equity-shareholders": _lineage(
        ["top10_holders", "top10_floatholders"],
        fallback_routes=["/api/v1/stock_fnd/shareholder-list"],
    ),
    "/api/v1/data/canonical/equity-restricted-releases": _lineage(
        ["share_float"],
        fallback_routes=["/api/v1/stock_fnd/restricted-release-calendar"],
    ),
    "/api/v1/data/canonical/equity-pledges": _lineage(
        ["pledge_detail", "pledge_stat"],
        fallback_routes=["/api/v1/stock_sh_equity/freeze-pledge"],
    ),
    "/api/v1/data/canonical/equity-risk-alerts": _lineage(
        ["stk_alert", "stock_st"], fallback_routes=["/api/v1/stock/risk-alerts"]
    ),
    "/api/v1/data/canonical/equity-suspensions": _lineage(
        ["stock_suspend"], fallback_routes=["/api/v1/stock/suspend-resumption"]
    ),
    "/api/v1/data/canonical/fund-profiles": _lineage(
        ["fund_basic"], fallback_routes=["/api/v1/fund/fund-archive"]
    ),
    "/api/v1/data/canonical/fund-nav": _lineage(
        ["fund_nav"], fallback_routes=["/api/v1/fund/net-value"]
    ),
    "/api/v1/data/canonical/fund-stock-holdings": _lineage(
        ["fund_portfolio"], fallback_routes=["/api/v1/fund/stock-portfolio"]
    ),
    "/api/v1/data/canonical/fund-dividends": _lineage(
        ["fund_div"], fallback_routes=["/api/v1/fund/dividend"]
    ),
    "/api/v1/data/canonical/fund-managers": _lineage(
        ["fund_manager"], fallback_routes=["/api/v1/fund/fund-manager"]
    ),
    "/api/v1/data/canonical/index-profiles": _lineage(
        ["index_basic"],
        fallback_routes=["/api/v1/index_fnd/index-profile-basic-info"],
    ),
    "/api/v1/data/canonical/index-constituents": _lineage(
        ["index_weight"],
        fallback_routes=["/api/v1/index_fnd/index-constituents-list-weight"],
    ),
}


_RESEARCH_FIXED_DATASETS: dict[str, tuple[str, ...]] = {
    "/api/v1/research/macro/{theme}": (
        "cn_gdp", "cn_pmi", "cn_cpi", "cn_ppi", "cn_m", "sf_month",
        "shibor", "shibor_lpr",
    ),
    "/api/v1/research/stocks/{ts_code}/snapshot": (
        "stock_basic", "stock_daily", "stock_daily_basic", "moneyflow",
        "financial_indicator", "stock_limit", "stock_suspend",
    ),
    "/api/v1/research/stocks/{ts_code}/research-pack": (
        "stock_basic", "stock_company", "stock_daily", "stock_daily_basic",
        "adj_factor", "moneyflow", "cyq_perf", "margin_detail", "hk_hold",
        "block_trade", "stock_limit", "stock_suspend", "index_daily",
        "financial_indicator", "income", "balancesheet", "cashflow",
        "forecast", "express", "stk_holdernumber", "stk_holdertrade",
        "top10_holders", "top10_floatholders", "pledge_stat", "repurchase",
        "dividend", "major_news",
    ),
    "/api/v1/research/stocks/{ts_code}/sectors": (
        "ths_index", "ths_member", "dc_index", "dc_member", "tdx_index", "tdx_member",
    ),
    "/api/v1/research/stocks/{ts_code}/peers": (
        "ths_index", "ths_member", "dc_index", "dc_member", "tdx_index", "tdx_member",
    ),
    "/api/v1/research/sectors": ("ths_index", "dc_index", "tdx_index"),
    "/api/v1/research/sectors/{provider}/{sector_code}/snapshot": (
        "ths_index", "industry_daily", "ths_member", "moneyflow_cnt_ths",
        "dc_index", "dc_daily", "dc_member", "moneyflow_ind_dc",
        "tdx_index", "tdx_daily", "tdx_member",
    ),
    "/api/v1/research/sectors/{provider}/{sector_code}/members": (
        "ths_index", "ths_member", "dc_index", "dc_member", "tdx_index", "tdx_member",
    ),
    "/api/v1/research/sectors/{provider}/{sector_code}/research-pack": (
        "ths_index", "industry_daily", "ths_member", "moneyflow_cnt_ths",
        "dc_index", "dc_daily", "dc_member", "moneyflow_ind_dc",
        "tdx_index", "tdx_daily", "tdx_member",
    ),
    "/api/v1/research/investment-calendar": ("eco_cal", "fut_basic"),
    "/api/v1/research/investment-calendar/{event_date}": ("eco_cal", "fut_basic"),
}

_SYSTEM_RESEARCH_ENDPOINTS = {
    "/api/v1/research/capabilities": "service definitions and research lineage",
    "/api/v1/research/readiness": "V2 data states, freshness and strict coverage audits",
    "/api/v1/research/validation-set": "versioned end-to-end acceptance cases",
}


def _contract_datasets() -> dict[str, set[str]]:
    result: dict[str, set[str]] = {}
    for contract in RESEARCH_DATA_CONTRACTS:
        path = contract["path"]
        if contract["id"].startswith("instrument-technicals-"):
            path = "/api/v1/research/instruments/{asset_type}/{code}/technicals"
        result.setdefault(path, set()).update(
            dependency["dataset"] for dependency in contract["dependencies"]
        )
    return result


def research_endpoint_lineage(path: str) -> dict[str, Any]:
    if path in _SYSTEM_RESEARCH_ENDPOINTS:
        return _lineage(
            derivation=_SYSTEM_RESEARCH_ENDPOINTS[path],
            origin="system_metadata",
            read_strategy="metadata_only",
        )
    datasets = set(_RESEARCH_FIXED_DATASETS.get(path, ()))
    datasets.update(_contract_datasets().get(path, ()))
    return _lineage(
        datasets,
        derivation="Claw Quant deterministic research calculation over canonical local datasets",
        origin="claw_derived",
        read_strategy="derive_from_local_db",
    )


def endpoint_with_sources(
    endpoint: dict[str, Any],
    lineage: dict[str, Any],
    dataset_sources: dict[str, list[str]],
) -> dict[str, Any]:
    local_datasets = lineage["local_datasets"]
    upstream_sources = sorted(
        {
            source
            for dataset in local_datasets
            for source in dataset_sources.get(dataset, ["tushare"])
        }
    )
    if lineage["fallback_routes"]:
        upstream_sources.append("financial_data")
    return {
        **endpoint,
        **lineage,
        "upstream_sources": list(dict.fromkeys(upstream_sources)),
        "lineage_status": "complete",
    }
