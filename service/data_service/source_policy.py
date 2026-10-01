"""Reviewed source precedence for canonical external datasets.

The Financial Data provider exposes provider-native tools.  Those tools are
not interchangeable with the canonical datasets served by ``/v1/data``.  This
module records the reviewed overlap and, crucially, makes the quota policy
deterministic: local canonical data wins; Financial Data is used only when a
canonical adapter exists and the requested local slice is absent or stale.
"""

from __future__ import annotations

from dataclasses import dataclass

from service.source_connectors.financial_data_catalog import FINANCIAL_DATA_ROUTES


LOCAL_DB_FIRST = "local_db_first"
FINANCIAL_DATA_FIRST = "financial_data_first"


# Only declare an overlap when the local dataset can supply the same business
# fact (or the ingredients of the same deterministic derived fact).  A listed
# overlap does not itself activate read-through: field/symbol adapters must be
# contract-tested before ``adapter_status`` may become ``ready``.
FINANCIAL_ROUTE_LOCAL_DATASETS: dict[str, tuple[str, ...]] = {
    "/api/v1/common/symbol-by-cond": (
        "stock_basic", "fund_basic", "index_basic", "hk_basic", "us_basic",
        "sge_basic",
    ),
    "/api/v1/common/trading-day": (
        "trade_calendar", "hk_tradecal", "us_tradecal", "fut_trade_cal",
    ),
    "/api/v1/fund/dividend": ("fund_div",),
    "/api/v1/fund/fund-archive": ("fund_basic",),
    "/api/v1/fund/fund-company-info": ("fund_company",),
    "/api/v1/fund/fund-manager": ("fund_manager",),
    "/api/v1/fund/net-value": ("fund_nav", "fund_daily"),
    "/api/v1/fund/share-split": ("fund_adj",),
    "/api/v1/fund/stock-portfolio": ("fund_portfolio",),
    "/api/v1/fund_derived/benchmark-excess": (
        "fund_daily", "fund_nav", "index_daily",
    ),
    "/api/v1/fund_derived/risk-return": ("fund_daily", "fund_nav"),
    "/api/v1/index_fnd/index-constituents-list-weight": (
        "index_weight", "index_member_all",
    ),
    "/api/v1/index_fnd/index-profile-basic-info": ("index_basic",),
    "/api/v1/macro/data-query": (
        "cn_cpi", "cn_gdp", "cn_m", "cn_pmi", "cn_ppi", "sf_month",
        "shibor", "shibor_lpr", "libor", "hibor", "us_tbr", "us_tltr",
        "us_trltr", "us_trycr", "us_tycr",
    ),
    "/api/v1/onecode/query": (
        "stock_daily", "stock_daily_basic", "index_daily", "fund_daily",
        "fund_nav", "financial_indicator",
    ),
    "/api/v1/quote/capital-flow-range": (
        "moneyflow", "moneyflow_dc", "moneyflow_ths", "moneyflow_ind_dc",
        "moneyflow_ind_ths", "moneyflow_mkt_dc",
    ),
    "/api/v1/quote/kline-batch": (
        "stock_daily", "index_daily", "index_weekly", "index_monthly",
        "fund_daily", "hk_daily", "sge_daily", "fut_daily", "opt_daily",
        "cb_daily", "forex_daily",
    ),
    "/api/v1/sector/plate-component": (
        "ths_member", "dc_member", "tdx_member", "index_member_all",
    ),
    "/api/v1/sector/plate-list": (
        "ths_index", "dc_index", "tdx_index", "index_classify",
    ),
    "/api/v1/sector/sector-capital-flow": (
        "moneyflow_ind_dc", "moneyflow_ind_ths", "margin", "margin_detail",
    ),
    "/api/v1/sector/sector-valuation": ("index_dailybasic",),
    "/api/v1/stock/block-trading-details": ("block_trade",),
    "/api/v1/stock/component-list-belonged": (
        "index_member_all", "ths_member", "dc_member", "tdx_member",
    ),
    "/api/v1/stock/daily-valuation-indicators": ("stock_daily_basic",),
    "/api/v1/stock/risk-alerts": ("stk_alert", "stock_st"),
    "/api/v1/stock/sh-hold-stat": ("hk_hold", "stock_hsgt"),
    "/api/v1/stock/stock-index-constituents-list": (
        "index_member_all", "index_weight",
    ),
    "/api/v1/stock/suspend-resumption": ("stock_suspend",),
    "/api/v1/stock/tech-indicators": (
        "stock_daily", "adj_factor", "stk_factor", "stk_factor_pro",
    ),
    "/api/v1/stock/tech-patterns": ("stock_daily", "adj_factor"),
    "/api/v1/stock_fnd/balance-sheet": ("balancesheet",),
    "/api/v1/stock_fnd/broker-golden-stocks": ("broker_recommend",),
    "/api/v1/stock_fnd/buyback-plans": ("repurchase",),
    "/api/v1/stock_fnd/dividend-details": ("dividend",),
    "/api/v1/stock_fnd/dividend-record": ("dividend",),
    "/api/v1/stock_fnd/executive-compensation": ("stk_rewards",),
    "/api/v1/stock_fnd/growth-rates-acc": ("financial_indicator",),
    "/api/v1/stock_fnd/growth-rates-quarter": (
        "income", "cashflow", "financial_indicator",
    ),
    "/api/v1/stock_fnd/holder-count": ("stk_holdernumber",),
    "/api/v1/stock_fnd/income-cashflow-acc": ("income", "cashflow"),
    "/api/v1/stock_fnd/income-cashflow-single": ("income", "cashflow"),
    "/api/v1/stock_fnd/industry-classification": (
        "stock_basic", "index_classify",
    ),
    "/api/v1/stock_fnd/main-business-business": ("fina_mainbz",),
    "/api/v1/stock_fnd/main-business-industry": ("fina_mainbz",),
    "/api/v1/stock_fnd/main-business-product": ("fina_mainbz",),
    "/api/v1/stock_fnd/main-business-region": ("fina_mainbz",),
    "/api/v1/stock_fnd/metrics-ttm": ("financial_indicator",),
    "/api/v1/stock_fnd/performance-forecast": ("forecast",),
    "/api/v1/stock_fnd/prelim-acc": ("express",),
    "/api/v1/stock_fnd/prelim-balance": ("express",),
    "/api/v1/stock_fnd/prelim-quarter": ("express",),
    "/api/v1/stock_fnd/restricted-release-calendar": ("share_float",),
    "/api/v1/stock_fnd/shareholder-list": (
        "top10_holders", "top10_floatholders",
    ),
    "/api/v1/stock_fnd/stock-basic-info": ("stock_basic", "stock_company"),
    "/api/v1/stock_fnd/stock-rel-fund-holdings-top": ("fund_portfolio",),
    "/api/v1/stock_sh_equity/freeze-pledge": (
        "pledge_detail", "pledge_stat",
    ),
    "/api/v1/info/research-reports": ("report_rc",),
}


