"""Derived-indicator API for the dashboard 数据派生 page.

Static metadata comes from :mod:`service.data_service.derivations` (compiled
from the code-owned transformation registry).  Runtime attachments — latest
task execution, dataset readiness and materialized date coverage — are merged
defensively so the page still renders when the control plane or database is
unavailable.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from service.api.dependencies import OrchestrationV2RepositoryDependency
from service.data_service.derivations import (
    date_coverage,
    derivation_inventory,
    derivation_summary,
    on_demand_catalog,
)

router = APIRouter(prefix="/v1/data/derivations", tags=["data: derivations"])


def _runtime_maps(repository) -> tuple[dict[str, dict], dict[str, dict], bool]:
    try:
        executions = repository.latest_execution_states()
        datasets = repository.latest_dataset_states()
        return executions, datasets, True
    except Exception:  # pragma: no cover - control plane unavailable
        return {}, {}, False


def _merge_runtime(
    rows: list[dict[str, Any]],
    executions: dict[str, dict],
    datasets: dict[str, dict],
) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    for item in rows:
        row = dict(item)
        execution = executions.get(row["key"])
        state = None
        ready = False
        observation_end = None
        for name in row["output_datasets"]:
            candidate = datasets.get(name)
            if not candidate:
                continue
            if state is None or str(candidate.get("observation_end") or "") > str(
                observation_end or ""
            ):
                state = candidate
                observation_end = candidate.get("observation_end")
                ready = bool(candidate.get("ready"))
        runtime: dict[str, Any] = {
            "latest_execution": dict(execution) if execution else None,
            "dataset_state": {
                "ready": ready,
                "observation_end": str(observation_end) if observation_end else None,
                "actual_count": state.get("actual_count") if state else None,
            }
            if state
            else None,
        }
        row["runtime"] = runtime
        merged.append(row)
    return merged


@router.get("/tasks")
def list_derivation_tasks(
    repository: OrchestrationV2RepositoryDependency,
) -> dict[str, Any]:
    rows = derivation_inventory()
    summary = derivation_summary()
    executions, datasets, runtime_available = _runtime_maps(repository)
    coverage_available = True
    try:
        coverage = date_coverage(rows)
    except Exception:  # pragma: no cover - database unavailable
        coverage = {row["key"]: None for row in rows}
        coverage_available = False
    items = _merge_runtime(rows, executions, datasets)
    for row in items:
        row["coverage"] = coverage.get(row["key"])
    return {
        "items": items,
        "total": len(items),
        "summary": summary,
        "runtime_available": runtime_available,
        "coverage_available": coverage_available,
    }


@router.get("/summary")
def derivation_summary_endpoint() -> dict[str, Any]:
    return derivation_summary()


@router.get("/ondemand")
def on_demand_indicators() -> dict[str, Any]:
    items = on_demand_catalog()
    return {"items": items, "total": len(items)}
