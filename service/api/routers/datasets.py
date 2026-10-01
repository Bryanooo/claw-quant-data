"""Dataset discovery, querying and freshness endpoints."""

from datetime import date

from fastapi import APIRouter, Query, Request

from service.api.dependencies import (
    CanonicalEquityActionServiceDependency,
    CanonicalEquityDataServiceDependency,
    CanonicalEquityEventServiceDependency,
    CanonicalFundDataServiceDependency,
    CanonicalIndexDataServiceDependency,
    CanonicalMarketDataServiceDependency,
    DataServiceDependency,
)
from service.api.schemas import (
    CanonicalEquityBusinessSegmentsResponse,
    CanonicalEquityPledgesResponse,
    CanonicalEquityRestrictedReleasesResponse,
    CanonicalEquityRiskAlertsResponse,
    CanonicalEquityShareholdersResponse,
    CanonicalEquitySuspensionsResponse,
    CanonicalEquityDividendsResponse,
    CanonicalEquityFinancialPeriodsResponse,
    CanonicalEquityFinancialMetricsResponse,
    CanonicalEquityHolderCountsResponse,
    CanonicalEquityPerformanceUpdatesResponse,
    CanonicalEquityProfilesResponse,
    CanonicalEquityRepurchasesResponse,
    CanonicalEquityTtmFinancialsResponse,
    CanonicalEquityValuationsResponse,
    CanonicalFundNavResponse,
    CanonicalFundDividendsResponse,
    CanonicalFundManagersResponse,
    CanonicalFundProfilesResponse,
    CanonicalFundStockHoldingsResponse,
    CanonicalIndexConstituentsResponse,
    CanonicalIndexProfilesResponse,
    CanonicalMarketBarsResponse,
    CanonicalTradingSessionsResponse,
    DatasetDescription,
    DatasetSummary,
    FreshnessItem,
    RecordsResponse,
)
from service.data_service.source_policy import (
    source_policy_catalog,
    source_policy_summary,
)
from service.data_service.provider_equivalence import (
    financial_tushare_catalog,
    financial_tushare_summary,
    tushare_financial_reverse_catalog,
    tushare_financial_reverse_summary,
)

router = APIRouter(prefix="/v1/data", tags=["data"])

_STANDARD_QUERY_PARAMETERS = {
    "date",
    "start_date",
    "end_date",
    "limit",
    "offset",
    "include_total",
    "as_of",
    "filter_mode",
    "cursor",
}


@router.get("/datasets", response_model=list[DatasetSummary])
def list_datasets(
    service: DataServiceDependency,
) -> list[dict]:
    return service.list_datasets()


@router.get("/freshness", response_model=list[FreshnessItem])
def get_freshness(
    service: DataServiceDependency,
    dataset: str | None = None,
) -> list[dict]:
    return service.freshness(dataset)