# These are genuinely live/provider-specific products.  They should consume
# quota only through an explicit real-time research capability, never as an
# invisible substitute for a completed historical DB query.
REALTIME_FINANCIAL_ROUTES = frozenset({
    "/api/v1/common/trading-state",
    "/api/v1/quote/auction-snapshot",
    "/api/v1/quote/basic-snapshot",
    "/api/v1/quote/derived-snapshot",
})

# Ready means a provider response is normalized into a versioned canonical
# contract and guarded by bounded inputs. It does not imply that every market,
# period or asset supported by the provider is ready.
READY_CANONICAL_ADAPTERS = {
    "/api/v1/common/trading-day": "partial_ready_a_share",
    "/api/v1/fund/fund-archive": "partial_ready_common_profile_fields",
    "/api/v1/fund/net-value": "partial_ready_bounded_nav_range",
    "/api/v1/fund/stock-portfolio": "partial_ready_quarterly_stock_holdings",
    "/api/v1/fund/dividend": "partial_ready_fund_cash_dividends",
    "/api/v1/fund/fund-manager": "partial_ready_fund_manager_tenures",
    "/api/v1/index_fnd/index-profile-basic-info": "partial_ready_sh_sz_index_profile",
    "/api/v1/index_fnd/index-constituents-list-weight": (
        "partial_ready_sh_sz_weighted_constituents"
    ),
    "/api/v1/quote/kline-batch": "partial_ready_a_share_daily_unadjusted",
    "/api/v1/stock/daily-valuation-indicators": (
        "partial_ready_a_share_daily_core_fields"
    ),
    "/api/v1/stock_fnd/stock-basic-info": (
        "partial_ready_a_share_identity_fields"
    ),
    "/api/v1/stock_fnd/income-cashflow-acc": (
        "partial_ready_a_share_cumulative_core_fields"
    ),
    "/api/v1/stock_fnd/balance-sheet": (
        "partial_ready_a_share_balance_core_fields"
    ),
    "/api/v1/stock_fnd/performance-forecast": (
        "partial_ready_a_share_core_forecast_fields"
    ),
    "/api/v1/stock_fnd/prelim-acc": (
        "partial_ready_a_share_cumulative_preliminary_fields"
    ),
    "/api/v1/stock_fnd/dividend-details": (
        "partial_ready_a_share_core_dividend_fields"
    ),
    "/api/v1/stock_fnd/buyback-plans": (
        "partial_ready_a_share_repurchase_plan_fields"
    ),
    "/api/v1/stock_fnd/holder-count": (
        "partial_ready_a_share_holder_count_fields"
    ),
    "/api/v1/stock_fnd/growth-rates-acc": (
        "partial_ready_a_share_core_financial_metrics"
    ),
    "/api/v1/stock_fnd/metrics-ttm": (
        "partial_ready_a_share_core_ttm_financials"
    ),
    "/api/v1/stock_fnd/main-business-business": (
        "partial_ready_a_share_business_segments"
    ),
    "/api/v1/stock_fnd/main-business-industry": (
        "partial_ready_a_share_business_segments"
    ),
    "/api/v1/stock_fnd/main-business-product": (
        "partial_ready_a_share_business_segments"
    ),
    "/api/v1/stock_fnd/main-business-region": (
        "partial_ready_a_share_business_segments"
    ),
    "/api/v1/stock_fnd/shareholder-list": (
        "partial_ready_a_share_major_shareholders"
    ),
    "/api/v1/stock_fnd/restricted-release-calendar": (
        "partial_ready_a_share_restricted_releases"
    ),
    "/api/v1/stock_sh_equity/freeze-pledge": (
        "partial_ready_a_share_pledge_events"
    ),
    "/api/v1/stock/risk-alerts": (
        "partial_ready_a_share_risk_alerts"
    ),
    "/api/v1/stock/suspend-resumption": (
        "partial_ready_a_share_suspensions"
    ),
}


