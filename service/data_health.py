"""V2-native operational and data-readiness health projection."""

from __future__ import annotations

from datetime import date
from typing import Any

from service.clock import business_now
from service.data_coverage.service import CoverageService
from service.data_service.service import DataService
from service.initialization.service import InitializationService
from service.orchestration_v2.repository import OrchestrationV2Repository
from service.orchestration_v2.gap_repair import dataset_task_map
from service.orchestration_v2.late_repair import (
    LATE_PUBLISHED_DATASETS,
    next_late_repair_at,
)
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
        running = sum(
            int(executions.get(status, 0))
            for status in ("running", "validating", "publishing")
        )
        queued = sum(
            int(executions.get(status, 0))
            for status in ("created", "queued")
        )
        retrying = int(executions.get("retrying", 0))
        waiting_dependency = int(executions.get("waiting_dependency", 0))
        attention = int(executions.get("attention", 0))
        expected_states = [
            item for item in states.values()
            if item.get("expectation_status", "expected") == "expected"
        ]
        not_expected_states = [
            item for item in states.values()
            if item.get("expectation_status") == "not_expected"
        ]
        not_ready = [item for item in expected_states if not item.get("ready")]
        gaps = [
            item for item in expected_states
            if item.get("data_status") in {"gaps", "partial", "indeterminate"}
        ]
        issues = []
        now = business_now()
        late_repair_at = next_late_repair_at(now)
        covered_attention = set(
            self._orchestration.attention_covered_by_active_execution_ids()
        )
        for item in sorted(gaps, key=lambda row: row["dataset_name"]):
            late_published = item["dataset_name"] in LATE_PUBLISHED_DATASETS
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
                "severity": (
                    "warning"
                    if late_published
                    or item.get("source_execution_id") in covered_attention
                    else "critical"
                ),
                "confidence": "confirmed",
                "dataset": item["dataset_name"],
                "observation_key": item["observation_key"],
                "status": item["data_status"],
                "resolution_state": (
                    "waiting_upstream"
                    if late_published
                    else "repair_in_progress"
                    if item.get("source_execution_id") in covered_attention
                    else "operator_action_required"
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
                    "wait for the newer covering V2 repair and its independent "
                    "validation; inspect that recovery only if it later fails"
                    if item.get("source_execution_id") in covered_attention else
                    "inspect the source V2 execution and queue a scoped repair"
                ),
                "recovery_policy": (
                    "scheduled_late_repair"
                    if late_published
                    else "active_covering_repair"
                    if item.get("source_execution_id") in covered_attention
                    else "scoped_repair"
                ),
                "next_automatic_repair_at": (
                    late_repair_at.isoformat() if late_published else None
                ),
                "source_execution_id": item.get("source_execution_id"),
            })
        # Latest-delivery readiness and full-history coverage answer different
        # questions.  A dataset can serve its newest partition while older
        # audited periods are still absent (notably quota-limited US history).
        # Keep those obligations visible in the same action centre instead of
        # reporting a misleading zero merely because today's state is ready.
        active_task_keys = set(control.get("current_active_tasks", {}))
        task_by_dataset = dataset_task_map()
        issue_datasets = {item["dataset"] for item in issues}
        for item in coverage.get("datasets", []):
            latest = item.get("latest") or {}
            dataset_name = item.get("dataset")
            if (
                not dataset_name
                or dataset_name in issue_datasets
                or latest.get("status") != "gaps"
            ):
                continue
            task_key = task_by_dataset.get(dataset_name, dataset_name)
            recovery_active = task_key in active_task_keys
            issues.append({
                "kind": "historical_coverage_gap",
                "severity": "warning" if recovery_active else "critical",
                "confidence": "confirmed",
                "dataset": dataset_name,
                "observation_key": (
                    f"{latest.get('start_date')}..{latest.get('end_date')}"
                ),
                "status": "gaps",
                "resolution_state": (
                    "repair_in_progress"
                    if recovery_active
                    else "operator_action_required"
                ),
                "actual_count": latest.get("present_partitions"),
                "expected_count": latest.get("expected_partitions"),
                "completeness_ratio": latest.get("coverage_ratio"),
                "action": (
                    "历史补采已在自动执行队列中；查看该任务的重试/限频状态和覆盖审计"
                    if recovery_active
                    else "历史覆盖存在确认缺口且没有活动恢复实例；创建有界 V2 补采"
                ),
                "recovery_policy": (
                    "active_history_repair"
                    if recovery_active
                    else "scoped_history_repair"
                ),
                "next_automatic_repair_at": None,
                "source_execution_id": None,
                "task_key": task_key,
                "missing_partitions": int(latest.get("missing_partitions") or 0),
                "partial_partitions": int(latest.get("partial_partitions") or 0),
            })
            issue_datasets.add(dataset_name)
        mapped_attention = {
            item["source_execution_id"]
            for item in issues
            if item.get("source_execution_id") is not None
        }
        covered_unmapped_attention = covered_attention - mapped_attention
        execution_issue_ids: set[int] = set()
        if hasattr(self._orchestration, "list_executions"):
            attention_executions = self._orchestration.list_executions(
                status="attention", limit=5000
            )
            for execution in attention_executions:
                execution_id = int(execution["task_execution_id"])
                if (
                    not execution.get("is_current_scope_execution", True)
                    or execution_id in mapped_attention
                    or execution_id in covered_attention
                ):
                    continue
                category = execution.get("final_error_category") or "unknown"
                if category in {
                    "provider_transient", "rate_limited", "network",
                    "database_transient", "lease_expired",
                }:
                    guidance = (
                        "上游或基础设施临时异常；查看执行证据，确认恢复后可重试。"
                    )
                elif category in {"data_incomplete", "completeness_guard"}:
                    guidance = (
                        "采集已完成但完整性校验未通过；检查数据证据后做范围补采。"
                    )
                elif category in {
                    "permission_denied", "invalid_parameters", "invalid_scope",
                    "contract_error",
                }:
                    guidance = "任务配置、权限或范围错误；修复任务定义后重新执行。"
                else:
                    guidance = "执行异常尚未归类；先查看节点事件和错误详情。"
                issues.append({
                    "kind": "task_execution_attention",
                    "severity": "critical",
                    "confidence": "confirmed",
                    "dataset": execution.get("task_key") or "unknown_task",
                    "observation_key": execution.get("observation_key") or "—",
                    "status": "attention",
                    "resolution_state": "operator_action_required",
                    "actual_count": None,
                    "expected_count": None,
                    "completeness_ratio": None,
                    "action": guidance,
                    "recovery_policy": "inspect_execution",
                    "next_automatic_repair_at": None,
                    "source_execution_id": execution_id,
                    "error_category": category,
                    "error_message": execution.get("final_error_message"),
                })
                execution_issue_ids.add(execution_id)
        unmapped_attention = max(
            0, attention - len(mapped_attention) - len(covered_unmapped_attention)
            - len(execution_issue_ids),
        )
        operator_action_required = (
            sum(item["resolution_state"] == "operator_action_required" for item in issues)
            + unmapped_attention
        )
        waiting_upstream = sum(
            item["resolution_state"] == "waiting_upstream" for item in issues
        )
        repair_in_progress = (
            sum(
                item["resolution_state"] == "repair_in_progress"
                for item in issues
            )
            + len(covered_unmapped_attention)
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
                "running_task_instances": running,
                "queued_task_instances": queued,
                "retrying_task_instances": retrying,
                "waiting_dependency_task_instances": waiting_dependency,
                "attention_task_instances": attention,
                "attention_attempts": int(ledger_executions.get("attention", 0)),
                "open_issues": len(issues) + unmapped_attention,
                "operator_action_required": operator_action_required,
                "waiting_upstream": waiting_upstream,
                "repair_in_progress": repair_in_progress,
                "datasets": coverage["summary"]["datasets"],
                "latest_dataset_states": len(expected_states),
                "observed_dataset_states": len(states),
                "not_expected_dataset_states": len(not_expected_states),
                "ready_dataset_states": sum(
                    bool(item.get("ready")) for item in expected_states
                ),
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
