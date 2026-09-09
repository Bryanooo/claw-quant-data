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
    date_column: str | None


class ColumnDescription(ApiModel):
    column_name: str
    data_type: str
    is_nullable: str


class DatasetDescription(DatasetSummary):
    table: str
    read_view: str | None = None
    primary_keys: list[str]
    storage_semantics: str = "canonical_upsert"
    business_identity_fields: list[str] = Field(default_factory=list)
    identity_confidence: str = "database_constraint"
    allowed_filters: list[str]
    availability_column: str | None = None
    max_page_size: int
    columns: list[ColumnDescription]


class RecordsMeta(ApiModel):
    dataset: str
    source: str
    returned: int


class PageInfo(ApiModel):
    limit: int
    offset: int
    total: int | None = None
    has_more: bool


class RecordsResponse(ApiModel):
    data: list[dict[str, Any]]
    meta: RecordsMeta
    page: PageInfo


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


class CollectionTaskSummary(ApiModel):
    name: str
    description: str
    category: str
    handler_type: str
    handler_version: str
    parameters_schema: dict[str, Any]


class CollectionJobRequest(ApiModel):
    task_name: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    max_attempts: int = Field(default=3, ge=1, le=5)


class FanoutBatchRequest(ApiModel):
    """Bounded request for an allow-listed fan-out collection plan."""

    api_name: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_]*$")
    trade_date: date | None = None
    ann_date: date | None = None
    period: date | None = None
    start_date: date | None = None
    end_date: date | None = None
    offset: int = Field(default=0, ge=0)
    max_children: int = Field(default=50, ge=1, le=200)


class FanoutCampaignRequest(ApiModel):
    """A whole-universe fan-out that automatically advances bounded pages."""

    api_name: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_]*$")
    trade_date: date | None = None
    ann_date: date | None = None
    period: date | None = None
    start_date: date | None = None
    end_date: date | None = None
    page_size: int = Field(default=100, ge=1, le=200)


class InitializationRequest(ApiModel):
    profile: Literal["quick", "standard", "research", "full"] = "standard"
    history_start: date | None = None
    history_end: date | None = None
    auto_activate: bool = True


class CollectionJobResponse(ApiModel):
    job_id: int
    task_name: str
    parameters: dict[str, Any]
    status: str
    attempt: int
    max_attempts: int
    rows_inserted: int
    rows_fetched: int | None = None
    api_name: str | None = None
    cadence: str | None = None
    period_key: str | None = None
    expected_for: Any = None
    completion_status: str = "pending"
    completion_evidence: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str | None = None
    parent_job_id: int | None = None
    recheck_of_job_id: int | None = None
    recheck_root_job_id: int | None = None
    recheck_generation: int = 0
    job_kind: str = "leaf"
    child_total: int = 0
    child_queued: int = 0
    child_running: int = 0
    child_succeeded: int = 0
    child_failed: int = 0
    worker_id: str | None = None
    handler_type: str | None = None
    handler_key: str | None = None
    handler_version: str | None = None
    code_revision: str | None = None
    priority: int = 50
    resource_class: str = "default"
    heartbeat_at: datetime | None = None
    lease_expires_at: datetime | None = None
    error_message: str | None = None
    available_at: datetime
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None


class CoverageAuditRequest(ApiModel):
    datasets: list[str] | None = Field(default=None, min_length=1, max_length=50)
    start_date: date | None = None
    end_date: date | None = None


class CoverageRepairRequest(ApiModel):
    dataset: str = Field(min_length=1, max_length=100)
    start_date: date
    end_date: date
