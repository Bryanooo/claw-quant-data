"""Application service shared by the API and future MCP adapter."""

from service.collection_jobs.models import (
    JobConflictError,
    JobNotFoundError,
)
from service.collection_jobs.registry import TaskRegistry
from service.collection_jobs.fanout import FanoutPlanner

JOB_STATUSES = {"queued", "running", "success", "failed"}
COMPLETION_STATUSES = {
    "pending", "running", "retrying", "complete", "empty",
    "verifying", "unverified", "incomplete", "failed",
}
JOB_KINDS = {"leaf", "batch"}

_TASK_PRIORITIES = {
    "market": 80,
    "reference": 60,
    "finance": 55,
    "moneyflow": 70,
    "scheduled": 90,
    "catalog": 40,
}

# Purpose-built tasks use internal names that are not always the public
# Tushare API name. Persist the canonical interface identity on every job so
# monitoring and recovery can correlate old failures with later successes.
DEDICATED_TASK_API_NAMES = {
    "trade_calendar": "trade_cal",
    "stock_basic": "stock_basic",
    "stock_daily": "daily",
    "stock_daily_basic": "daily_basic",
    "moneyflow": "moneyflow",
    "stock_limit": "stk_limit",
    "stock_suspend": "suspend_d",
    "income_period": "income",
    "balancesheet_period": "balancesheet",
    "cashflow_period": "cashflow",
    "financial_indicator_period": "fina_indicator",
}


class CollectionJobService:
    def __init__(self, repository, registry: TaskRegistry):
        self._repository = repository
        self._registry = registry

    def list_tasks(self) -> list[dict]:
        return [task.describe() for task in self._registry.list()]

    def list_fanout_definitions(self) -> list[dict]:
        return FanoutPlanner.definitions()

    def submit_fanout(
        self,
        parameters: dict,
        *,
        idempotency_key: str | None,
    ) -> tuple[dict, bool]:
        return FanoutPlanner(self._repository, self._registry).create_batch(
            parameters,
            idempotency_key=idempotency_key,
        )

    def submit(
        self,
        task_name: str,
        parameters: dict,
        *,
        max_attempts: int,
        idempotency_key: str | None,
        parent_job_id: int | None = None,
        api_name: str | None = None,
        cadence: str | None = None,
        period_key: str | None = None,
        expected_for=None,
        priority: int | None = None,
        resource_class: str | None = None,
    ) -> tuple[dict, bool]:
        validated = self._registry.validate(task_name, parameters)
        normalized = validated.model_dump(mode="json")
        handler = self._registry.handler_metadata(task_name, normalized)
        task = self._registry.get(task_name)
        job, created = self._repository.create(
            task_name,
            normalized,
            max_attempts=max_attempts,
            idempotency_key=idempotency_key,
            parent_job_id=parent_job_id,
            api_name=(
                api_name
                or (
                    normalized.get("api_name")
                    if task_name == "tushare_interface"
                    else DEDICATED_TASK_API_NAMES.get(task_name)
                )
            ),
            cadence=cadence,
            period_key=period_key,
            expected_for=expected_for,
            handler_type=handler.handler_type,
            handler_key=handler.handler_key,
            handler_version=handler.handler_version,
            code_revision=handler.code_revision,
            priority=(priority if priority is not None else _TASK_PRIORITIES.get(task.category, 50)),
            resource_class=(resource_class or task.category),
        )
        if not created and (
            job["task_name"] != task_name or job["parameters"] != normalized
        ):
            raise JobConflictError(
                "idempotency key is already associated with another request"
            )
        return job, created

    def get(self, job_id: int) -> dict:
        job = self._repository.get(job_id)
        if not job:
            raise JobNotFoundError(f"collection job not found: {job_id}")
        return job

    def list(
        self,
        *,
        task_name: str | None,
        status: str | None,
        api_name: str | None = None,
        period_key: str | None = None,
        completion_status: str | None = None,
        parent_job_id: int | None = None,
        job_kind: str | None = None,
        limit: int,
    ) -> list[dict]:
        if task_name and task_name != "collection_batch":
            self._registry.get(task_name)
        if status and status not in JOB_STATUSES:
            raise JobConflictError(f"unsupported job status: {status}")
        if completion_status and completion_status not in COMPLETION_STATUSES:
            raise JobConflictError(
                f"unsupported completion status: {completion_status}"
            )
        if job_kind and job_kind not in JOB_KINDS:
            raise JobConflictError(f"unsupported job kind: {job_kind}")
        return self._repository.list(
            task_name=task_name,
            status=status,
            api_name=api_name,
            period_key=period_key,
            completion_status=completion_status,
            parent_job_id=parent_job_id,
            job_kind=job_kind,
            limit=limit,
        )

    def retry(
        self,
        job_id: int,
        *,
        idempotency_key: str | None,
    ) -> tuple[dict, bool]:
        original = self.get(job_id)
        if original.get("job_kind") == "batch":
            raise JobConflictError(
                "batch parents cannot be retried; retry their failed child jobs"
            )
        if original["status"] != "failed":
            raise JobConflictError("only failed jobs can be retried")
        if original.get("parent_job_id"):
            parent = self._repository.get(original["parent_job_id"])
            if parent and parent.get("job_kind") == "batch":
                retried = self._repository.requeue_failed_batch_child(job_id)
                if not retried:
                    raise JobConflictError("failed batch child could not be requeued")
                return retried, True
        return self.submit(
            original["task_name"],
            original["parameters"],
            max_attempts=original["max_attempts"],
            idempotency_key=idempotency_key,
            parent_job_id=original["job_id"],
            api_name=original.get("api_name"),
            cadence=original.get("cadence"),
            period_key=original.get("period_key"),
            expected_for=original.get("expected_for"),
            priority=original.get("priority"),
            resource_class=original.get("resource_class"),
        )
