"""Pydantic response contracts for the HTTP API."""

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ApiModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class LiveResponse(ApiModel):
    status: str
    service: str
    version: str


class ReadyResponse(ApiModel):
    status: str
    database: str


class DatasetSummary(ApiModel):
    name: str
    description: str
    category: str
    source: str
    source_ids: list[str] = Field(default_factory=list)
    merge_policy: str = "single_source"
    read_strategy: str = "local_db_first"
    fallback_source_ids: list[str] = Field(default_factory=list)
    fallback_status: str = "not_configured"
    date_column: str | None


class ColumnDescription(ApiModel):
    column_name: str
    data_type: str
    is_nullable: str


class DatasetDescription(DatasetSummary):
    table: str
    read_view: str | None = None
    freshness_table: str | None = None
    primary_keys: list[str]
    storage_semantics: str = "canonical_upsert"
    business_identity_fields: list[str] = Field(default_factory=list)
    identity_confidence: str = "database_constraint"
    allowed_filters: list[str]
    standard_filters: list[str] = Field(default_factory=list)
    advanced_filters: list[str] = Field(default_factory=list)
    availability_column: str | None = None
    max_page_size: int
    max_offset: int = 10_000
    fallback_endpoints: list[str] = Field(default_factory=list)
    columns: list[ColumnDescription]


class RecordsMeta(ApiModel):
    dataset: str
    source: str
    source_ids: list[str] = Field(default_factory=list)
    served_from: str = "local_db"
    read_strategy: str = "local_db_first"
    fallback_used: bool = False
    returned: int


class PageInfo(ApiModel):
    limit: int
    offset: int
    total: int | None = None
    next_cursor: str | None = None
    has_more: bool


class RecordsResponse(ApiModel):
    data: list[dict[str, Any]]
    meta: RecordsMeta
    page: PageInfo


class CanonicalMarketBar(ApiModel):
    instrument_id: str
    asset_type: Literal["stock"]
    period: Literal["day"]
    period_start: date
    period_end: date
    adjustment: Literal["none"]
    currency: Literal["CNY"]
    open: float | None = None
    high: float | None = None
    low: float | None = None
    close: float | None = None
    previous_close: float | None = None
    change: float | None = None
    return_pct: float | None = None
    volume: float | None = None
    volume_unit: Literal["share"]
    amount: float | None = None
    amount_unit: Literal["CNY"]
    source_id: Literal["tushare", "financial_data"]
    source_dataset: str


class CanonicalMarketBarsResponse(ApiModel):
    data: list[CanonicalMarketBar]
    meta: dict[str, Any]


class CanonicalTradingSession(ApiModel):
    market: Literal["A_SHARE"]
    session_date: date
    is_open: Literal[True]
    time_zone: Literal["Asia/Shanghai"]
    source_id: Literal["tushare", "financial_data"]


class CanonicalTradingSessionsResponse(ApiModel):
    data: list[CanonicalTradingSession]
    meta: dict[str, Any]


class CanonicalFundProfile(ApiModel):
    fund_id: str
    name: str | None = None
    management_company: str | None = None
    custodian: str | None = None
    fund_type: str | None = None
    investment_style: str | None = None
    establishment_date: date | None = None
    minimum_purchase_amount: float | None = None
    amount_currency: str
    management_fee_rate: float | None = None
    custodian_fee_rate: float | None = None
    source_id: Literal["tushare", "financial_data"]
    source_dataset: str


class CanonicalFundProfilesResponse(ApiModel):
    data: list[CanonicalFundProfile]
    meta: dict[str, Any]


class CanonicalFundNav(ApiModel):
    fund_id: str
    nav_date: date
    announcement_date: date | None = None
    unit_nav: float | None = None
    cumulative_nav: float | None = None
    adjusted_nav: float | None = None
    daily_return_rate: float | None = None
    annualized_yield_7d_rate: float | None = None
    daily_profit_per_10k: float | None = None
    currency: str
    source_id: Literal["tushare", "financial_data"]
    source_dataset: str


class CanonicalFundNavResponse(ApiModel):
    data: list[CanonicalFundNav]
    meta: dict[str, Any]