@dataclass(frozen=True, slots=True)
class RouteSourcePolicy:
    route: str
    preferred_read: str
    local_datasets: tuple[str, ...]
    financial_data_role: str
    adapter_status: str
    local_scope: str
    reason: str

    @property
    def dependency_class(self) -> str:
        if self.route in REALTIME_FINANCIAL_ROUTES:
            return "financial_data_realtime_required"
        if not self.local_datasets:
            return "financial_data_primary_no_local_canonical"
        if self.adapter_status.startswith("partial_ready"):
            return "local_first_canonical_fallback_ready"
        return "local_overlap_adapter_pending"

    @property
    def requires_financial_data(self) -> bool:
        return self.dependency_class in {
            "financial_data_realtime_required",
            "financial_data_primary_no_local_canonical",
        }

    @property
    def public_access(self) -> str:
        if self.dependency_class == "local_first_canonical_fallback_ready":
            return "canonical_api_with_bounded_fallback"
        if self.dependency_class == "local_overlap_adapter_pending":
            return "local_dataset_or_explicit_provider_gateway"
        return "explicit_provider_gateway_only"

    def as_dict(self) -> dict:
        return {
            "route": self.route,
            "preferred_read": self.preferred_read,
            "local_datasets": list(self.local_datasets),
            "financial_data_role": self.financial_data_role,
            "adapter_status": self.adapter_status,
            "local_scope": self.local_scope,
            "reason": self.reason,
            "dependency_class": self.dependency_class,
            "requires_financial_data": self.requires_financial_data,
            "public_access": self.public_access,
        }


