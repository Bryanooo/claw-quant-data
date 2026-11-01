"""V2-native operational and data-readiness health projection."""

from __future__ import annotations

from datetime import date
from typing import Any

from service.clock import business_now
from service.config import V2_TRANSIENT_RECOVERY_MAX_ROUNDS
from service.data_coverage.service import CoverageService
from service.data_service.service import DataService
from service.initialization.service import InitializationService
from service.orchestration_v2.repository import OrchestrationV2Repository
from service.orchestration_v2.gap_repair import dataset_task_map
from service.orchestration_v2.late_repair import (
    LATE_PUBLISHED_DATASETS,
    next_late_repair_at,
)
from service.orchestration_v2.recovery_policy import DEFERRED_RESEARCH_DATASETS
from service.research.readiness import evaluate_research_readiness


_ACTIVE = frozenset({
    "created", "queued", "running", "waiting_dependency", "retrying",
    "validating", "publishing",
})


def _scope_covers(execution: dict, task_key: str, start, end, key=None) -> bool:
    if execution.get('task_key') != task_key:
        return False
    def parsed(value):
        if value is None:
            return None
        return date.fromisoformat(str(value)[:10])
    try:
        left, right = parsed(start), parsed(end)
        active_left = parsed(execution.get('observation_start'))
        active_right = parsed(execution.get('observation_end'))
    except ValueError:
        return False
    if left is not None and right is not None:
        return (active_left is not None and active_right is not None
                and active_left <= left <= right <= active_right)
    return bool(key and execution.get('observation_key') == key)