class CanonicalFundStockHolding(ApiModel):
    fund_id: str
    report_date: date
    announcement_date: date | None = None
    instrument_id: str
    instrument_name: str | None = None
    holding_shares: float | None = None
    holding_market_value: float | None = None
    market_value_currency: str
    weight_pct: float | None = None
    source_id: Literal["tushare", "financial_data"]
    source_dataset: str


class CanonicalFundStockHoldingsResponse(ApiModel):
    data: list[CanonicalFundStockHolding]
    meta: dict[str, Any]


class CanonicalFundDividend(ApiModel):
    fund_id: str
    announcement_date: date | None = None
    record_date: date | None = None
    ex_dividend_date: date | None = None
    payment_date: date | None = None
    cash_per_unit: float | None = None
    distribution_base_units: float | None = None
    status: str | None = None
    currency: Literal["CNY"]
    source_id: Literal["tushare", "financial_data"]
    source_dataset: str


class CanonicalFundDividendsResponse(ApiModel):
    data: list[CanonicalFundDividend]
    meta: dict[str, Any]


class CanonicalFundManager(ApiModel):
    fund_id: str
    manager_name: str | None = None
    tenure_start_date: date | None = None
    tenure_end_date: date | None = None
    tenure_return_rate: float | None = None
    career_start_date: date | None = None
    background: str | None = None
    education: str | None = None
    source_id: Literal["tushare", "financial_data"]
    source_dataset: str


class CanonicalFundManagersResponse(ApiModel):
    data: list[CanonicalFundManager]
    meta: dict[str, Any]


class CanonicalIndexProfile(ApiModel):
    index_id: str
    name: str | None = None
    full_name: str | None = None
    market: str | None = None
    publisher: str | None = None
    category: str | None = None
    publication_date: date | None = None
    base_date: date | None = None
    base_point: float | None = None
    currency: str
    description: str | None = None
    source_id: Literal["tushare", "financial_data"]
    source_dataset: str


class CanonicalIndexProfilesResponse(ApiModel):
    data: list[CanonicalIndexProfile]
    meta: dict[str, Any]


class CanonicalIndexConstituent(ApiModel):
    index_id: str
    update_date: date
    instrument_id: str
    instrument_name: str | None = None
    weight_pct: float | None = None
    source_id: Literal["tushare", "financial_data"]
    source_dataset: str


class CanonicalIndexConstituentsResponse(ApiModel):
    data: list[CanonicalIndexConstituent]
    meta: dict[str, Any]


class CanonicalEquityProfile(ApiModel):
    instrument_id: str
    ticker: str | None = None
    name: str | None = None
    full_name: str | None = None
    english_name: str | None = None
    exchange: str | None = None
    board: str | None = None
    currency: str
    listing_status: Literal["listed", "delisted", "pre_listing", "unknown"]
    listing_date: date | None = None
    region_name: str | None = None
    industry_name: str | None = None
    industry_classification: str
    actual_controller: str | None = None
    source_id: Literal["tushare", "financial_data"]
    source_dataset: str


class CanonicalEquityProfilesResponse(ApiModel):
    data: list[CanonicalEquityProfile]
    meta: dict[str, Any]


class CanonicalEquityValuation(ApiModel):
    instrument_id: str
    observation_date: date
    currency: Literal["CNY"]
    close: float | None = None
    pe_lyr: float | None = None
    pe_ttm: float | None = None
    pb_mrq: float | None = None
    ps_lyr: float | None = None
    ps_ttm: float | None = None
    dividend_yield_lyr_rate: float | None = None
    dividend_yield_ttm_rate: float | None = None
    total_shares: float | None = None
    float_shares: float | None = None
    total_market_cap: float | None = None
    float_market_cap: float | None = None
    source_id: Literal["tushare", "financial_data"]
    source_dataset: str


class CanonicalEquityValuationsResponse(ApiModel):
    data: list[CanonicalEquityValuation]
    meta: dict[str, Any]


class CanonicalFinancialIncome(ApiModel):
    total_revenue: float | None = None
    revenue: float | None = None
    operating_profit: float | None = None
    total_profit: float | None = None
    net_profit: float | None = None
    parent_net_profit: float | None = None


class CanonicalFinancialCashFlow(ApiModel):
    operating_cash_flow: float | None = None
    investing_cash_flow: float | None = None
    financing_cash_flow: float | None = None
    capital_expenditure_cash_paid: float | None = None


