"""Strong contracts and state machines for the V2 task control plane."""

from __future__ import annotations

from datetime import date, datetime, time
from enum import StrEnum
import hashlib
import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


TASK_KEY_PATTERN = r"^[a-z][a-z0-9_.:-]{2,127}$"
HANDLER_KEY_PATTERN = r"^[a-z][a-z0-9_.:-]{2,127}$"
DATASET_NAME_PATTERN = r"^[a-z][a-z0-9_.:-]{1,127}$"

# These partitions are published on the following morning.  Keeping the
# contract shared prevents the scheduler and operations view from disagreeing
# about whether today's absent execution is late or simply not due yet.
NEXT_MORNING_TASKS = frozenset({
    "ccass_hold",
    "etf_share_size",
    "margin",
    "margin_detail",
})
NEXT_MORNING_TASK_RELEASE_TIME = time(9, 15)


class WorkflowKind(StrEnum):
    ACQUISITION = "acquisition"
    TRANSFORMATION = "transformation"


class NodeKind(StrEnum):
    CONDITION = "condition"
    DEPENDENCY_CHECK = "dependency_check"
    SCOPE_PLAN = "scope_plan"
    ACQUIRE = "acquire"
    MERGE = "merge"
    TRANSFORM = "transform"
    VALIDATE = "validate"
    PUBLISH = "publish"


class ExecutionPurpose(StrEnum):
    DAILY = "daily"
    INITIALIZATION = "initialization"
    BACKFILL = "backfill"
    REPAIR = "repair"
    MANUAL = "manual"
    SHADOW = "shadow"


class TriggerSource(StrEnum):
    SCHEDULE = "schedule"
    DEPENDENCY = "dependency"
    MANUAL = "manual"
    RECOVERY = "recovery"
    MIGRATION = "migration"
    SHADOW = "shadow"


class ExecutionStatus(StrEnum):
    CREATED = "created"
    QUEUED = "queued"
    RUNNING = "running"
    WAITING_DEPENDENCY = "waiting_dependency"
    RETRYING = "retrying"
    VALIDATING = "validating"
    PUBLISHING = "publishing"
    SUCCESS = "success"
    ATTENTION = "attention"
    SUPERSEDED = "superseded"
    CANCELLED = "cancelled"


class DataStatus(StrEnum):
    PENDING = "pending"
    AUDITING = "auditing"
    COMPLETE = "complete"
    EMPTY_VERIFIED = "empty_verified"
    GAPS = "gaps"
    PARTIAL = "partial"
    INDETERMINATE = "indeterminate"


TERMINAL_EXECUTION_STATUSES = frozenset({
    ExecutionStatus.SUCCESS,
    ExecutionStatus.ATTENTION,
    ExecutionStatus.SUPERSEDED,
    ExecutionStatus.CANCELLED,
})

EXECUTION_TRANSITIONS: dict[ExecutionStatus, frozenset[ExecutionStatus]] = {
    ExecutionStatus.CREATED: frozenset({
        ExecutionStatus.QUEUED,
        ExecutionStatus.SUPERSEDED,
        ExecutionStatus.CANCELLED,
    }),
    ExecutionStatus.QUEUED: frozenset({
        ExecutionStatus.RUNNING,
        ExecutionStatus.WAITING_DEPENDENCY,
        ExecutionStatus.SUPERSEDED,
        ExecutionStatus.CANCELLED,
    }),
    ExecutionStatus.RUNNING: frozenset({
        ExecutionStatus.RETRYING,
        ExecutionStatus.WAITING_DEPENDENCY,
        ExecutionStatus.VALIDATING,
        ExecutionStatus.ATTENTION,
        ExecutionStatus.CANCELLED,
    }),
    ExecutionStatus.WAITING_DEPENDENCY: frozenset({
        ExecutionStatus.QUEUED,
        ExecutionStatus.RUNNING,
        ExecutionStatus.ATTENTION,
        ExecutionStatus.SUPERSEDED,
        ExecutionStatus.CANCELLED,
    }),
    ExecutionStatus.RETRYING: frozenset({
        ExecutionStatus.QUEUED,
        ExecutionStatus.RUNNING,
        ExecutionStatus.ATTENTION,
        ExecutionStatus.SUPERSEDED,
        ExecutionStatus.CANCELLED,
    }),
    ExecutionStatus.VALIDATING: frozenset({
        ExecutionStatus.PUBLISHING,
        ExecutionStatus.RETRYING,
        ExecutionStatus.ATTENTION,
        ExecutionStatus.CANCELLED,
    }),
    ExecutionStatus.PUBLISHING: frozenset({
        ExecutionStatus.SUCCESS,
        ExecutionStatus.RETRYING,
        ExecutionStatus.ATTENTION,
        ExecutionStatus.CANCELLED,
    }),
    ExecutionStatus.ATTENTION: frozenset({
        ExecutionStatus.QUEUED,
        ExecutionStatus.SUPERSEDED,
        ExecutionStatus.CANCELLED,
    }),
    ExecutionStatus.SUCCESS: frozenset(),
    ExecutionStatus.SUPERSEDED: frozenset(),
    ExecutionStatus.CANCELLED: frozenset(),
}


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class RetryPolicy(ContractModel):
    max_attempts: int = Field(default=3, ge=1, le=100)
    initial_delay_seconds: int = Field(default=5, ge=0, le=86_400)
    max_delay_seconds: int = Field(default=300, ge=0, le=604_800)
    backoff_multiplier: float = Field(default=2.0, ge=1.0, le=10.0)
    retryable_categories: tuple[str, ...] = (
        "provider_transient",
        "rate_limited",
        "network",
        "database_transient",
        "lease_expired",
    )

    @model_validator(mode="after")
    def validate_delay_bounds(self) -> "RetryPolicy":
        if self.max_delay_seconds < self.initial_delay_seconds:
            raise ValueError("max retry delay cannot be below initial delay")
        return self