@router.get("/source-priorities")
def get_source_priorities(
    dependency_class: str | None = None,
    equivalence_class: str | None = None,
    requires_financial_data: bool | None = None,
    current_token_ready: bool | None = None,
    namespace: str | None = None,
    limit: int = Query(default=500, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> dict:
    """Expose reviewed DB-first/quota-source precedence for every FD route."""
    policies = source_policy_catalog()
    filtered = list(policies)
    if dependency_class:
        filtered = [
            item for item in filtered
            if item.dependency_class == dependency_class
        ]
    if requires_financial_data is not None:
        filtered = [
            item for item in filtered
            if item.requires_financial_data is requires_financial_data
        ]
    if equivalence_class:
        filtered = [
            item for item in filtered
            if item.as_dict()["provider_equivalence"]["equivalence_class"]
            == equivalence_class
        ]
    if current_token_ready is not None:
        filtered = [
            item for item in filtered
            if item.as_dict()["provider_equivalence"]["current_token_ready"]
            is current_token_ready
        ]
    if namespace:
        normalized_namespace = namespace.strip("/")
        filtered = [
            item for item in filtered
            if len(item.route.split("/")) > 3
            and item.route.split("/")[3] == normalized_namespace
        ]
    total = len(filtered)
    return {
        "policy": "local canonical DB first; quota source only by explicit policy",
        "semantics": {
            "financial_data_required_now": (
                "routes whose capability currently has no local canonical equivalent, "
                "including explicit real-time products"
            ),
            "no_local_canonical_warning": (
                "no local canonical equivalent does not prove that Tushare has no "
                "semantically related endpoint; it may also indicate an unmapped gap"
            ),
            "provider_equivalence": (
                "vendor capability is classified independently from current token "
                "permission and local canonical implementation"
            ),
        },
        "summary": source_policy_summary(policies),
        "provider_equivalence_summary": financial_tushare_summary(
            financial_tushare_catalog()
        ),
        "page": {
            "limit": limit,
            "offset": offset,
            "total": total,
            "has_more": offset + limit < total,
        },
        "items": [item.as_dict() for item in filtered[offset:offset + limit]],
    }


@router.get("/source-priorities/tushare-endpoints")
def get_tushare_financial_mapping(
    mapping_status: str | None = None,
    permission: str | None = None,
    collectable: bool | None = None,
    query: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> dict:
    """Expose the reverse mapping for every audited Tushare contract."""
    all_items = tushare_financial_reverse_catalog()
    items = list(all_items)
    if mapping_status:
        items = [
            item for item in items
            if item["mapping_status"] == mapping_status
        ]
    if permission:
        items = [item for item in items if item["permission"] == permission]
    if collectable is not None:
        items = [
            item for item in items
            if item["collectable"] is collectable
        ]
    if query:
        normalized = query.strip().lower()
        items = [
            item for item in items
            if normalized in " ".join((
                item["api_name"],
                item["title"],
                *item["full_equivalence_routes"],
                *item["partial_overlap_routes"],
            )).lower()
        ]
    total = len(items)
    return {
        "summary": tushare_financial_reverse_summary(all_items),
        "page": {
            "limit": limit,
            "offset": offset,
            "total": total,
            "has_more": offset + limit < total,
        },
        "items": items[offset:offset + limit],
    }


@router.get(
    "/canonical/market-bars",
    response_model=CanonicalMarketBarsResponse,
)
def canonical_market_bars(
    service: CanonicalMarketDataServiceDependency,
    symbols: list[str] = Query(...),
    start_date: date = Query(...),
    end_date: date = Query(...),
    allow_quota_fallback: bool = True,
) -> dict:
    """Return canonical A-share daily bars, reading local DB before quota data."""
    return service.daily_bars(
        symbols=symbols,
        start_date=start_date,
        end_date=end_date,
        allow_quota_fallback=allow_quota_fallback,
    )


@router.get(
    "/canonical/trading-sessions",
    response_model=CanonicalTradingSessionsResponse,
)
def canonical_trading_sessions(
    service: CanonicalMarketDataServiceDependency,
    symbol: str,
    start_date: date = Query(...),
    end_date: date = Query(...),
    allow_quota_fallback: bool = True,
) -> dict:
    """Return canonical A-share open sessions with a bounded quota fallback."""
    return service.trading_days(
        symbol=symbol,
        start_date=start_date,
        end_date=end_date,
        allow_quota_fallback=allow_quota_fallback,
    )


@router.get(
    "/canonical/fund-profiles",
    response_model=CanonicalFundProfilesResponse,
)
def canonical_fund_profiles(
    service: CanonicalFundDataServiceDependency,
    symbols: list[str] = Query(...),
    allow_quota_fallback: bool = True,
) -> dict:
    """Return canonical fund profiles, reading local DB before quota data."""
    return service.profiles(
        symbols=symbols,
        allow_quota_fallback=allow_quota_fallback,
    )


@router.get(
    "/canonical/fund-nav",
    response_model=CanonicalFundNavResponse,
)
def canonical_fund_nav(
    service: CanonicalFundDataServiceDependency,
    symbols: list[str] = Query(...),
    start_date: date = Query(...),
    end_date: date = Query(...),
    allow_quota_fallback: bool = True,
) -> dict:
    """Return canonical fund NAV records with conservative gap semantics."""
    return service.nav(
        symbols=symbols,
        start_date=start_date,
        end_date=end_date,
        allow_quota_fallback=allow_quota_fallback,
    )


@router.get(
    "/canonical/fund-stock-holdings",
    response_model=CanonicalFundStockHoldingsResponse,
)
def canonical_fund_stock_holdings(
    service: CanonicalFundDataServiceDependency,
    symbols: list[str] = Query(...),
    report_dates: list[date] = Query(...),
    allow_quota_fallback: bool = True,
) -> dict:
    """Return canonical disclosed fund stock holdings by quarter end."""
    return service.stock_holdings(
        symbols=symbols,
        report_dates=report_dates,
        allow_quota_fallback=allow_quota_fallback,
    )


@router.get(
    "/canonical/fund-dividends",
    response_model=CanonicalFundDividendsResponse,
)
def canonical_fund_dividends(
    service: CanonicalFundDataServiceDependency,
    symbols: list[str] = Query(...),
    start_date: date = Query(...),
    end_date: date = Query(...),
    allow_quota_fallback: bool = True,
) -> dict:
    """Return fund cash distributions normalized to CNY per fund unit."""
    return service.dividends(
        symbols=symbols, start_date=start_date, end_date=end_date,
        allow_quota_fallback=allow_quota_fallback,
    )


@router.get(
    "/canonical/fund-managers",
    response_model=CanonicalFundManagersResponse,
)
def canonical_fund_managers(
    service: CanonicalFundDataServiceDependency,
    symbols: list[str] = Query(...),
    allow_quota_fallback: bool = True,
) -> dict:
    """Return fund-manager tenures with normalized dates and provenance."""
    return service.managers(
        symbols=symbols, allow_quota_fallback=allow_quota_fallback,
    )


@router.get(
    "/canonical/index-profiles",
    response_model=CanonicalIndexProfilesResponse,
)
def canonical_index_profiles(
    service: CanonicalIndexDataServiceDependency,
    symbols: list[str] = Query(...),
    allow_quota_fallback: bool = True,
) -> dict:
    """Return canonical SH/SZ index identity and base information."""
    return service.profiles(
        symbols=symbols, allow_quota_fallback=allow_quota_fallback,
    )


@router.get(
    "/canonical/index-constituents",
    response_model=CanonicalIndexConstituentsResponse,
)
def canonical_index_constituents(
    service: CanonicalIndexDataServiceDependency,
    symbols: list[str] = Query(...),
    update_dates: list[date] = Query(...),
    allow_quota_fallback: bool = True,
) -> dict:
    """Return weighted index constituents for explicit observation dates."""
    return service.constituents(
        symbols=symbols, update_dates=update_dates,
        allow_quota_fallback=allow_quota_fallback,
    )


@router.get(
    "/canonical/equity-profiles",
    response_model=CanonicalEquityProfilesResponse,
)
def canonical_equity_profiles(
    service: CanonicalEquityDataServiceDependency,
    symbols: list[str] = Query(...),
    allow_quota_fallback: bool = True,
) -> dict:
    """Return canonical A-share identities from local DB or bounded fallback."""
    return service.profiles(
        symbols=symbols,
        allow_quota_fallback=allow_quota_fallback,
    )


@router.get(
    "/canonical/equity-valuations",
    response_model=CanonicalEquityValuationsResponse,
)
def canonical_equity_valuations(
    service: CanonicalEquityDataServiceDependency,
    symbols: list[str] = Query(...),
    start_date: date = Query(...),
    end_date: date = Query(...),
    allow_quota_fallback: bool = True,
) -> dict:
    """Return daily A-share valuation facts with explicit unit semantics."""
    return service.valuations(
        symbols=symbols,
        start_date=start_date,
        end_date=end_date,
        allow_quota_fallback=allow_quota_fallback,
    )


@router.get(
    "/canonical/equity-financial-periods",
    response_model=CanonicalEquityFinancialPeriodsResponse,
)
def canonical_equity_financial_periods(
    service: CanonicalEquityDataServiceDependency,
    symbols: list[str] = Query(...),
    report_dates: list[date] = Query(...),
    allow_quota_fallback: bool = True,
) -> dict:
    """Return cumulative financial statements with section-level provenance."""
    return service.financial_periods(
        symbols=symbols,
        report_dates=report_dates,
        allow_quota_fallback=allow_quota_fallback,
    )


@router.get(
    "/canonical/equity-performance-updates",
    response_model=CanonicalEquityPerformanceUpdatesResponse,
)
def canonical_equity_performance_updates(
    service: CanonicalEquityEventServiceDependency,
    symbols: list[str] = Query(...),
    report_dates: list[date] = Query(...),
    allow_quota_fallback: bool = True,
) -> dict:
    """Return forecasts and preliminary results for explicit report periods."""
    return service.performance_updates(
        symbols=symbols,
        report_dates=report_dates,
        allow_quota_fallback=allow_quota_fallback,
    )


@router.get(
    "/canonical/equity-financial-metrics",
    response_model=CanonicalEquityFinancialMetricsResponse,
)
def canonical_equity_financial_metrics(
    service: CanonicalEquityEventServiceDependency,
    symbols: list[str] = Query(...),
    report_dates: list[date] = Query(...),
    allow_quota_fallback: bool = True,
) -> dict:
    """Return core profitability, growth, solvency and efficiency metrics."""
    return service.financial_metrics(
        symbols=symbols,
        report_dates=report_dates,
        allow_quota_fallback=allow_quota_fallback,
    )


@router.get(
    "/canonical/equity-ttm-financials",
    response_model=CanonicalEquityTtmFinancialsResponse,
)
def canonical_equity_ttm_financials(
    service: CanonicalEquityEventServiceDependency,
    symbols: list[str] = Query(...),
    report_dates: list[date] = Query(...),
    allow_quota_fallback: bool = True,
) -> dict:
    """Return locally derived or provider-reported rolling twelve-month facts."""
    return service.ttm_financials(
        symbols=symbols,
        report_dates=report_dates,
        allow_quota_fallback=allow_quota_fallback,
    )


@router.get(
    "/canonical/equity-dividends",
    response_model=CanonicalEquityDividendsResponse,
)
def canonical_equity_dividends(
    service: CanonicalEquityEventServiceDependency,
    symbols: list[str] = Query(...),
    report_dates: list[date] = Query(...),
    allow_quota_fallback: bool = True,
) -> dict:
    """Return dividend proposals for explicit fiscal report periods."""
    return service.dividends(
        symbols=symbols,
        report_dates=report_dates,
        allow_quota_fallback=allow_quota_fallback,
    )


@router.get(
    "/canonical/equity-repurchases",
    response_model=CanonicalEquityRepurchasesResponse,
)
def canonical_equity_repurchases(
    service: CanonicalEquityEventServiceDependency,
    symbols: list[str] = Query(...),
    start_date: date = Query(...),
    end_date: date = Query(...),
    allow_quota_fallback: bool = True,
) -> dict:
    """Return bounded share-repurchase plans and progress events."""
    return service.repurchases(
        symbols=symbols,
        start_date=start_date,
        end_date=end_date,
        allow_quota_fallback=allow_quota_fallback,
    )


@router.get(
    "/canonical/equity-holder-counts",
    response_model=CanonicalEquityHolderCountsResponse,
)
def canonical_equity_holder_counts(
    service: CanonicalEquityEventServiceDependency,
    symbols: list[str] = Query(...),
    start_date: date = Query(...),
    end_date: date = Query(...),
    allow_quota_fallback: bool = True,
) -> dict:
    """Return shareholder-count observations with explicit date semantics."""
    return service.holder_counts(
        symbols=symbols,
        start_date=start_date,
        end_date=end_date,
        allow_quota_fallback=allow_quota_fallback,
    )


@router.get(
    "/canonical/equity-business-segments",
    response_model=CanonicalEquityBusinessSegmentsResponse,
)
def canonical_equity_business_segments(
    service: CanonicalEquityEventServiceDependency,
    symbols: list[str] = Query(...),
    report_dates: list[date] = Query(...),
    classifications: list[str] = Query(...),
    allow_quota_fallback: bool = True,
) -> dict:
    """Return business composition by explicit report period and dimension."""
    return service.business_segments(
        symbols=symbols,
        report_dates=report_dates,
        classifications=classifications,
        allow_quota_fallback=allow_quota_fallback,
    )


@router.get(
    "/canonical/equity-shareholders",
    response_model=CanonicalEquityShareholdersResponse,
)
def canonical_equity_shareholders(
    service: CanonicalEquityActionServiceDependency,
    symbols: list[str] = Query(...),
    report_dates: list[date] = Query(...),
    allow_quota_fallback: bool = True,
) -> dict:
    """Return disclosed major shareholders for explicit quarter ends."""
    return service.shareholders(
        symbols=symbols, report_dates=report_dates,
        allow_quota_fallback=allow_quota_fallback,
    )


@router.get(
    "/canonical/equity-restricted-releases",
    response_model=CanonicalEquityRestrictedReleasesResponse,
)
def canonical_equity_restricted_releases(
    service: CanonicalEquityActionServiceDependency,
    symbols: list[str] = Query(...),
    start_date: date = Query(...),
    end_date: date = Query(...),
    allow_quota_fallback: bool = True,
) -> dict:
    """Return restricted-share releases and their supply-pressure ratios."""
    return service.restricted_releases(
        symbols=symbols, start_date=start_date, end_date=end_date,
        allow_quota_fallback=allow_quota_fallback,
    )


@router.get(
    "/canonical/equity-pledges",
    response_model=CanonicalEquityPledgesResponse,
)
def canonical_equity_pledges(
    service: CanonicalEquityActionServiceDependency,
    symbols: list[str] = Query(...),
    start_date: date = Query(...),
    end_date: date = Query(...),
    allow_quota_fallback: bool = True,
) -> dict:
    """Return equity pledge/freeze events with explicit source provenance."""
    return service.pledges(
        symbols=symbols, start_date=start_date, end_date=end_date,
        allow_quota_fallback=allow_quota_fallback,
    )


@router.get(
    "/canonical/equity-risk-alerts",
    response_model=CanonicalEquityRiskAlertsResponse,
)
def canonical_equity_risk_alerts(
    service: CanonicalEquityActionServiceDependency,
    symbols: list[str] = Query(...),
    start_date: date = Query(...),
    end_date: date = Query(...),
    allow_quota_fallback: bool = True,
) -> dict:
    """Return ST/delisting-risk status episodes with source provenance."""
    return service.risk_alerts(
        symbols=symbols, start_date=start_date, end_date=end_date,
        allow_quota_fallback=allow_quota_fallback,
    )


@router.get(
    "/canonical/equity-suspensions",
    response_model=CanonicalEquitySuspensionsResponse,
)
def canonical_equity_suspensions(
    service: CanonicalEquityActionServiceDependency,
    symbols: list[str] = Query(...),
    start_date: date = Query(...),
    end_date: date = Query(...),
    allow_quota_fallback: bool = True,
) -> dict:
    """Return trading suspension and resumption events."""
    return service.suspensions(
        symbols=symbols, start_date=start_date, end_date=end_date,
        allow_quota_fallback=allow_quota_fallback,
    )


@router.get("/datasets/{dataset_name}", response_model=DatasetDescription)
def describe_dataset(
    dataset_name: str,
    service: DataServiceDependency,
) -> dict:
    return service.describe_dataset(dataset_name)


@router.get("/datasets/{dataset_name}/records", response_model=RecordsResponse)
def query_dataset(
    dataset_name: str,
    request: Request,
    service: DataServiceDependency,
    date_value: str | None = Query(default=None, alias="date"),
    start_date: str | None = None,
    end_date: str | None = None,
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    include_total: bool = False,
    as_of: str | None = None,
    filter_mode: str = Query(default="standard", pattern="^(standard|advanced)$"),
    cursor: str | None = None,
) -> dict:
    exact_filters: dict[str, str] = {}
    for name, value in request.query_params.multi_items():
        if name not in _STANDARD_QUERY_PARAMETERS:
            exact_filters[name] = value

    return service.query_dataset(
        dataset_name,
        exact_filters=exact_filters,
        date_value=date_value,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
        offset=offset,
        include_total=include_total,
        as_of=as_of,
        filter_mode=filter_mode,
        cursor=cursor,
    )