def route_source_policy(route: str) -> RouteSourcePolicy:
    if route not in FINANCIAL_DATA_ROUTES:
        raise KeyError(f"uncatalogued Financial Data route: {route}")
    local_datasets = FINANCIAL_ROUTE_LOCAL_DATASETS.get(route, ())
    if local_datasets:
        return RouteSourcePolicy(
            route=route,
            preferred_read=LOCAL_DB_FIRST,
            local_datasets=local_datasets,
            financial_data_role="quota_fallback_after_local_miss",
            # No provider-native response is allowed to leak into a canonical
            # response until symbol, date, unit and field mappings are tested.
            adapter_status=READY_CANONICAL_ADAPTERS.get(
                route, "adapter_required"
            ),
            local_scope=(
                "only requests whose market, asset, period and fields are covered "
                "by the listed canonical datasets"
            ),
            reason=(
                "已有定时入库的规范数据集；先验证本地切片，只有缺失或不新鲜且"
                "规范适配器已通过契约测试时才允许消耗 Financial Data 额度"
            ),
        )
    if route in REALTIME_FINANCIAL_ROUTES:
        reason = "实时产品没有等价的已持久化快照；必须显式请求实时能力"
        role = "explicit_realtime_query"
    else:
        reason = "当前没有等价的本地规范数据集；需先建立规范数据集或查询适配器"
        role = "primary_until_local_dataset_exists"
    return RouteSourcePolicy(
        route=route,
        preferred_read=FINANCIAL_DATA_FIRST,
        local_datasets=(),
        financial_data_role=role,
        adapter_status="canonical_dataset_required",
        local_scope="none",
        reason=reason,
    )


def source_policy_catalog() -> tuple[RouteSourcePolicy, ...]:
    return tuple(route_source_policy(route) for route in sorted(FINANCIAL_DATA_ROUTES))


def source_policy_summary(
    policies: tuple[RouteSourcePolicy, ...] | None = None,
) -> dict[str, int]:
    policies = source_policy_catalog() if policies is None else policies
    classes = {
        name: sum(item.dependency_class == name for item in policies)
        for name in (
            "local_first_canonical_fallback_ready",
            "local_overlap_adapter_pending",
            "financial_data_realtime_required",
            "financial_data_primary_no_local_canonical",
        )
    }
    return {
        "routes": len(policies),
        "local_db_first": sum(
            item.preferred_read == LOCAL_DB_FIRST for item in policies
        ),
        "financial_data_first": sum(
            item.preferred_read == FINANCIAL_DATA_FIRST for item in policies
        ),
        "financial_data_required_now": sum(
            item.requires_financial_data for item in policies
        ),
        "active_implicit_fallbacks": 0,
        "active_canonical_fallbacks": classes[
            "local_first_canonical_fallback_ready"
        ],
        **classes,
    }


def dataset_fallback_routes(dataset_name: str) -> tuple[str, ...]:
    return tuple(
        sorted(
            route
            for route, datasets in FINANCIAL_ROUTE_LOCAL_DATASETS.items()
            if dataset_name in datasets
        )
    )


def dataset_fallback_status(dataset_name: str) -> str:
    routes = dataset_fallback_routes(dataset_name)
    ready = [route for route in routes if route in READY_CANONICAL_ADAPTERS]
    if ready:
        return "partial_ready"
    return "adapter_required" if routes else "not_configured"
