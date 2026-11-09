"""Stable operator-facing task and execution APIs.

These routes intentionally hide orchestration implementation generations from
the console.  A task is a versioned definition; an execution is one concrete
run of that definition.
"""

from datetime import date, datetime
from typing import Literal

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from service.api.dependencies import OrchestrationV2RepositoryDependency
from service.clock import business_now, business_today
from service.orchestration_v2.contracts import TASK_KEY_PATTERN
from service.orchestration_v2.late_repair import (
    LATE_PUBLISHED_DATASETS,
    next_late_repair_at,
)


router = APIRouter(prefix="/v1/ops", tags=["operations"])


@router.get("/factors/validation")
def factor_validation(trade_date: date | None = None) -> dict:
    """Operator comparison evidence, not a provider-value supply endpoint."""
    from service.research.local_factors.service import factor_validation_payload
    return factor_validation_payload(trade_date=trade_date)


@router.get("/factors/reference-plan")
def factor_reference_plan(trade_date: date) -> dict:
    """Preview reference-only requests without consuming provider quota."""
    from service.research.local_factors.reference_sampling import reference_sample_plan
    return reference_sample_plan(trade_date)


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
        eligible_at = execution.get("eligible_at")
        if isinstance(eligible_at, str):
            try:
                eligible_at = datetime.fromisoformat(eligible_at)
            except ValueError:
                eligible_at = None
        if (
            execution.get("status") in {"queued", "retrying"}
            and eligible_at is not None
            and eligible_at > business_now()
        ):
            return {
                "action": "wait_schedule",
                "resolution_state": "scheduled",
                "retryable": False,
                "eligible_at": eligible_at.isoformat(),
                "guidance": (
                    "已按安全时间窗预约执行，将在 "
                    f"{eligible_at.strftime('%m-%d %H:%M')} 自动开始；"
                    "这不是失败，也不需要人工重试"
                ),
            }
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
    if (
        category in {"data_incomplete", "completeness_guard"}
        and execution.get("task_key") in LATE_PUBLISHED_DATASETS
        and execution.get("trigger_source") == "schedule"
    ):
        next_repair = next_late_repair_at(business_now())
        return {
            "action": "wait_upstream",
            "resolution_state": "waiting_upstream",
            "retryable": False,
            "next_automatic_repair_at": next_repair.isoformat(),
            "guidance": (
                "采集与分页已完成，但上游尚未发布完整截面；系统会在"
                f" {next_repair.strftime('%m-%d %H:%M')} 自动做限定范围复查，"
                "无需人工重复提交"
            ),
        }
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
    cadence: Literal[
        "daily", "weekly", "monthly", "quarterly", "manual", "dependency",
    ] | None = None,
    before_id: int | None = Query(default=None, ge=1),
    limit: int = Query(default=50, ge=1, le=200),
) -> dict:
    items = repository.list_definitions(
        limit=limit + 1,
        before_id=before_id,
        lifecycle_status=lifecycle_status,
        workflow_kind=workflow_kind,
        cadence=cadence,
    )
    try:
        automation = repository.automation_states()
    except Exception:
        automation = {}
    try:
        from service.data_service.dependencies import task_asset_classes
        asset_classes = task_asset_classes()
    except Exception:
        asset_classes = {}
    from service.data_service.registry import DATASETS
    storage = {dataset.name: dataset.table for dataset in DATASETS.list()}
    for item in items:
        item['output_storage'] = [{'dataset': name, 'table': storage.get(name)}
                                  for name in item.get('output_datasets', [])]
        item['automation'] = (automation.get(item['task_key'])
                              if item.get('lifecycle_status') == 'active' else None)
        item['asset_class'] = asset_classes.get(item['task_key'])
    return _page(items, limit=limit, id_field="task_definition_id")


@router.get("/automation-audit")
def automation_audit(repository: OrchestrationV2RepositoryDependency) -> dict:
    states = repository.automation_states()
    return {'items': [{'task_key': key, **value} for key, value in sorted(states.items())],
            'configured_automatic': sum(value['automatic'] for value in states.values()),
            'without_automatic_entry': [key for key, value in sorted(states.items()) if not value['automatic']],
            'notice': '配置状态不等于进程健康、执行成功或数据完整；需结合实例与数据审计'}


@router.get("/tasks/{definition_id}")
def task_detail(
    definition_id: int,
    repository: OrchestrationV2RepositoryDependency,
) -> dict:
    definition = repository.get_definition(definition_id)
    if definition is None:
        raise HTTPException(status_code=404, detail="task definition not found")
    return {"task": definition}


@router.get("/tasks/{definition_id}/relationships")
def task_relationships(
    definition_id: int,
    repository: OrchestrationV2RepositoryDependency,
) -> dict:
    task = repository.get_definition(definition_id)
    if task is None:
        raise HTTPException(status_code=404, detail="task definition not found")
    endpoints = []
    for endpoint_id in task["definition"].get("acquisition_endpoint_ids", []):
        endpoint = repository.get_endpoint(endpoint_id)
        if endpoint:
            # Never expose credentials, request payloads or arbitrary provider
            # configuration through a navigation endpoint.
            endpoints.append({key: endpoint.get(key) for key in (
                "acquisition_endpoint_id", "source_id", "endpoint_key", "acquisition_mode",
            )})
    instances = repository.list_executions(task_key=task["task_key"], limit=10)
    ids = [item["task_execution_id"] for item in instances]
    states = repository.execution_output_states(ids)
    from service.data_service.registry import DATASETS
    tables = {dataset.name: dataset.table for dataset in DATASETS.list()}
    return {
        "task": task,
        "sources": endpoints,
        "output_storage": [{"dataset": name, "table": tables.get(name)}
                           for name in task["definition"].get("output_datasets", [])],
        "recent_executions": [{key: item.get(key) for key in (
            "task_execution_id", "task_definition_id", "definition_version", "status",
            "observation_start", "observation_end", "purpose", "current_node_key",
        )} for item in instances],
        "published_states": states[:200],
        "states_truncated": len(states) > 200,
        "semantics": "最近10次实例（含历史版本）的发布证据，不代表全历史完整性；任务与数据分别验收。",
    }


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
    total = repository.count_executions(
        status=execution_status,
        task_key=task_key,
    )
    for item in items:
        item["resolution"] = _resolution(item)
    result = _page(items, limit=limit, id_field="task_execution_id")
    result["page"]["total"] = total
    return result


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
    # A fan-out execution can freeze thousands of request checkpoints.  The
    # action response must stay small; callers that need the full scope and
    # node evidence can explicitly load the execution-detail endpoint.
    updated = retried[0]
    return {
        "execution": {
            key: updated.get(key)
            for key in (
                "task_execution_id", "task_key", "status",
                "current_node_key", "attempt_count", "max_attempts",
                "eligible_at", "updated_at",
            )
        },
        "message": "execution queued for retry",
    }