class CanonicalFinancialBalanceSheet(ApiModel):
    total_assets: float | None = None
    total_liabilities: float | None = None
    total_equity: float | None = None
    monetary_capital: float | None = None
    inventories: float | None = None
    accounts_receivable: float | None = None
    accounts_payable: float | None = None


class CanonicalFinancialSectionSource(ApiModel):
    source_id: Literal["tushare", "financial_data"]
    source_dataset: str
    disclosure_date: date | None = None


class CanonicalFinancialSectionSources(ApiModel):
    income: CanonicalFinancialSectionSource | None = None
    cash_flow: CanonicalFinancialSectionSource | None = None
    balance_sheet: CanonicalFinancialSectionSource | None = None


class CanonicalEquityFinancialPeriod(ApiModel):
    instrument_id: str
    report_period: date
    disclosure_date: date | None = None
    currency: Literal["CNY"]
    income: CanonicalFinancialIncome | None = None
    cash_flow: CanonicalFinancialCashFlow | None = None
    balance_sheet: CanonicalFinancialBalanceSheet | None = None
    source_sections: CanonicalFinancialSectionSources


class CanonicalEquityFinancialPeriodsResponse(ApiModel):
    data: list[CanonicalEquityFinancialPeriod]
    meta: dict[str, Any]


class CanonicalEquityPerformanceUpdate(ApiModel):
    instrument_id: str
    report_period: date
    publication_date: date | None = None
    update_type: Literal["forecast", "preliminary"]
    accumulation_basis: Literal["cumulative", "single_quarter", "unknown"]
    forecast_category: str | None = None
    forecast_direction: Literal[
        "positive", "negative", "flat", "uncertain", "unknown"
    ]
    revenue_lower: float | None = None
    revenue_upper: float | None = None
    parent_net_profit_lower: float | None = None
    parent_net_profit_upper: float | None = None
    parent_net_profit_yoy_lower_pct: float | None = None
    parent_net_profit_yoy_upper_pct: float | None = None
    basic_eps_lower: float | None = None
    basic_eps_upper: float | None = None
    reported_revenue: float | None = None
    reported_parent_net_profit: float | None = None
    reported_operating_cash_flow: float | None = None
    reported_basic_eps: float | None = None
    reported_roe_pct: float | None = None
    summary: str | None = None
    reason: str | None = None
    currency: Literal["CNY"]
    source_id: Literal["tushare", "financial_data"]
    source_dataset: str


class CanonicalEquityPerformanceUpdatesResponse(ApiModel):
    data: list[CanonicalEquityPerformanceUpdate]
    meta: dict[str, Any]


class CanonicalEquityFinancialMetric(ApiModel):
    instrument_id: str
    report_period: date
    disclosure_date: date | None = None
    basic_eps: float | None = None
    diluted_eps: float | None = None
    book_value_per_share: float | None = None
    operating_cash_flow_per_share: float | None = None
    revenue_per_share: float | None = None
    roe_diluted_pct: float | None = None
    roe_weighted_pct: float | None = None
    roe_deducted_pct: float | None = None
    roa_pct: float | None = None
    roic_pct: float | None = None
    gross_margin_pct: float | None = None
    net_margin_pct: float | None = None
    current_ratio: float | None = None
    quick_ratio: float | None = None
    debt_to_assets_pct: float | None = None
    interest_coverage_ratio: float | None = None
    receivables_turnover: float | None = None
    inventory_turnover: float | None = None
    asset_turnover: float | None = None
    operating_revenue_yoy_pct: float | None = None
    parent_net_profit_yoy_pct: float | None = None
    deducted_parent_net_profit_yoy_pct: float | None = None
    operating_cash_flow_to_revenue: float | None = None
    source_id: Literal["tushare", "financial_data"]
    source_dataset: str


class CanonicalEquityFinancialMetricsResponse(ApiModel):
    data: list[CanonicalEquityFinancialMetric]
    meta: dict[str, Any]


class CanonicalEquityTtmFinancial(ApiModel):
    instrument_id: str
    report_period: date
    disclosure_date: date | None = None
    total_revenue_ttm: float | None = None
    revenue_ttm: float | None = None
    parent_net_profit_ttm: float | None = None
    operating_cash_flow_ttm: float | None = None
    capital_expenditure_ttm: float | None = None
    free_cash_flow_ttm: float | None = None
    net_margin_ttm_pct: float | None = None
    gross_margin_ttm_pct: float | None = None
    roe_ttm_pct: float | None = None
    roa_ttm_pct: float | None = None
    roic_ttm_pct: float | None = None
    basic_eps_ttm: float | None = None
    source_id: Literal["tushare", "financial_data"]
    source_dataset: str
    calculation: str


