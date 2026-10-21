"""Interface-centric dependency inventory API for the dashboard 数据依赖 page.

The inventory itself is compiled from governed code-level catalog assets (see
:mod:`service.data_service.dependencies`).  This router only adds the runtime
projection: latest V2 execution state per task and latest published dataset
state, both read from the V2 control plane and attached defensively — the
inventory stays available even when the control-plane schema is absent.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from service.api.dependencies import OrchestrationV2RepositoryDependency
from service.data_service.dependencies import (
    dependency_summary,
    field_lineage,
    interface_detail,
    interface_inventory,
    merge_runtime,
)

router = APIRouter(prefix="/v1/data/dependencies", tags=["data: dependencies"])


def _runtime_maps(repository) -> tuple[dict[str, dict], dict[str, dict], bool]:
    """Read runtime snapshots; degrade gracefully when V2 is not installed."""
    try:
        executions = repository.latest_execution_states()
        datasets = repository.latest_dataset_states()
        return executions, datasets, True
    except Exception:  # pragma: no cover - control plane unavailable
        return {}, {}, False


def _filtered_items(
    *,
    source: str | None,
    status: str | None,
    category: str | None,
    query: str | None,
) -> list[dict[str, Any]]:
    items = interface_inventory()
    tokens = (query or "").strip().lower()
    if tokens:
        matched = []
        for item in items:
            haystack = " ".join(
                [
                    item["key"],
                    item.get("title") or "",
                    item.get("category") or "",
                    *(item.get("datasets") or []),
                    *(item.get("tables") or []),
                    *(task["task_key"] for task in item.get("tasks") or []),
                ]
            ).lower()
            if tokens in haystack:
                matched.append(item)
        items = matched
    if source:
        items = [item for item in items if item["source"] == source]
    if status:
        items = [item for item in items if item["status"] == status]
    if category:
        items = [item for item in items if item.get("category") == category]
    return items


@router.get("/summary")
def get_dependency_summary() -> dict:
    return dependency_summary()


@router.get("/interfaces")
def list_dependency_interfaces(
    repository: OrchestrationV2RepositoryDependency,
    source: str | None = Query(default=None),
    status: str | None = Query(default=None),
    category: str | None = Query(default=None),
    q: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=500),
) -> dict:
    items = _filtered_items(source=source, status=status, category=category, query=q)
    execution_states, dataset_states, runtime_available = _runtime_maps(repository)
    merged = merge_runtime(items, execution_states, dataset_states)
    total = len(merged)
    start = (page - 1) * page_size
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "runtime_available": runtime_available,
        "items": merged[start : start + page_size],
    }


@router.get("/interfaces/{source}/detail")
def get_dependency_interface(
    source: str,
    key: str = Query(..., description="Interface key, e.g. adj_factor or /api/v1/quote/basic-snapshot"),
) -> dict:
    detail = interface_detail(source, key)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"unknown interface: {source}/{key}")
    return {"interface": detail}


@router.get("/field-lineage")
def get_field_lineage(
    q: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=500),
) -> dict:
    items = field_lineage()
    tokens = (q or "").strip().lower()
    if tokens:
        matched = []
        for item in items:
            haystack = " ".join(
                [item["table"], *item["interfaces"],
                 *(field["name"] for field in item["fields"])]
            ).lower()
            if tokens in haystack:
                matched.append(item)
        items = matched
    total = len(items)
    start = (page - 1) * page_size
    return {"total": total, "page": page, "page_size": page_size, "items": items[start : start + page_size]}
