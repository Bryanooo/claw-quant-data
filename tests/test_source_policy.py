from service.data_service.registry import DATASETS
from service.data_service.source_policy import (
    FINANCIAL_DATA_FIRST,
    LOCAL_DB_FIRST,
    FINANCIAL_ROUTE_LOCAL_DATASETS,
    dataset_fallback_routes,
    source_policy_catalog,
    source_policy_summary,
)
from service.source_connectors.financial_data_catalog import FINANCIAL_DATA_ROUTES
from service.api.routers.datasets import get_source_priorities


def test_every_financial_route_has_an_explicit_source_policy():
    policies = source_policy_catalog()

    assert len(policies) == len(FINANCIAL_DATA_ROUTES) == 163
    assert {item.route for item in policies} == FINANCIAL_DATA_ROUTES
    assert {item.preferred_read for item in policies} == {
        LOCAL_DB_FIRST, FINANCIAL_DATA_FIRST,
    }


def test_financial_data_dependency_classes_are_complete_and_disjoint():
    policies = source_policy_catalog()
    summary = source_policy_summary(policies)

    assert summary == {
        "routes": 163,
        "local_db_first": 57,
        "financial_data_first": 106,
        "financial_data_required_now": 106,
        "active_implicit_fallbacks": 0,
        "active_canonical_fallbacks": 29,
        "local_first_canonical_fallback_ready": 29,
        "local_overlap_adapter_pending": 28,
        "financial_data_realtime_required": 4,
        "financial_data_primary_no_local_canonical": 102,
    }
    assert sum(
        summary[key]
        for key in (
            "local_first_canonical_fallback_ready",
            "local_overlap_adapter_pending",
            "financial_data_realtime_required",
            "financial_data_primary_no_local_canonical",
        )
    ) == summary["routes"]
    assert all(item.as_dict()["dependency_class"] for item in policies)


def test_source_priority_api_can_filter_required_and_realtime_routes():
    required = get_source_priorities(
        dependency_class=None,
        requires_financial_data=True,
        namespace=None,
        limit=500,
        offset=0,
    )
    realtime = get_source_priorities(
        dependency_class="financial_data_realtime_required",
        requires_financial_data=None,
        namespace=None,
        limit=500,
        offset=0,
    )
    assert required["page"]["total"] == 106
    assert len(required["items"]) == 106
    assert realtime["page"]["total"] == 4
    assert {item["route"] for item in realtime["items"]} == {
        "/api/v1/common/trading-state",
        "/api/v1/quote/auction-snapshot",
        "/api/v1/quote/basic-snapshot",
        "/api/v1/quote/derived-snapshot",
    }


def test_local_first_routes_reference_real_canonical_datasets():
    datasets = {item.name for item in DATASETS.list()}
    referenced = {
        dataset
        for route_datasets in FINANCIAL_ROUTE_LOCAL_DATASETS.values()
        for dataset in route_datasets
    }

    assert referenced <= datasets
    assert dataset_fallback_routes("stock_daily") == (
        "/api/v1/onecode/query",
        "/api/v1/quote/kline-batch",
        "/api/v1/stock/tech-indicators",
        "/api/v1/stock/tech-patterns",
    )


def test_only_reviewed_financial_fallbacks_are_claimed_ready():
    local_first = [
        item for item in source_policy_catalog()
        if item.preferred_read == LOCAL_DB_FIRST
    ]

    assert local_first
    ready = {
        item.route: item.adapter_status
        for item in local_first
        if item.adapter_status.startswith("partial_ready")
    }
    assert ready == {
        "/api/v1/common/trading-day": "partial_ready_a_share",
        "/api/v1/fund/fund-archive": (
            "partial_ready_common_profile_fields"
        ),
        "/api/v1/fund/net-value": "partial_ready_bounded_nav_range",
        "/api/v1/fund/stock-portfolio": (
            "partial_ready_quarterly_stock_holdings"
        ),
        "/api/v1/fund/dividend": "partial_ready_fund_cash_dividends",
        "/api/v1/fund/fund-manager": "partial_ready_fund_manager_tenures",
        "/api/v1/index_fnd/index-profile-basic-info": (
            "partial_ready_sh_sz_index_profile"
        ),
        "/api/v1/index_fnd/index-constituents-list-weight": (
            "partial_ready_sh_sz_weighted_constituents"
        ),
        "/api/v1/quote/kline-batch": (
            "partial_ready_a_share_daily_unadjusted"
        ),
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
