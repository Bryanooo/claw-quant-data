"""Stable operator-facing task and execution APIs.

These routes intentionally hide orchestration implementation generations from
the console.  A task is a versioned definition; an execution is one concrete
run of that definition.
"""

from datetime import date
from typing import Literal

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from service.api.dependencies import OrchestrationV2RepositoryDependency
from service.clock import business_today
from service.orchestration_v2.contracts import TASK_KEY_PATTERN


router = APIRouter(prefix="/v1/ops", tags=["operations"])


class RetryExecutionRequest(BaseModel):
    reason: str = Field(
        default="operator confirmed retry from dashboard",
        min_length=3,
        max_length=500,
    )


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


def _resolution(execution: dict) -> dict:
    if execution.get("status") != "attention":
        return {"action": "view", "retryable": False, "guidance": "查看节点与事件证据"}
    if execution.get("is_current_scope_execution") is False:
        latest_id = execution.get("latest_scope_execution_id")
        return {
            "action": "view_latest",
            "retryable": False,
            "latest_execution_id": latest_id,
            "guidance": f"历史失败记录；请查看同一数据周期的最新实例 #{latest_id}",
        }
    category = execution.get("final_error_category") or "unknown"
    if category in {"provider_transient", "rate_limited", "network", "database_transient", "lease_expired"}:
        return {
            "action": "retry",
            "retryable": True,
            "guidance": "上游或基础设施临时异常；确认已恢复后可重试",
        }
    if category in {"data_incomplete", "completeness_guard"}:
        return {
            "action": "inspect_then_retry",
            "retryable": True,
            "guidance": "数据完整性未通过；先查看校验证据，上游数据完整后再重试",
        }
    if category in {"permission_denied", "invalid_parameters", "invalid_scope", "contract_error"}:
        return {
            "action": "fix_definition",
            "retryable": False,
            "guidance": "配置、权限或任务范围错误；请修复任务定义后再执行",
        }
    return {
        "action": "inspect_then_retry",
        "retryable": True,
        "guidance": "原因尚未归类；先查看错误详情和节点事件，再决定是否重试",
    }


@router.get("/today")
def today_delivery(
    repository: OrchestrationV2RepositoryDependency,
    data_date: date | None = None,
) -> dict:
    return repository.today_delivery(data_date or business_today())


@router.get("/tasks")
def tasks(
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


@router.get("/tasks/{definition_id}")
def task_detail(
    definition_id: int,
    repository: OrchestrationV2RepositoryDependency,
) -> dict:
    definition = repository.get_definition(definition_id)
    if definition is None:
        raise HTTPException(status_code=404, detail="task definition not found")
    return {"task": definition}


@router.get("/executions")
def executions(
    repository: OrchestrationV2RepositoryDependency,
    execution_status: Literal[
        "created", "queued", "running", "waiting_dependency", "retrying",
        "validating", "publishing", "success", "attention", "superseded",
        "cancelled",
    ] | None = Query(default=None, alias="status"),
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
    for item in items:
        item["resolution"] = _resolution(item)
    return _page(items, limit=limit, id_field="task_execution_id")


@router.get("/executions/{execution_id}")
def execution_detail(
    execution_id: int,
    repository: OrchestrationV2RepositoryDependency,
) -> dict:
    execution = repository.get_execution(execution_id)
    if execution is None:
        raise HTTPException(status_code=404, detail="execution not found")
    execution["resolution"] = _resolution(execution)
    return {
        "execution": execution,
        "events": repository.list_execution_events(execution_id),
    }


@router.post("/executions/{execution_id}/retry", status_code=status.HTTP_202_ACCEPTED)
def retry_execution(
    execution_id: int,
    request: RetryExecutionRequest,
    repository: OrchestrationV2RepositoryDependency,
) -> dict:
    execution = repository.get_execution(execution_id)
    if execution is None:
        raise HTTPException(status_code=404, detail="execution not found")
    resolution = _resolution(execution)
    if execution.get("status") != "attention":
        raise HTTPException(status_code=409, detail="only attention executions can be retried")
    if not resolution["retryable"]:
        raise HTTPException(status_code=409, detail=resolution["guidance"])
    retried = repository.retry_attention_executions(
        (execution_id,),
        reason=request.reason,
    )
    if not retried:
        raise HTTPException(status_code=409, detail="execution state changed; refresh and retry")
    return {"execution": retried[0], "message": "execution queued for retry"}