def _scope_overlaps(execution: dict, task_key: str, start, end) -> bool:
    if execution.get('task_key') != task_key:
        return False
    try:
        left, right, active_left, active_right = (
            date.fromisoformat(str(value)[:10]) for value in (
                start, end, execution.get('observation_start'), execution.get('observation_end')
            )
        )
        return max(left, active_left) <= min(right, active_right)
    except (TypeError, ValueError):
        return False


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
        active_task_keys = set(control.get("current_active_tasks", {}))
        recovery_rounds = (
            self._orchestration.transient_recovery_rounds()
            if hasattr(self._orchestration, 'transient_recovery_rounds') else {}
        )
        active_scopes = (
            self._orchestration.active_recovery_scopes()
            if hasattr(self._orchestration, 'active_recovery_scopes') else []
        )

        def _is_deferred_inactive(dataset_name: str) -> bool:
            return (
                dataset_name in DEFERRED_RESEARCH_DATASETS
                and dataset_name not in active_task_keys
            )

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
            and not _is_deferred_inactive(item.get("dataset_name", ""))
        ]
        not_expected_states = [
            item for item in states.values()
            if item.get("expectation_status") == "not_expected"
            or _is_deferred_inactive(item.get("dataset_name", ""))
        ]
        not_ready = [item for item in expected_states if not item.get("ready")]
        gaps = [
            item for item in expected_states
            if item.get("data_status") in {"gaps", "partial", "indeterminate"}
        ]
        issues = []
        now = business_now()
        late_repair_at = next_late_repair_at(now)
        task_by_dataset = dataset_task_map()
        covered_attention = set(
            self._orchestration.attention_covered_by_active_execution_ids()
        )
        for item in sorted(gaps, key=lambda row: row["dataset_name"]):
            late_published = item["dataset_name"] in LATE_PUBLISHED_DATASETS
            recovery_active = (
                any(_scope_covers(
                    execution,
                    task_by_dataset.get(item['dataset_name'], item['dataset_name']),
                    item.get('observation_start'), item.get('observation_end'),
                    item.get('observation_key'),
                ) for execution in active_scopes)
            )
            repair_in_progress = (
                recovery_active
                or item.get("source_execution_id") in covered_attention
            )
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
                    or repair_in_progress
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
                    if repair_in_progress
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
                    "当日上游截面不完整，系统将按限定范围复查；若持续缺失，检查来源实例的实体缺口。"
                    if late_published else
                    "已有覆盖此范围的恢复实例；等待采集和独立校验，若失败再处理该恢复实例。"
                    if repair_in_progress else
                    "查看来源实例的校验证据，确认缺失字段或证券后按范围修复；重试成功不等于数据完整。"
                ),
                "recovery_policy": (
                    "scheduled_late_repair"
                    if late_published
                    else "active_covering_repair"
                    if repair_in_progress
                    else "scoped_repair"
                ),
                "next_automatic_repair_at": (
                    late_repair_at.isoformat() if late_published else None
                ),
                "source_execution_id": item.get("source_execution_id"),
            })
        # Latest-delivery readiness and full-history coverage answer different
        for issue in issues:
            if (issue['dataset'] == 'local_factor_snapshot'
                    and hasattr(self._orchestration, 'factor_input_issues')):
                issue['input_issues'] = self._orchestration.factor_input_issues(
                    issue['observation_key']
                )
                issue['action'] = (
                    '本地因子已计算，但部分证券的财报输入缺失或公式结果尚未完成归因。'
                    '下方为主要受影响因子及证券数；应先核对原始字段和公告日期，'
                    '不能用其他财报字段替代，也不能靠反复重算消除缺口。'
                )
        # Latest-delivery readiness and full-history coverage answer different
        # questions.  A dataset can serve its newest partition while older
        # audited periods are still absent (notably quota-limited US history).
        # Keep those obligations visible in the same action centre instead of
        # reporting a misleading zero merely because today's state is ready.
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
            recovery_active = any(_scope_covers(
                execution, task_key,
                latest.get('effective_start_date') or latest.get('start_date'),
                latest.get('end_date'),
            ) for execution in active_scopes)
            if (
                dataset_name in DEFERRED_RESEARCH_DATASETS
                and not recovery_active
            ):
                continue
            issues.append({
                "kind": "historical_coverage_gap",
                "severity": "warning" if recovery_active else "critical",
                "confidence": "confirmed",
                "dataset": dataset_name,
                "observation_key": (
                    f"{latest.get('effective_start_date') or latest.get('start_date')}"
                    f"..{latest.get('end_date')}"
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
                    else "历史覆盖仍有确认缺口；当前没有覆盖整个缺口范围的活动恢复实例，请核对已有分段补采计划，勿重复创建"
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
        # A bounded historical segment does not cover the whole obligation.
        # Show its real progress without clearing the remaining gap alarm.
        for issue in issues:
            if issue['kind'] != 'historical_coverage_gap':
                continue
            start, end = issue['observation_key'].split('..', 1)
            segments = [execution for execution in active_scopes if _scope_overlaps(
                execution, issue['task_key'], start, end,
            )]
            if segments:
                issue['active_recovery_segments'] = [{
                    key: execution.get(key) for key in (
                        'task_execution_id', 'status', 'observation_start', 'observation_end'
                    )
                } for execution in segments]
                if issue['resolution_state'] != 'repair_in_progress':
                    issue['action'] = (
                        '部分历史区间正在补采（见下方实例）；其余缺口仍未验收，'
                        '请勿重复提交正在执行的范围。'
                    )
        mapped_attention = {
            item["source_execution_id"]
            for item in issues
            if item.get("source_execution_id") is not None
        }
        covered_unmapped_attention = covered_attention - mapped_attention
        execution_issue_ids: set[int] = set()
        classified_attention_ledger = False
        if hasattr(self._orchestration, "list_executions"):
            classified_attention_ledger = True
            attention_executions = self._orchestration.list_executions(
                status="attention", limit=5000
            )
            # An execution ledger preserves every failed business period, but
            # the action centre must not turn that immutable history into one
            # incident per date.  Current dataset state and full-history
            # coverage already report data obligations.  For failures without
            # such state (for example an upstream request that produced no
            # rows), retain only the newest unresolved incident per task.
            newest_attention_by_task: dict[str, int] = {}
            for execution in attention_executions:
                task_key = execution.get("task_key") or "unknown_task"
                execution_id = int(execution["task_execution_id"])
                newest_attention_by_task[task_key] = max(
                    execution_id,
                    newest_attention_by_task.get(task_key, 0),
                )
            task_outputs: dict[str, set[str]] = {}
            for dataset_name, task_key in task_by_dataset.items():
                task_outputs.setdefault(task_key, set()).add(dataset_name)
            issue_task_keys = {
                task_by_dataset.get(item["dataset"], item.get("task_key"))
                for item in issues
            }

            def _date_value(value: Any) -> date | None:
                if isinstance(value, date):
                    return value
                if isinstance(value, str):
                    try:
                        return date.fromisoformat(value[:10])
                    except ValueError:
                        return None
                return None

            def _covered_by_ready_latest_state(execution: dict) -> bool:
                outputs = task_outputs.get(execution.get("task_key") or "", set())
                if not outputs:
                    return False
                execution_end = _date_value(execution.get("observation_end"))
                for dataset_name in outputs:
                    state = states.get(dataset_name)
                    if not state or not state.get("ready"):
                        return False
                    state_end = _date_value(state.get("observation_end"))
                    if execution_end and (state_end is None or state_end < execution_end):
                        return False
                return True

            for execution in attention_executions:
                execution_id = int(execution["task_execution_id"])
                task_key = execution.get("task_key") or "unknown_task"
                if (
                    _is_deferred_inactive(task_key)
                    or
                    not execution.get("is_current_scope_execution", True)
                    or any(_scope_covers(
                        active_execution, task_key,
                        execution.get('observation_start'), execution.get('observation_end'),
                        execution.get('observation_key'),
                    ) for active_execution in active_scopes)
                    or execution_id in mapped_attention
                    or execution_id in covered_attention
                    or newest_attention_by_task.get(task_key) != execution_id
                    or task_key in issue_task_keys
                    or _covered_by_ready_latest_state(execution)
                ):
                    continue
                category = execution.get("final_error_category") or "unknown"
                rate_limited = category == "rate_limited"
                transient = category in {
                    "provider_transient", "network",
                    "database_transient", "lease_expired",
                }
                exhausted = (rate_limited or transient) and (
                    recovery_rounds.get(execution_id, 0) >= V2_TRANSIENT_RECOVERY_MAX_ROUNDS
                )
                if exhausted:
                    rate_limited = transient = False
                if rate_limited:
                    guidance = (
                        "上游明确返回限频；不要立即重复重试，等待额度窗口恢复或下一调度周期。"
                    )
                elif transient:
                    guidance = (
                        "上游或基础设施临时异常；系统会在冷却窗口后自动续跑已验证检查点，"
                        "无需立即人工重复提交。"
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
                if exhausted:
                    guidance = "自动恢复预算已耗尽；检查上游连接、额度和执行证据，修复后再重试。"
                issues.append({
                    "kind": "task_execution_attention",
                    "severity": "warning" if rate_limited or transient else "critical",
                    "confidence": "confirmed",
                    "dataset": task_key,
                    "observation_key": execution.get("observation_key") or "—",
                    "status": "attention",
                    "resolution_state": (
                        "waiting_upstream"
                        if rate_limited or transient
                        else "operator_action_required"
                    ),
                    "actual_count": None,
                    "expected_count": None,
                    "completeness_ratio": None,
                    "action": guidance,
                    "recovery_policy": (
                        "scheduled_next_run"
                        if rate_limited
                        else "automatic_transient_recovery"
                        if transient
                        else "inspect_execution"
                    ),
                    "next_automatic_repair_at": None,
                    "source_execution_id": execution_id,
                    "error_category": category,
                    "automatic_recovery_exhausted": exhausted,
                    "error_message": execution.get("final_error_message"),
                })
                execution_issue_ids.add(execution_id)
        # When the repository exposes the ledger, every actionable execution
        # has just been classified explicitly.  The remaining attention rows
        # are historical attempts, not hidden incidents.  Older repositories
        # retain the conservative count-only fallback.
        unmapped_attention = 0 if classified_attention_ledger else max(
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
            + (0 if classified_attention_ledger else len(covered_unmapped_attention))
        )
        coverage_rows = coverage.get("datasets", [])
        expected_coverage_rows = [
            item for item in coverage_rows
            if not _is_deferred_inactive(item.get("dataset", ""))
        ]
        deferred_coverage_rows = [
            item for item in coverage_rows
            if _is_deferred_inactive(item.get("dataset", ""))
        ]
        audited_coverage_rows = [
            item for item in expected_coverage_rows if item.get("latest")
        ]
        gap_coverage_rows = [
            item for item in audited_coverage_rows
            if item["latest"].get("status") == "gaps"
        ]
        # Datasets parked on purpose (provider quota / deferred research) are
        # kept out of the operational scope so they never raise an incident, but
        # they still hold real gaps.  Reporting only the filtered numbers made
        # this summary look like it contradicted ``/api/v1/ops/coverage`` (2 vs 4
        # datasets with gaps); the totals below reconcile the two views.
        deferred_gap_coverage_rows = [
            item for item in deferred_coverage_rows
            if (item.get("latest") or {}).get("status") == "gaps"
        ]
        all_audited_coverage_rows = [
            item for item in coverage_rows if item.get("latest")
        ]

        def _sum_partitions(rows: list[dict], field: str) -> int:
            return sum(int(item["latest"].get(field) or 0) for item in rows)

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
                "deferred_coverage_datasets": len(deferred_coverage_rows),
                "datasets_with_gaps": len(gap_coverage_rows),
                "missing_partitions": _sum_partitions(audited_coverage_rows, "missing_partitions"),
                "partial_partitions": _sum_partitions(audited_coverage_rows, "partial_partitions"),
                "audited_datasets": len(audited_coverage_rows),
                "strictly_verified_datasets": sum(
                    item["latest"].get("status") in {"complete", "empty"}
                    for item in audited_coverage_rows
                ),
                "coverage_scope": {
                    "total_datasets": len(coverage_rows),
                    "audited_datasets": len(all_audited_coverage_rows),
                    "operational_datasets": len(expected_coverage_rows),
                    "deferred_datasets": [
                        item.get("dataset") for item in deferred_coverage_rows
                    ],
                    "deferred_fields": [
                        "datasets_with_gaps",
                        "missing_partitions",
                        "partial_partitions",
                    ],
                },
                "deferred_datasets_with_gaps": len(deferred_gap_coverage_rows),
                "deferred_missing_partitions": _sum_partitions(
                    deferred_coverage_rows, "missing_partitions"
                ),
                "total_datasets_with_gaps": (
                    len(gap_coverage_rows) + len(deferred_gap_coverage_rows)
                ),
                "total_missing_partitions": _sum_partitions(
                    all_audited_coverage_rows, "missing_partitions"
                ),
                "total_partial_partitions": _sum_partitions(
                    all_audited_coverage_rows, "partial_partitions"
                ),
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