class CanonicalEquityTtmFinancialsResponse(ApiModel):
    data: list[CanonicalEquityTtmFinancial]
    meta: dict[str, Any]


class CanonicalEquityDividend(ApiModel):
    instrument_id: str
    report_period: date
    proposal_publication_date: date | None = None
    record_date: date | None = None
    ex_dividend_date: date | None = None
    payment_date: date | None = None
    status: str | None = None
    cash_per_share_before_tax: float | None = None
    cash_per_share_after_tax: float | None = None
    total_cash_dividend: float | None = None
    equity_base_shares: float | None = None
    bonus_shares_per_share: float | None = None
    capitalization_shares_per_share: float | None = None
    description: str | None = None
    currency: Literal["CNY"]
    source_id: Literal["tushare", "financial_data"]
    source_dataset: str


class CanonicalEquityDividendsResponse(ApiModel):
    data: list[CanonicalEquityDividend]
    meta: dict[str, Any]


class CanonicalEquityRepurchase(ApiModel):
    instrument_id: str
    event_date: date
    progress_status: str | None = None
    deadline: date | None = None
    current_shares: float | None = None
    current_amount: float | None = None
    current_average_price: float | None = None
    current_low_price: float | None = None
    current_high_price: float | None = None
    cumulative_shares: float | None = None
    cumulative_amount: float | None = None
    planned_amount_lower: float | None = None
    planned_amount_upper: float | None = None
    purpose: str | None = None
    currency: Literal["CNY"]
    source_id: Literal["tushare", "financial_data"]
    source_dataset: str


class CanonicalEquityRepurchasesResponse(ApiModel):
    data: list[CanonicalEquityRepurchase]
    meta: dict[str, Any]


class CanonicalEquityHolderCount(ApiModel):
    instrument_id: str
    observation_date: date
    publication_date: date | None = None
    total_shareholders: float | None = None
    shareholder_change: float | None = None
    shareholder_change_pct: float | None = None
    average_holding_shares: float | None = None
    average_holding_market_value: float | None = None
    a_share_shareholders: float | None = None
    currency: Literal["CNY"]
    source_id: Literal["tushare", "financial_data"]
    source_dataset: str


class CanonicalEquityHolderCountsResponse(ApiModel):
    data: list[CanonicalEquityHolderCount]
    meta: dict[str, Any]


class CanonicalEquityBusinessSegment(ApiModel):
    instrument_id: str
    report_period: date
    classification: Literal["business", "industry", "product", "region"]
    segment_name: str | None = None
    revenue: float | None = None
    cost: float | None = None
    profit: float | None = None
    gross_margin_pct: float | None = None
    revenue_share_pct: float | None = None
    revenue_yoy_pct: float | None = None
    source_information: str | None = None
    currency: Literal["CNY"]
    source_id: Literal["tushare", "financial_data"]
    source_dataset: str


class CanonicalEquityBusinessSegmentsResponse(ApiModel):
    data: list[CanonicalEquityBusinessSegment]
    meta: dict[str, Any]


class CanonicalEquityShareholder(ApiModel):
    instrument_id: str
    report_period: date
    publication_date: date | None = None
    scope: Literal["total", "float", "reported"]
    rank: int | None = None
    shareholder_name: str | None = None
    shareholder_type: str | None = None
    holding_shares: float | None = None
    holding_pct_total: float | None = None
    holding_pct_float: float | None = None
    holding_change_shares: float | None = None
    pledged_shares: float | None = None
    frozen_shares: float | None = None
    source_id: Literal["tushare", "financial_data"]
    source_dataset: str


class CanonicalEquityShareholdersResponse(ApiModel):
    data: list[CanonicalEquityShareholder]
    meta: dict[str, Any]


class CanonicalEquityRestrictedRelease(ApiModel):
    instrument_id: str
    release_date: date
    publication_date: date | None = None
    restricted_start_date: date | None = None
    shareholder_name: str | None = None
    release_shares: float | None = None
    release_pct_total: float | None = None
    release_type: str | None = None
    source_id: Literal["tushare", "financial_data"]
    source_dataset: str