class TaskNode(ContractModel):
    key: str = Field(pattern=TASK_KEY_PATTERN)
    kind: NodeKind
    handler_key: str = Field(pattern=HANDLER_KEY_PATTERN)
    retry: RetryPolicy = Field(default_factory=RetryPolicy)
    configuration: dict[str, Any] = Field(default_factory=dict)


class TaskDependency(ContractModel):
    task_key: str = Field(pattern=TASK_KEY_PATTERN)
    datasets: tuple[str, ...] = ()
    require_status: Literal["ready"] = "ready"

    @field_validator("datasets")
    @classmethod
    def validate_datasets(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if len(values) != len(set(values)):
            raise ValueError("dependency datasets must be unique")
        for value in values:
            if not value or len(value) > 128:
                raise ValueError(f"invalid dependency dataset: {value}")
        return values


class ScheduleContract(ContractModel):
    mode: Literal["cron", "dependency", "manual", "disabled"]
    timezone: str = "Asia/Shanghai"
    expression: str | None = None
    release_delay_seconds: int = Field(default=0, ge=0, le=604_800)
    pause_history_during_market_hours: bool = True

    @model_validator(mode="after")
    def validate_expression(self) -> "ScheduleContract":
        if self.mode == "cron" and not (self.expression or "").strip():
            raise ValueError("cron schedules require an expression")
        if self.mode != "cron" and self.expression is not None:
            raise ValueError("only cron schedules may define an expression")
        return self


class ResourceContract(ContractModel):
    resource_class: str = Field(default="default", min_length=1, max_length=64)
    priority: int = Field(default=50, ge=0, le=100)
    max_node_concurrency: int = Field(default=1, ge=1, le=64)
    source_quota_key: str | None = Field(default=None, max_length=128)


class DatasetAuditContract(ContractModel):
    """Frozen completeness contract for one task output.

    A task execution may only publish a ready dataset state after the validate
    node has evaluated this contract.  ``period_granularity`` is also the
    atomic execution boundary for initialization, backfill and repair: pages,
    symbols and provider-side partitions stay inside that execution.
    """

    dataset_name: str = Field(pattern=DATASET_NAME_PATTERN)
    audit_mode: Literal[
        "expected_partition",
        "observed_scope_transport",
        "exhaustive_snapshot",
        "dependency_scoped",
    ]
    period_granularity: Literal[
        "day", "week", "month", "quarter", "snapshot", "dependency"
    ]
    rule_revision: int = Field(default=1, ge=1)
    availability_start: date | None = None
    date_column: str | None = Field(default=None, max_length=128)
    entity_reference: str | None = Field(default=None, max_length=128)
    min_entity_ratio: float | None = Field(default=None, gt=0, le=1)
    require_transport_proof: bool = False
    accepts_verified_empty: bool = False

    @model_validator(mode="after")
    def validate_audit_geometry(self) -> "DatasetAuditContract":
        if self.audit_mode == "exhaustive_snapshot":
            if self.period_granularity != "snapshot" or self.date_column is not None:
                raise ValueError(
                    "exhaustive snapshots require snapshot granularity and no date column"
                )
        elif self.audit_mode == "dependency_scoped":
            if self.period_granularity != "dependency":
                raise ValueError(
                    "dependency-scoped audits require dependency granularity"
                )
        elif self.period_granularity in {"snapshot", "dependency"}:
            raise ValueError("temporal audit modes require a temporal granularity")
        return self


class TaskValidationContract(ContractModel):
    verified_evidence_required: Literal[True] = True
    outputs: tuple[str, ...]
    dataset_audits: tuple[DatasetAuditContract, ...]

    @model_validator(mode="after")
    def validate_output_coverage(self) -> "TaskValidationContract":
        outputs = tuple(self.outputs)
        audited = tuple(item.dataset_name for item in self.dataset_audits)
        if len(outputs) != len(set(outputs)):
            raise ValueError("validation outputs must be unique")
        if len(audited) != len(set(audited)):
            raise ValueError("dataset audit contracts must be unique")
        if set(outputs) != set(audited):
            raise ValueError(
                "validation outputs and dataset audit contracts must match exactly"
            )
        return self


class TaskDefinitionDocument(ContractModel):
    schema_version: Literal[1] = 1
    task_key: str = Field(pattern=TASK_KEY_PATTERN)
    workflow_kind: WorkflowKind
    nodes: tuple[TaskNode, ...]
    input_datasets: tuple[str, ...] = ()
    output_datasets: tuple[str, ...]
    acquisition_endpoint_ids: tuple[int, ...] = ()
    dependencies: tuple[TaskDependency, ...] = ()
    schedule: ScheduleContract
    scope_contract: dict[str, Any] = Field(default_factory=dict)
    validation_contract: TaskValidationContract
    resource: ResourceContract = Field(default_factory=ResourceContract)

    @field_validator("input_datasets", "output_datasets")
    @classmethod
    def validate_dataset_names(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if len(values) != len(set(values)):
            raise ValueError("dataset names must be unique")
        for value in values:
            if not value or len(value) > 128:
                raise ValueError(f"invalid dataset name: {value}")
            first, *rest = value
            allowed = set("abcdefghijklmnopqrstuvwxyz0123456789_.:-")
            if first not in set("abcdefghijklmnopqrstuvwxyz") or any(
                character not in allowed for character in rest
            ):
                raise ValueError(f"invalid dataset name: {value}")
        return values

    @model_validator(mode="after")
    def validate_graph(self) -> "TaskDefinitionDocument":
        if not self.nodes:
            raise ValueError("a task definition must contain nodes")
        node_keys = [node.key for node in self.nodes]
        if len(node_keys) != len(set(node_keys)):
            raise ValueError("node keys must be unique")
        if not self.output_datasets:
            raise ValueError("a task must publish at least one dataset")
        if set(self.validation_contract.outputs) != set(self.output_datasets):
            raise ValueError(
                "validation contract must cover every declared output exactly"
            )
        if len(self.acquisition_endpoint_ids) != len(set(
            self.acquisition_endpoint_ids
        )):
            raise ValueError("acquisition endpoint ids must be unique")
        if any(value <= 0 for value in self.acquisition_endpoint_ids):
            raise ValueError("acquisition endpoint ids must be positive")
        if any(item.task_key == self.task_key for item in self.dependencies):
            raise ValueError("a task cannot depend on itself")
        dependency_keys = [item.task_key for item in self.dependencies]
        if len(dependency_keys) != len(set(dependency_keys)):
            raise ValueError("dependency task keys must be unique")

        kinds = tuple(node.kind for node in self.nodes)
        acquisition = (
            NodeKind.CONDITION,
            NodeKind.SCOPE_PLAN,
            NodeKind.ACQUIRE,
            NodeKind.VALIDATE,
            NodeKind.PUBLISH,
        )
        multi_source = (
            NodeKind.CONDITION,
            NodeKind.SCOPE_PLAN,
            NodeKind.ACQUIRE,
            NodeKind.MERGE,
            NodeKind.VALIDATE,
            NodeKind.PUBLISH,
        )
        transformation = (
            NodeKind.CONDITION,
            NodeKind.DEPENDENCY_CHECK,
            NodeKind.SCOPE_PLAN,
            NodeKind.TRANSFORM,
            NodeKind.VALIDATE,
            NodeKind.PUBLISH,
        )
        if self.workflow_kind == WorkflowKind.ACQUISITION:
            if kinds not in {acquisition, multi_source}:
                raise ValueError(
                    "acquisition tasks must use the standard five-node or "
                    "multi-source six-node template"
                )
            if not self.acquisition_endpoint_ids:
                raise ValueError("acquisition tasks require at least one endpoint")
        else:
            if kinds != transformation:
                raise ValueError(
                    "transformation tasks must use the six-node dependency template"
                )
            if self.acquisition_endpoint_ids:
                raise ValueError("transformation tasks cannot call acquisition endpoints")
            if not self.input_datasets or not self.dependencies:
                raise ValueError(
                    "transformation tasks require input datasets and dependencies"
                )
        return self


class AcquisitionEndpointContract(ContractModel):
    schema_version: Literal[1] = 1
    source_id: str = Field(pattern=r"^[a-z][a-z0-9_-]{1,63}$")
    endpoint_key: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_.:-]*$")
    acquisition_mode: Literal[
        "scheduled_pull", "web_snapshot", "query_through", "stream"
    ]
    handler_key: str = Field(pattern=HANDLER_KEY_PATTERN)
    credential_ref: str | None = None
    request_contract: dict[str, Any] = Field(default_factory=dict)
    response_contract: dict[str, Any] = Field(default_factory=dict)
    pagination_policy: dict[str, Any] = Field(default_factory=dict)
    rate_limit_policy: dict[str, Any] = Field(default_factory=dict)
    completeness_policy: dict[str, Any]


class ExecutionRequest(ContractModel):
    task_key: str = Field(pattern=TASK_KEY_PATTERN)
    purpose: ExecutionPurpose
    trigger_source: TriggerSource
    idempotency_key: str = Field(min_length=1, max_length=512)
    observation_key: str = Field(min_length=1, max_length=256)
    observation_start: date | None = None
    observation_end: date | None = None
    observation_period: str | None = Field(default=None, max_length=128)
    publication_date: date | None = None
    data_available_at: datetime | None = None
    frozen_scope: dict[str, Any] = Field(default_factory=dict)
    app_revision: str | None = Field(default=None, max_length=256)
    image_digest: str | None = Field(default=None, max_length=512)

    @model_validator(mode="after")
    def validate_observation_range(self) -> "ExecutionRequest":
        if (
            self.observation_start is not None
            and self.observation_end is not None
            and self.observation_start > self.observation_end
        ):
            raise ValueError("observation_start cannot be after observation_end")
        return self


class DatasetStateUpdate(ContractModel):
    dataset_name: str = Field(pattern=DATASET_NAME_PATTERN)
    observation_key: str = Field(min_length=1, max_length=256)
    observation_start: date | None = None
    observation_end: date | None = None
    observation_period: str | None = Field(default=None, max_length=128)
    publication_date: date | None = None
    available_at: datetime | None = None
    collected_at: datetime | None = None
    scope: dict[str, Any] = Field(default_factory=dict)
    contract_version: str = Field(min_length=1, max_length=64)
    expectation_status: Literal["expected", "not_expected", "unknown"]
    data_status: DataStatus
    expected_count: int | None = Field(default=None, ge=0)
    actual_count: int | None = Field(default=None, ge=0)
    gap_summary: dict[str, Any] = Field(default_factory=dict)
    validation_summary: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_state(self) -> "DatasetStateUpdate":
        if (
            self.observation_start is not None
            and self.observation_end is not None
            and self.observation_start > self.observation_end
        ):
            raise ValueError("observation_start cannot be after observation_end")
        if self.data_status in {DataStatus.COMPLETE, DataStatus.EMPTY_VERIFIED}:
            if self.expectation_status != "expected":
                raise ValueError("only expected data can become ready")
            if not self.validation_summary.get("verified", False):
                raise ValueError("ready data requires verified validation evidence")
        return self

    @property
    def ready(self) -> bool:
        return self.data_status in {DataStatus.COMPLETE, DataStatus.EMPTY_VERIFIED}


def canonical_digest(document: BaseModel | dict[str, Any]) -> str:
    """Return the stable SHA-256 used to freeze definitions and scopes."""
    value = document.model_dump(mode="json") if isinstance(document, BaseModel) else document
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def assert_execution_transition(
    current: ExecutionStatus | str,
    target: ExecutionStatus | str,
) -> None:
    current_status = ExecutionStatus(current)
    target_status = ExecutionStatus(target)
    if target_status not in EXECUTION_TRANSITIONS[current_status]:
        raise ValueError(
            f"invalid execution transition: {current_status.value} -> "
            f"{target_status.value}"
        )
