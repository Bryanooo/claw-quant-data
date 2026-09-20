"""Application service shared by the API and future MCP adapter."""

from datetime import date, datetime, time, timedelta

from service.clock import SHANGHAI_TIMEZONE

from service.collection_jobs.models import (
    JobConflictError,
    JobNotFoundError,
)
from service.collection_jobs.registry import TaskRegistry
from service.collection_jobs.fanout import FanoutPlanner

JOB_STATUSES = {"queued", "running", "success", "failed", "superseded"}
COMPLETION_STATUSES = {
    "pending", "running", "retrying", "complete", "empty",
    "verifying", "unverified", "page_complete", "incomplete", "failed",
    "superseded",
}
JOB_KINDS = {"leaf", "batch"}
INSTANCE_STATES = {
    "active", "attention", "recovered", "failure_history", "complete", "retry",
    "superseded",
}

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
        retry_of_job_id: int | None = None,
        retry_root_job_id: int | None = None,
        retry_generation: int = 0,
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
            retry_of_job_id=retry_of_job_id,
            retry_root_job_id=retry_root_job_id,
            retry_generation=retry_generation,
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
        job["attempts"] = self._repository.list_attempts(job_id)
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

    def page_instances(
        self,
        *,
        state: str | None,
        query: str | None,
        job_kind: str | None,
        resource_class: str | None,
        created_from: date | None,
        created_to: date | None,
        campaign_id: int | None,
        page: int,
        page_size: int,
    ) -> dict:
        if state and state not in INSTANCE_STATES:
            raise JobConflictError(f"unsupported instance state: {state}")
        if job_kind and job_kind not in JOB_KINDS:
            raise JobConflictError(f"unsupported job kind: {job_kind}")
        if created_from and created_to and created_from > created_to:
            raise JobConflictError("created_from must not be after created_to")
        from_time = (
            datetime.combine(created_from, time.min, SHANGHAI_TIMEZONE)
            if created_from else None
        )
        to_time = (
            datetime.combine(
                created_to + timedelta(days=1), time.min, SHANGHAI_TIMEZONE
            )
            if created_to else None
        )
        items, total = self._repository.page_instances(
            state=state,
            query=query.strip() if query else None,
            job_kind=job_kind,
            resource_class=resource_class,
            created_from=from_time,
            created_to=to_time,
            campaign_id=campaign_id,
            page=page,
            page_size=page_size,
        )
        total_pages = max(1, (total + page_size - 1) // page_size)
        return {
            "items": items,
            "page": {
                "number": page,
                "size": page_size,
                "total_items": total,
                "total_pages": total_pages,
                "has_previous": page > 1,
                "has_next": page < total_pages,
            },
        }

    def retry(
        self,
        job_id: int,
        *,
        idempotency_key: str | None,
    ) -> tuple[dict, bool]:
        # Retry decisions only need the execution-instance row. Attempt
        # history belongs to the detail view and must not affect control flow.
        original = self._repository.get(job_id)
        if not original:
            raise JobNotFoundError(f"collection job not found: {job_id}")
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
            retry_of_job_id=original["job_id"],
            retry_root_job_id=(
                original.get("retry_root_job_id") or original["job_id"]
            ),
            retry_generation=int(original.get("retry_generation") or 0) + 1,
            api_name=original.get("api_name"),
            cadence=original.get("cadence"),
            period_key=original.get("period_key"),
            expected_for=original.get("expected_for"),
            priority=original.get("priority"),
            resource_class=original.get("resource_class"),
        )