class CanonicalEquityRestrictedReleasesResponse(ApiModel):
    data: list[CanonicalEquityRestrictedRelease]
    meta: dict[str, Any]


class CanonicalEquityPledge(ApiModel):
    instrument_id: str
    publication_date: date | None = None
    event_date: date
    event_type: str | None = None
    shareholder_name: str | None = None
    receiver_name: str | None = None
    involved_shares: float | None = None
    pct_of_total_shares: float | None = None
    pct_of_pledger: float | None = None
    end_date: date | None = None
    release_date: date | None = None
    is_released: bool
    reason: str | None = None
    statement: str | None = None
    source_id: Literal["tushare", "financial_data"]
    source_dataset: str


class CanonicalEquityPledgesResponse(ApiModel):
    data: list[CanonicalEquityPledge]
    meta: dict[str, Any]


class CanonicalEquityRiskAlert(ApiModel):
    instrument_id: str
    instrument_name: str | None = None
    effective_date: date
    removal_date: date | None = None
    publication_date: date | None = None
    risk_type: str | None = None
    is_in_risk_alert_board: bool | None = None
    reason: str | None = None
    description: str | None = None
    source_id: Literal["tushare", "financial_data"]
    source_dataset: str


class CanonicalEquityRiskAlertsResponse(ApiModel):
    data: list[CanonicalEquityRiskAlert]
    meta: dict[str, Any]


class CanonicalEquitySuspension(ApiModel):
    instrument_id: str
    suspend_date: date
    resumption_date: date | None = None
    suspend_time: str | None = None
    resumption_time: str | None = None
    suspend_type: str | None = None
    publication_date: date | None = None
    reason: str | None = None
    statement: str | None = None
    source_information: str | None = None
    source_id: Literal["tushare", "financial_data"]
    source_dataset: str


class CanonicalEquitySuspensionsResponse(ApiModel):
    data: list[CanonicalEquitySuspension]
    meta: dict[str, Any]


class InterfaceSummary(ApiModel):
    api_name: str
    title: str
    category: str
    permission_status: str
    implementation_mode: str
    storage_mode: str
    datasets: list[str]
    records_url: str | None = None


class InterfaceDescription(InterfaceSummary):
    description: str
    document_urls: list[str]
    input_parameters: list[dict[str, Any]]
    output_parameters: list[dict[str, Any]]
    allowed_filters: list[str]
    standard_filters: list[str] = Field(default_factory=list)
    advanced_filters: list[str] = Field(default_factory=list)
    date_fields: list[str]


class InterfaceRecordsMeta(ApiModel):
    interface: str
    storage: str
    read_view: str | None = None
    returned: int
    date_field: str | None = None


class InterfaceRecordsResponse(ApiModel):
    data: list[dict[str, Any]]
    meta: InterfaceRecordsMeta
    page: PageInfo


class RawInterfaceSummary(ApiModel):
    api_name: str
    title: str
    implementation_mode: str
    document_urls: list[str]
    request_count: int
    successful_requests: int
    empty_requests: int
    failed_requests: int
    latest_request_at: datetime | None = None
    has_records: bool


class RawRequestItem(ApiModel):
    request_id: int
    api_name: str
    request_hash: str
    logical_request_hash: str
    request_params: dict[str, Any]
    logical_request_params: dict[str, Any]
    collector_name: str
    status: Literal["success", "empty", "failed"]
    row_count: int
    response_hash: str | None = None
    source_doc_id: int | None = None
    error_message: str | None = None
    requested_at: datetime
    completed_at: datetime | None = None


class RawRecordItem(ApiModel):
    api_name: str
    request_hash: str
    record_hash: str
    request_params: dict[str, Any]
    payload: dict[str, Any]
    source_doc_id: int | None = None
    collected_at: datetime
    first_seen_at: datetime
    last_seen_at: datetime


class RawAuditMeta(ApiModel):
    interface: str
    returned: int


class RawRequestPageResponse(ApiModel):
    data: list[RawRequestItem]
    meta: RawAuditMeta
    page: PageInfo


class RawRecordPageResponse(ApiModel):
    data: list[RawRecordItem]
    meta: RawAuditMeta
    page: PageInfo


