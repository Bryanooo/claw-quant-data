"""Provider-acquisition models shared by the V2 workflow runtime."""

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel


HISTORICAL_CADENCES = frozenset({"backfill", "initialization", "repair"})
HISTORICAL_MAX_ATTEMPTS = 8


def max_attempts_for_cadence(cadence: str | None, default: int = 3) -> int:
    """Give resumable history enough budget to survive short provider outages."""
    return HISTORICAL_MAX_ATTEMPTS if cadence in HISTORICAL_CADENCES else default


class AcquisitionExecutionError(Exception):
    """Base class for V2 acquisition errors safe to expose through the API."""


class TaskNotFoundError(AcquisitionExecutionError):
    pass


class JobNotFoundError(AcquisitionExecutionError):
    pass


class JobConflictError(AcquisitionExecutionError):
    pass


class JobLeaseLostError(AcquisitionExecutionError):
    """The worker no longer owns the running job it tried to update."""


class JobHandlerMismatchError(AcquisitionExecutionError):
    """A persisted job no longer resolves to its snapshotted handler."""

    retryable = False


class JobHandlerUnavailableError(AcquisitionExecutionError):
    """The claiming worker is older than the handler required by the job.

    Rolling deployments can briefly leave old and new workers alive together.
    An old worker must release a newer job without consuming an attempt so a
    compatible worker can claim it after the deployment converges.
    """

    defer_without_failure = True
    retry_after_seconds = 30


class InvalidTaskParametersError(AcquisitionExecutionError):
    pass


@dataclass(frozen=True, slots=True)
class TaskExecutionResult:
    """Verified outcome returned by a task runner to the durable queue."""

    rows_inserted: int
    rows_fetched: int | None = None
    completion_status: str = "unverified"
    completion_evidence: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class TaskSpec:
    name: str
    description: str
    category: str
    parameters_model: type[BaseModel]
    runner: Callable[[BaseModel], int | TaskExecutionResult] = field(repr=False)
    handler_type: str = "dedicated"
    handler_version: str = "1"

    def describe(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "handler_type": self.handler_type,
            "handler_version": self.handler_version,
            "parameters_schema": self.parameters_model.model_json_schema(),
        }


@dataclass(frozen=True, slots=True)
class HandlerMetadata:
    handler_type: str
    handler_key: str
    handler_version: str
    code_revision: str


@dataclass(frozen=True, slots=True)
class BatchChildSpec:
    """One independently retryable leaf in a durable collection batch."""

    task_name: str
    parameters: dict[str, Any]
    idempotency_key: str
    api_name: str | None
    cadence: str | None
    period_key: str | None
    expected_for: Any | None
    handler: HandlerMetadata
    max_attempts: int = 3
    priority: int = 20
    resource_class: str = "backfill"
