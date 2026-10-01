"""V2-native operational and data-readiness health projection."""

from __future__ import annotations

from datetime import date
from typing import Any

from service.clock import business_now
from service.data_coverage.service import CoverageService
from service.data_service.service import DataService
from service.initialization.service import InitializationService
from service.orchestration_v2.repository import OrchestrationV2Repository
from service.orchestration_v2.late_repair import next_late_repair_at
from service.research.readiness import evaluate_research_readiness


_ACTIVE = frozenset({
    "created", "queued", "running", "waiting_dependency", "retrying",
    "validating", "publishing",
})


class DataHealthService:
    def __init__(
        self,
        *,
        coverage_service: CoverageService,
        data_service: DataService,
        initialization_service: InitializationService,
        orchestration_repository: OrchestrationV2Repository,
        **_ignored: Any,
    ):
        self._coverage = coverage_service
        self._data = data_service
        self._initialization = initialization_service
        self._orchestration = orchestration_repository

    def overview(self) -> dict[str, Any]:
        control = self._orchestration.control_plane_summary()
        coverage = self._coverage.overview()
        initialization = self._initialization.overview()
        states = self._orchestration.latest_dataset_states()
        ledger_executions = control.get("executions", {})
        executions = control.get("current_executions") or ledger_executions
        active = sum(int(executions.get(status, 0)) for status in _ACTIVE)
        attention = int(executions.get("attention", 0))
        not_ready = [item for item in states.values() if not item.get("ready")]
        gaps = [
            item for item in states.values()
            if item.get("data_status") in {"gaps", "partial", "indeterminate"}
        ]
        issues = []
        now = business_now()
        late_repair_at = next_late_repair_at(now)
        for item in sorted(gaps, key=lambda row: row["dataset_name"]):
            late_published = item["dataset_name"] in {
                "ccass_hold", "etf_share_size", "margin", "margin_detail",
            }
            partition = None
            observation_start = item.get("observation_start")
            if isinstance(observation_start, str):
                try:
                    observation_start = date.fromisoformat(observation_start)
                except ValueError:
                    observation_start = None
            if observation_start and hasattr(self._coverage, "list_partitions"):
                detail = self._coverage.list_partitions(
                    item["dataset_name"],
                    start_date=observation_start,
                    end_date=observation_start,
                    status="problem",
                    limit=1,
                )
                partition = next(iter(detail.get("partitions", [])), None)
            issues.append({
                "kind": "dataset_not_ready",
                # Late-published data is a confirmed incomplete partition, but
                # it is not an operator failure while bounded rechecks are
                # scheduled.  Keeping it visible as ``waiting_upstream`` avoids
                # both false-green data and a false critical incident.
                "severity": "warning" if late_published else "critical",
                "confidence": "confirmed",
                "dataset": item["dataset_name"],
                "observation_key": item["observation_key"],
                "status": item["data_status"],
                "resolution_state": (
                    "waiting_upstream" if late_published else "operator_action_required"
                ),
                "actual_count": (
                    partition.get("entity_count") if partition else item.get("actual_count")
                ),
                "expected_count": (
                    partition.get("expected_entity_count") if partition else None
                ),
                "completeness_ratio": (
                    float(partition["entity_coverage_ratio"])
                    if partition and partition.get("entity_coverage_ratio") is not None
                    else None
                ),
                "action": (
                    "await the upstream late publication; a fresh bounded V2 "
                    "repair is scheduled automatically, then inspect the source "
                    "execution if the partition remains incomplete"
                    if late_published else
                    "inspect the source V2 execution and queue a scoped repair"
                ),
                "recovery_policy": (
                    "scheduled_late_repair" if late_published else "scoped_repair"
                ),
                "next_automatic_repair_at": (
                    late_repair_at.isoformat() if late_published else None
                ),
                "source_execution_id": item.get("source_execution_id"),
            })
        mapped_attention = {
            item["source_execution_id"]
            for item in issues
            if item.get("source_execution_id") is not None
        }
        unmapped_attention = max(0, attention - len(mapped_attention))
        operator_action_required = (
            sum(item["resolution_state"] == "operator_action_required" for item in issues)
            + unmapped_attention
        )
        waiting_upstream = sum(
            item["resolution_state"] == "waiting_upstream" for item in issues
        )
        status = (
            "critical"
            if operator_action_required
            else "warning"
            if active or not_ready or waiting_upstream
            else "healthy"
        )
        return {
            "generated_at": business_now().isoformat(),
            "engine": "orchestration_v2",
            "status": status,
            "summary": {
                "active_task_instances": active,
                "attention_task_instances": attention,
                "attention_attempts": int(ledger_executions.get("attention", 0)),
                "open_issues": len(issues),
                "operator_action_required": operator_action_required,
                "waiting_upstream": waiting_upstream,
                "datasets": coverage["summary"]["datasets"],
                "latest_dataset_states": len(states),
                "ready_dataset_states": sum(bool(item.get("ready")) for item in states.values()),
                "not_ready_dataset_states": len(not_ready),
                "datasets_with_gaps": coverage["summary"]["with_gaps"],
                "missing_partitions": coverage["summary"]["missing_partitions"],
                "partial_partitions": coverage["summary"]["partial_partitions"],
                "audited_datasets": coverage["summary"]["audited"],
                "strictly_verified_datasets": coverage["summary"].get("strictly_verified", 0),
            },
            "issues": issues,
            "control_plane": control,
            "coverage": coverage,
            "freshness": self._data.freshness(),
            "initialization": initialization,
        }

    def summary(self) -> dict[str, Any]:
        view = self.overview()
        return {
            "generated_at": view["generated_at"],
            "engine": view["engine"],
            "status": view["status"],
            "scope": "operational_preflight",
            "summary": view["summary"],
            "full_health_url": "/api/v1/ops/data-health",
        }

    def history_obligations(self) -> dict[str, Any]:
        coverage = self._coverage.overview()
        gaps = [
            item for item in coverage["datasets"]
            if (item.get("latest") or {}).get("status") in {"gaps", "unverified"}
        ]
        return {
            "generated_at": business_now().isoformat(),
            "engine": "orchestration_v2",
            "summary": {
                "datasets": coverage["summary"]["datasets"],
                "datasets_with_obligations": len(gaps),
                "missing_partitions": coverage["summary"]["missing_partitions"],
                "partial_partitions": coverage["summary"]["partial_partitions"],
            },
            "datasets": gaps,
        }

    def research_readiness(self) -> dict[str, Any]:
        """Project persisted data evidence into the research contract.

        Data readiness and task execution are deliberately reported as
        separate dimensions: a successful execution cannot certify a missing
        partition, and an active repair does not make existing data unusable.
        """

        evaluated = evaluate_research_readiness(
            coverage=self._coverage.overview(),
            freshness=self._data.freshness(),
            as_of=business_now().date(),
        )
        control = self._orchestration.control_plane_summary()
        executions = control.get("executions", {})
        active = sum(int(executions.get(status, 0)) for status in _ACTIVE)
        attention = int(executions.get("attention", 0))
        evaluated["task_execution"] = {
            "engine": "orchestration_v2",
            "status": (
                "attention" if attention else "active" if active else "idle"
            ),
            "active_instances": active,
            "attention_instances": attention,
            "executions": executions,
        }
        evaluated["initialization"] = self._initialization.overview()
        evaluated["generated_at"] = business_now().isoformat()
        return evaluated