class RawCoverageResponse(ApiModel):
    api_name: str
    request_count: int
    successful_requests: int
    empty_requests: int
    failed_requests: int
    record_count: int
    logical_request_count: int
    first_seen_at: datetime | None = None
    last_seen_at: datetime | None = None
    latest_request_at: datetime | None = None
    implementation_mode: str
    document_urls: list[str]


class RawLineageResponse(ApiModel):
    api_name: str
    record_hash: str
    records: list[RawRecordItem]
    requests: list[RawRequestItem]


class DataServiceEndpoint(ApiModel):
    method: Literal["GET"]
    path: str
    name: str
    description: str
    domain: str | None = None
    status: str | None = None


class DataServiceLayer(ApiModel):
    id: Literal["raw", "standard", "research"]
    order: int
    title: str
    short_title: str
    description: str
    usage_guidance: str
    status: str
    coverage_note: str
    metrics: dict[str, int]
    endpoints: list[DataServiceEndpoint]
    items: list[dict[str, Any]]


class DataServiceCatalogResponse(ApiModel):
    generated_at: datetime
    recommended_entrypoint: str
    audiences: list[dict[str, Any]]
    control_plane: dict[str, Any]
    summary: dict[str, int]
    layers: list[DataServiceLayer]


class NormalizationInterfaceStatus(ApiModel):
    api_name: str
    table: str
    status: str
    raw_rows: int
    estimated_normalized_rows: int
    unresolved_errors: int
    unresolved_drift: int
    last_run_at: datetime | None = None
    last_run_status: str | None = None


class NormalizationSummary(ApiModel):
    interfaces: int
    raw_rows: int
    estimated_normalized_rows: int
    unresolved_errors: int
    unresolved_drift: int
    statuses: dict[str, int]


class NormalizationOverview(ApiModel):
    generated_at: datetime
    summary: NormalizationSummary
    interfaces: list[NormalizationInterfaceStatus]


class NormalizationDriftItem(ApiModel):
    api_name: str
    field_name: str
    drift_type: str
    severity: str
    occurrences: int
    first_seen_at: datetime
    last_seen_at: datetime
    resolved_at: datetime | None = None


class NormalizationErrorItem(ApiModel):
    api_name: str
    request_hash: str
    record_hash: str
    error_code: str
    error_message: str
    attempts: int
    first_seen_at: datetime
    last_seen_at: datetime
    resolved_at: datetime | None = None


class FreshnessItem(ApiModel):
    dataset: str
    latest_date: Any = None
    status: str
    freshness_sla_hours: int | None
    freshness_policy: str = "unconfigured"
    expected_latest_date: Any = None
    estimated_rows: int


class SnapshotMeta(ApiModel):
    ts_code: str
    generated_at: datetime


class StockSnapshotResponse(ApiModel):
    data: dict[str, Any]
    meta: SnapshotMeta


class StockResearchPackResponse(ApiModel):
    data: dict[str, Any]
    meta: dict[str, Any]


class SectorSummary(ApiModel):
    provider: str
    sector_code: str
    name: str | None = None
    category: str | None = None
    market: str | None = None
    constituent_count: int | None = None
    trade_date: Any = None


class SectorListResponse(ApiModel):
    data: list[SectorSummary]
    meta: dict[str, Any]


class SectorSnapshotResponse(ApiModel):
    data: dict[str, Any]
    meta: dict[str, Any]


class SectorMembersResponse(ApiModel):
    data: list[dict[str, Any]]
    meta: dict[str, Any]


class SectorResearchPackResponse(ApiModel):
    data: dict[str, Any]
    meta: dict[str, Any]


class ErrorBody(ApiModel):
    code: str
    message: str
    request_id: str | None = None


class ErrorResponse(ApiModel):
    error: ErrorBody


class InitializationRequest(ApiModel):
    profile: Literal["quick", "standard", "research", "full"] = "standard"
    history_start: date | None = None
    history_end: date | None = None
    auto_activate: bool = True


class CoverageAuditRequest(ApiModel):
    datasets: list[str] | None = Field(default=None, min_length=1, max_length=50)
    all_datasets: bool = False
    start_date: date | None = None
    end_date: date | None = None


class CoverageRepairRequest(ApiModel):
    dataset: str = Field(min_length=1, max_length=100)
    start_date: date
    end_date: date
