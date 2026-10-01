"""Read-only operations API for the isolated V2 orchestration control plane."""

from datetime import date
from typing import Literal

from fastapi import APIRouter, HTTPException, Query

from service.api.dependencies import OrchestrationV2RepositoryDependency
from service.orchestration_v2.catalog import task_baseline_summary
from service.orchestration_v2.contracts import DATASET_NAME_PATTERN, TASK_KEY_PATTERN
from service.clock import business_today


router = APIRouter(prefix="/v1/ops/orchestration-v2", tags=["operations"])


@router.get("/today")
def today_delivery(
    repository: OrchestrationV2RepositoryDependency,
    data_date: date | None = None,
) -> dict:
    return repository.today_delivery(data_date or business_today())


@router.get("/data-calendar")
def data_calendar(
    start_date: date,
    end_date: date,
    repository: OrchestrationV2RepositoryDependency,
) -> dict:
    if start_date > end_date:
        raise HTTPException(status_code=422, detail="start_date must not exceed end_date")
    return {
        "engine": "orchestration_v2",
        "start_date": start_date,
        "end_date": end_date,
        "days": repository.data_calendar(start_date, end_date),
    }


def _page(items: list[dict], *, limit: int, id_field: str) -> dict:
    has_more = len(items) > limit
    visible = items[:limit]
    return {
        "items": visible,
        "page": {
            "limit": limit,
            "has_more": has_more,
            "next_cursor": visible[-1][id_field] if has_more else None,
        },
    }


@router.get("/summary")
def summary(repository: OrchestrationV2RepositoryDependency) -> dict:
    """Return designed baseline and observed V2 control-plane counts."""

    return {
        "baseline": task_baseline_summary(),
        "control_plane": repository.control_plane_summary(),
        "activation": "active",
    }


@router.get("/definitions")
def definitions(
    repository: OrchestrationV2RepositoryDependency,
    lifecycle_status: Literal["draft", "active", "retired"] | None = None,
    workflow_kind: Literal["acquisition", "transformation"] | None = None,
    before_id: int | None = Query(default=None, ge=1),
    limit: int = Query(default=50, ge=1, le=200),
) -> dict:
    items = repository.list_definitions(
        limit=limit + 1,
        before_id=before_id,
        lifecycle_status=lifecycle_status,
        workflow_kind=workflow_kind,
    )
    return _page(items, limit=limit, id_field="task_definition_id")


@router.get("/executions")
def executions(
    repository: OrchestrationV2RepositoryDependency,
    execution_status: Literal[
        "created",
        "queued",
        "running",
        "waiting_dependency",
        "retrying",
        "validating",
        "publishing",
        "success",
        "attention",
        "superseded",
        "cancelled",
    ]
    | None = Query(default=None, alias="status"),
    task_key: str | None = Query(default=None, pattern=TASK_KEY_PATTERN),
    before_id: int | None = Query(default=None, ge=1),
    limit: int = Query(default=50, ge=1, le=200),
) -> dict:
    items = repository.list_executions(
        limit=limit + 1,
        before_id=before_id,
        status=execution_status,
        task_key=task_key,
    )
    return _page(items, limit=limit, id_field="task_execution_id")


@router.get("/executions/{execution_id}")
def execution_detail(
    execution_id: int,
    repository: OrchestrationV2RepositoryDependency,
) -> dict:
    execution = repository.get_execution(execution_id)
    if execution is None:
        raise HTTPException(status_code=404, detail="V2 execution not found")
    return {
        "execution": execution,
        "events": repository.list_execution_events(execution_id),
    }


@router.get("/dataset-states")
def dataset_states(
    repository: OrchestrationV2RepositoryDependency,
    data_status: Literal[
        "pending",
        "auditing",
        "complete",
        "empty_verified",
        "gaps",
        "partial",
        "indeterminate",
    ]
    | None = Query(default=None, alias="status"),
    dataset_name: str | None = Query(default=None, pattern=DATASET_NAME_PATTERN),
    before_id: int | None = Query(default=None, ge=1),
    limit: int = Query(default=50, ge=1, le=200),
) -> dict:
    items = repository.list_dataset_states(
        limit=limit + 1,
        before_id=before_id,
        data_status=data_status,
        dataset_name=dataset_name,
    )
    return _page(items, limit=limit, id_field="dataset_state_id")
