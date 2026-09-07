"""Domain models and errors for collection jobs."""

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel


class CollectionJobError(Exception):
    """Base class for collection-job errors safe to expose through the API."""


class TaskNotFoundError(CollectionJobError):
    pass


class JobNotFoundError(CollectionJobError):
    pass


class JobConflictError(CollectionJobError):
    pass


class JobLeaseLostError(CollectionJobError):
    """The worker no longer owns the running job it tried to update."""


class JobHandlerMismatchError(CollectionJobError):
    """A persisted job no longer resolves to its snapshotted handler."""

    retryable = False


class InvalidTaskParametersError(CollectionJobError):
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
