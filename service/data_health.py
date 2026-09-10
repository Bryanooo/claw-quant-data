"""One truthful data-health view across collection, freshness and coverage.

The individual subsystems intentionally answer different questions.  A
successful latest job does not prove historical coverage, and a non-empty
table does not prove that it is current.  This service keeps those dimensions
separate while presenting one prioritized issue ledger to operators.
"""

from __future__ import annotations

from datetime import date
from math import ceil
from typing import Any

from service.clock import business_now
from service.collection_monitor import CollectionMonitorService
from service.data_coverage.service import CoverageService
from service.data_service.service import DataService
from service.initialization.service import (
    FULL_INITIALIZATION_BASELINES,
    InitializationService,
)


_SEVERITY_ORDER = {"critical": 0, "warning": 1, "unknown": 2, "info": 3}
_DATASET_INTERFACE_ALIASES = {
    "financial_indicator": "fina_indicator",
    "forex_daily": "fx_daily",
    "industry_daily": "ths_daily",
    "stock_daily": "daily",
    "stock_daily_basic": "daily_basic",
    "stock_limit": "stk_limit",
    "stock_suspend": "suspend_d",
}
_INTERFACE_DATASET_ALIASES = {
    "disclosure_date": {"disclosure_date"},
    "express": {"express"},
    "express_vip": {"express"},
    "fina_mainbz": {"fina_mainbz"},
    "fina_mainbz_vip": {"fina_mainbz"},
    "forecast": {"forecast"},
    "forecast_vip": {"forecast"},
}


def _dataset_names_for_interface(api_name: str) -> set[str]:
    """Return public dataset names that are backed by one upstream API."""
    return {api_name} | _INTERFACE_DATASET_ALIASES.get(api_name, set()) | {
        dataset
        for dataset, interface in _DATASET_INTERFACE_ALIASES.items()
        if interface == api_name
    }


def _interface_has_stored_data(
    api_name: str, freshness_by_dataset: dict[str, dict[str, Any]]
) -> bool:
    return any(
        bool(item.get("latest_date")) or int(item.get("estimated_rows") or 0) > 0
        for dataset in _dataset_names_for_interface(api_name)
        if (item := freshness_by_dataset.get(dataset)) is not None
    )


class DataHealthService:
    def __init__(
        self,
        *,
        collection_service: CollectionMonitorService,
        coverage_service: CoverageService,
        data_service: DataService,
        initialization_service: InitializationService,
        delivery_service: Any | None = None,
    ):
        self._collection = collection_service
        self._coverage = coverage_service
        self._data = data_service
        self._initialization = initialization_service
        self._delivery = delivery_service

    def overview(self) -> dict[str, Any]:
        collection = self._collection.overview()
        coverage = self._coverage.overview()
        freshness = self._effective_freshness(
            collection, self._data.freshness()
        )
        freshness_by_dataset = {item["dataset"]: item for item in freshness}
        initialization = self._initialization.overview()
        delivery = self._delivery.today() if self._delivery is not None else None
        issues = self._issues(
            collection, coverage, freshness, initialization, delivery
        )

        collection_summary = collection["summary"]
        coverage_summary = coverage["summary"]
        collectable_interfaces = [
            item for item in collection["interfaces"] if item.get("collectable")
        ]
        initialization_running = bool(
            (initialization.get("active") or {}).get("status")
            in {"running", "attention", "paused"}
        )
        interfaces_without_evidence = [
            item
            for item in collectable_interfaces
            if not item.get("latest")
            and not _interface_has_stored_data(
                item["api_name"], freshness_by_dataset
            )
        ]
        pending_without_data = [
            item
            for item in collectable_interfaces
            if (item.get("latest") or {}).get("status")
            in {"queued", "running", "retrying"}
            and not _interface_has_stored_data(
                item["api_name"], freshness_by_dataset
            )
        ]
        backfill_pending = sum(
            initialization_running
            and (
                item.get("automatic_safe")
                or item["api_name"] in FULL_INITIALIZATION_BASELINES
            )
            for item in interfaces_without_evidence
        ) + len(pending_without_data)
        scope_required = sum(
            not item.get("automatic_safe")
            and item["api_name"] not in FULL_INITIALIZATION_BASELINES
            for item in interfaces_without_evidence
        )
        freshness_counts = {
            status: sum(item["status"] == status for item in freshness)
            for status in (
                "fresh", "stale", "empty", "event_driven",
                "not_configured", "not_applicable"
            )
        }
        scheduled_auditable = [
            item for item in coverage["datasets"]
            if item.get("auditable") and item.get("scheduled")
        ]
        scheduled_unaudited = sum(
            not item.get("latest") for item in scheduled_auditable
        )
        optional_unaudited = sum(
            item.get("auditable")
            and not item.get("scheduled")
            and not item.get("latest")
            for item in coverage["datasets"]
        )
        campaign = initialization.get("active") or initialization.get("latest")
        initialization_attention = bool(
            campaign and campaign.get("status") in {"attention", "paused"}
        )
        confirmed = sum(issue["confidence"] == "confirmed" for issue in issues)
        unknown = sum(issue["confidence"] == "unknown" for issue in issues)
        critical = sum(issue["severity"] == "critical" for issue in issues)
        informational = sum(issue["severity"] == "info" for issue in issues)
        actionable = sum(issue["severity"] != "info" for issue in issues)
        confirmed_data_issues = sum(
            issue["confidence"] == "confirmed"
            and issue["kind"] in {
                "coverage_gap", "dataset_empty", "stale_dataset",
                "collection_failed", "truncated", "incomplete",
            }
            for issue in issues
        )
        overall_status = (
            "critical"
            if critical or initialization_attention
            else "warning"
            if actionable or collection_summary["pending"]
            else "healthy"
        )

        return {
            "generated_at": business_now().isoformat(),
            "status": overall_status,
            "summary": {
                "interfaces": collection_summary["interfaces"],
                "collectable_interfaces": collection_summary["collectable"],
                "datasets": coverage_summary["datasets"],
                "fresh_datasets": freshness_counts["fresh"],
                "stale_datasets": freshness_counts["stale"],
                "empty_datasets": freshness_counts["empty"],
                "freshness_unconfigured": freshness_counts["not_configured"],
                "event_driven_datasets": freshness_counts["event_driven"],
                "not_applicable": freshness_counts["not_applicable"],
                "datasets_with_data": sum(
                    int(item.get("estimated_rows") or 0) > 0
                    for item in freshness
                ),
                "strictly_complete_interfaces": collection_summary["complete"],
                "never_collected_interfaces": sum(
                    bool(item.get("automatic_safe"))
                    and not initialization_running
                    for item in interfaces_without_evidence
                ),
                "backfill_pending_interfaces": backfill_pending,
                "scope_required_interfaces": scope_required,
                "verified_empty_interfaces": collection_summary.get("empty", 0),
                "unverified_interfaces": sum(
                    (item.get("latest") or {}).get("completion_status")
                    == "unverified"
                    for item in collectable_interfaces
                ),
                "unresolved_failures": collection_summary["unresolved_failures"],
                "audited_datasets": coverage_summary["audited"],
                "unaudited_datasets": (
                    coverage_summary["auditable"] - coverage_summary["audited"]
                ),
                "scheduled_unaudited_datasets": scheduled_unaudited,
                "optional_unaudited_datasets": optional_unaudited,
                "datasets_with_gaps": coverage_summary["with_gaps"],
                "missing_partitions": coverage_summary["missing_partitions"],
                "partial_partitions": coverage_summary["partial_partitions"],
                "critical_issue_count": critical,
                "actionable_issue_count": actionable,
                "informational_issue_count": informational,
                "confirmed_issue_count": confirmed,
                "confirmed_data_issue_count": confirmed_data_issues,
                "unknown_issue_count": unknown,
            },
            "history": self._history(initialization),
            "issues": issues,
            # Keep the source views so the dashboard renders one consistent
            # point-in-time snapshot instead of racing four independent calls.
            "collection": collection,
            "coverage": coverage,
            "freshness": freshness,
            "initialization": initialization,
        }

    def summary(self) -> dict[str, Any]:
        """Return a bounded operational preflight for humans and Agents.

        Full health intentionally evaluates freshness for every public table
        and delivery evidence for every scheduled interface. That is suitable
        for the dashboard but too expensive as the CLI's mandatory preflight.
        This summary uses already-aggregated collection, coverage and
        initialization evidence and links callers to the full view.
        """
        collection = self._collection.overview()
        coverage = self._coverage.overview()
        initialization = self._initialization.overview()
        delivery = self._delivery.today() if self._delivery is not None else None
        collection_summary = collection["summary"]
        coverage_summary = coverage["summary"]
        campaign = initialization.get("active") or initialization.get("latest")
        unhealthy_services = [
            item["component"]
            for item in collection.get("services", [])
            if item.get("status") != "healthy"
        ]
        confirmed_coverage_gaps = any(
            (item.get("latest") or {}).get("status") == "gaps"
            and self._pending_coverage_deadline(item, delivery) is None
            for item in coverage.get("datasets", [])
        )
        critical = bool(
            collection_summary.get("unresolved_failures")
            or confirmed_coverage_gaps
            or unhealthy_services
            or (campaign and campaign.get("status") in {"attention", "paused"})
        )
        pending = bool(
            collection_summary.get("pending")
            or collection_summary.get("running")
            or collection_summary.get("attention")
            or collection_summary.get("unverified")
            or coverage_summary.get("with_gaps")
            or (campaign and campaign.get("status") == "running")
        )
        return {
            "generated_at": business_now().isoformat(),
            "status": "critical" if critical else "warning" if pending else "healthy",
            "scope": "operational_preflight",
            "summary": {
                "interfaces": collection_summary.get("interfaces", 0),
                "collectable_interfaces": collection_summary.get("collectable", 0),
                "strictly_complete_interfaces": collection_summary.get("complete", 0),
                "pending_interfaces": collection_summary.get("pending", 0),
                "running_interfaces": collection_summary.get("running", 0),
                "unverified_interfaces": collection_summary.get("unverified", 0),
                "scope_required_interfaces": collection_summary.get("scope_required", 0),
                "not_collectable_interfaces": collection_summary.get("not_collectable", 0),
                "unresolved_failures": collection_summary.get("unresolved_failures", 0),
                "datasets": coverage_summary.get("datasets", 0),
                "datasets_with_gaps": coverage_summary.get("with_gaps", 0),
                "missing_partitions": coverage_summary.get("missing_partitions", 0),
                "partial_partitions": coverage_summary.get("partial_partitions", 0),
            },
            "history": campaign,
            "unhealthy_services": unhealthy_services,
            "full_health_url": "/api/v1/data-health",
        }

    @staticmethod
    def _effective_freshness(
        collection: dict[str, Any], freshness: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Use a recent verified empty check as freshness evidence.

        Event-driven tables can legitimately have no row on a trading day. In
        that case the newest physical row becomes old even though collection
        is healthy.  Only a bounded, verified empty task can override this
        table-level staleness; an unverified or old empty run cannot.
        """
        interfaces = {item["api_name"]: item for item in collection["interfaces"]}
        as_of = business_now().date()
        effective: list[dict[str, Any]] = []
        for original in freshness:
            item = dict(original)
            api_name = _DATASET_INTERFACE_ALIASES.get(
                item["dataset"], item["dataset"]
            )
            latest = (interfaces.get(api_name) or {}).get("latest") or {}
            evidence = latest.get("evidence") or {}
            checked_scope = latest.get("expected_for") or latest.get("period_key")
            try:
                checked_for = date.fromisoformat(str(checked_scope))
            except (TypeError, ValueError):
                checked_for = None
            sla_hours = item.get("freshness_sla_hours")
            recent_check = bool(
                checked_for
                and sla_hours is not None
                and (as_of - checked_for).days <= ceil(int(sla_hours) / 24)
            )
            if (
                item.get("status") == "stale"
                and latest.get("completion_status") == "empty"
                and evidence.get("verified") is True
                and recent_check
            ):
                item["status"] = "fresh"
                item["freshness_basis"] = "verified_empty_collection"
                item["latest_check_date"] = checked_for.isoformat()
            effective.append(item)
        return effective

    @staticmethod
    def _history(initialization: dict[str, Any]) -> dict[str, Any]:
        campaign = initialization.get("active") or initialization.get("latest")
        if not campaign:
            return {
                "status": "not_started",
                "complete": False,
                "message": "尚无可证明完成的初始化活动",
            }
        status = campaign.get("status")
        complete = status == "completed"
        return {
            "initialization_id": campaign.get("initialization_id"),
            "profile": campaign.get("profile"),
            "history_start": campaign.get("history_start"),
            "history_end": campaign.get("history_end"),
            "status": status,
            "complete": complete,
            "phase_name": campaign.get("phase_name"),
            "phase_index": campaign.get("phase_index"),
            "phase_total": campaign.get("phase_total"),
            "phase_planned_steps": campaign.get("planned_steps", 0),
            "phase_materialized_steps": campaign.get(
                "materialized_steps", campaign.get("planned_steps", 0)
            ),
            "phase_logical_total_steps": campaign.get(
                "logical_total_steps", campaign.get("planned_steps", 0)
            ),
            "phase_remaining_steps": campaign.get("remaining_steps", 0),
            "phase_progress_ratio": campaign.get("progress_ratio", 0.0),
            "phase_completed_steps": campaign.get("completed_steps", 0),
            "phase_failed_steps": campaign.get("failed_steps", 0),
            "completion_gate": campaign.get("completion_gate"),
            "work_window": campaign.get("work_window"),
            "message": (
                "全量历史初始化已经完成并通过验收"
                if complete
                else "初始化尚未完成；当前进度只代表当前阶段，不代表全历史完成率"
            ),
        }

    @classmethod
    def _issues(
        cls,
        collection: dict[str, Any],
        coverage: dict[str, Any],
        freshness: list[dict[str, Any]],
        initialization: dict[str, Any],
        delivery: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        issues: list[dict[str, Any]] = []
        auditable_names = {
            item["dataset"]
            for item in coverage["datasets"]
            if item.get("auditable")
        }
        campaign = initialization.get("active") or initialization.get("latest")
        initialization_running = bool(
            campaign
            and campaign.get("status") in {"running", "attention", "paused"}
        )
        freshness_by_dataset = {item["dataset"]: item for item in freshness}
        if campaign and campaign.get("status") in {"attention", "paused"}:
            issues.append(
                {
                    "severity": "critical",
                    "confidence": "confirmed",
                    "kind": "initialization_blocked",
                    "resource_type": "initialization",
                    "resource": f"初始化 #{campaign['initialization_id']}",
                    "scope": (
                        f"{campaign.get('history_start')} → "
                        f"{campaign.get('history_end')}"
                    ),
                    "detail": campaign.get("error_message") or "初始化已暂停",
                    "action": "检查失败步骤并恢复初始化",
                }
            )

        unresolved_names: set[str] = set()
        explained_dataset_names: set[str] = set()
        for item in collection["interfaces"]:
            api_name = item["api_name"]
            unresolved = item.get("unresolved_failure")
            latest = item.get("latest") or {}
            if unresolved:
                interface_datasets = _dataset_names_for_interface(api_name)
                unresolved_names.update(interface_datasets)
                explained_dataset_names.update(interface_datasets)
                auto_repair = bool(
                    item.get("automatic_safe")
                    and interface_datasets.intersection(auditable_names)
                )
                issues.append(
                    {
                        "severity": "critical",
                        "confidence": "confirmed",
                        "kind": unresolved["failure_type"],
                        "resource_type": "interface",
                        "resource": api_name,
                        "scope": unresolved.get("period_key")
                        or unresolved.get("expected_for")
                        or "未知周期",
                        "detail": unresolved.get("error_message") or "采集尚未恢复",
                        "action": (
                            "系统按业务日幂等重采并复审；持续不完整时保留告警"
                            if auto_repair
                            else "修复或重新采集该周期"
                        ),
                        "automatic_repair": auto_repair,
                        "api_name": api_name,
                        "job_id": unresolved.get("job_id"),
                        "partition_details": bool(
                            interface_datasets.intersection(auditable_names)
                        ),
                    }
                )
            elif latest.get("status") in {"queued", "running", "retrying"}:
                interface_datasets = _dataset_names_for_interface(api_name)
                explained_dataset_names.update(interface_datasets)
                issues.append(
                    {
                        "severity": "info",
                        "confidence": "planned",
                        "kind": "collection_pending",
                        "resource_type": "interface",
                        "resource": api_name,
                        "scope": latest.get("period_key") or "待执行任务",
                        "detail": (
                            "采集任务正在执行"
                            if latest.get("status") == "running"
                            else "采集任务已入队，等待可用 Worker 或接口请求窗口"
                        ),
                        "action": "等待任务完成；超出任务 SLA 后再升级为故障",
                        "api_name": api_name,
                    }
                )
            elif not latest and item.get("collectable"):
                interface_datasets = _dataset_names_for_interface(api_name)
                explained_dataset_names.update(interface_datasets)
                stored_data_exists = _interface_has_stored_data(
                    api_name, freshness_by_dataset
                )
                pending_initialization = bool(
                    initialization_running
                    and (
                        item.get("automatic_safe")
                        or api_name in FULL_INITIALIZATION_BASELINES
                    )
                )
                manual_scope_required = bool(
                    not item.get("automatic_safe")
                    and api_name not in FULL_INITIALIZATION_BASELINES
                )
                issues.append(
                    {
                        "severity": (
                            "info"
                            if (
                                pending_initialization
                                or stored_data_exists
                                or manual_scope_required
                            )
                            else "warning"
                        ),
                        "confidence": (
                            "planned"
                            if pending_initialization
                            else "observed"
                            if stored_data_exists
                            else "configuration"
                            if manual_scope_required
                            else "unknown"
                        ),
                        "kind": (
                            "initialization_pending"
                            if pending_initialization
                            else "collection_lineage_missing"
                            if stored_data_exists
                            else "manual_scope_required"
                            if manual_scope_required
                            else "never_collected"
                        ),
                        "resource_type": "interface",
                        "resource": api_name,
                        "scope": item.get("cadence") or "未配置",
                        "detail": (
                            "有权限接口将在当前全量初始化的后续基线阶段首采"
                            if pending_initialization
                            else "标准数据表已有记录，但缺少可关联的持久化采集任务谱系"
                            if stored_data_exists
                            else item.get("automatic_reason")
                            if manual_scope_required
                            else "有权限接口尚无任何采集任务记录"
                        ),
                        "action": (
                            "等待初始化进入最新基线阶段"
                            if pending_initialization
                            else "后续任务已写入规范接口标识；保留现有数据并补齐任务谱系"
                            if stored_data_exists
                            else "先配置明确且有界的标的或日期范围，再执行人工采集"
                            if manual_scope_required
                            else "配置安全参数或扇出策略后执行首采"
                        ),
                        "api_name": api_name,
                    }
                )
            elif latest.get("completion_status") == "unverified":
                pending_until = cls._pending_interface_deadline(
                    api_name, latest, delivery
                )
                issues.append(
                    {
                        "severity": "info" if pending_until else "unknown",
                        "confidence": "planned" if pending_until else "unknown",
                        "kind": (
                            "collection_verification_pending"
                            if pending_until
                            else "collection_unverified"
                        ),
                        "resource_type": "interface",
                        "resource": api_name,
                        "scope": latest.get("period_key") or "最近一次任务",
                        "detail": (
                            "本轮上游尚未发布可验证数据，仍处于自动复采窗口，"
                            f"截止时间 {pending_until}"
                            if pending_until
                            else latest.get("completion_reason")
                            or "任务成功，但没有严格完整性证据"
                        ),
                        "action": (
                            "等待后续计划轮次；截止后仍未验证将自动升级为故障"
                            if pending_until
                            else "补充分区、分页或标的覆盖证明"
                        ),
                        "api_name": api_name,
                    }
                )
            elif latest.get("completion_status") == "failed":
                explained_dataset_names.update(_dataset_names_for_interface(api_name))
                pending_initialization = bool(
                    initialization_running and api_name in FULL_INITIALIZATION_BASELINES
                )
                issues.append(
                    {
                        "severity": (
                            "info"
                            if pending_initialization
                            else "critical"
                            if item.get("automatic_safe")
                            else "info"
                        ),
                        "confidence": (
                            "planned"
                            if pending_initialization
                            else "confirmed"
                            if item.get("automatic_safe")
                            else "configuration"
                        ),
                        "kind": (
                            "initialization_pending"
                            if pending_initialization
                            else "collection_failed"
                            if item.get("automatic_safe")
                            else "manual_parameters_required"
                        ),
                        "resource_type": "interface",
                        "resource": api_name,
                        "scope": latest.get("period_key") or "手工探测",
                        "detail": latest.get("error_message") or "采集失败",
                        "action": (
                            "等待初始化进入全量扇出阶段"
                            if pending_initialization
                            else "等待自动重试或修复采集器"
                            if item.get("automatic_safe")
                            else "通过受控扇出任务提供必填参数"
                        ),
                        "api_name": api_name,
                    }
                )

        for item in coverage["datasets"]:
            latest = item.get("latest")
            if latest and latest.get("status") == "gaps":
                # A failed collection and its coverage audit are two pieces of
                # evidence for one operator incident.  Keep the richer
                # collection failure row instead of displaying the same
                # resource twice as two independent failures.
                if item["dataset"] in unresolved_names:
                    continue
                missing = int(latest.get("missing_partitions") or 0)
                partial = int(latest.get("partial_partitions") or 0)
                pending_until = cls._pending_coverage_deadline(item, delivery)
                if pending_until is not None:
                    issues.append(
                        {
                            "severity": "info",
                            "confidence": "planned",
                            "kind": "coverage_pending",
                            "resource_type": "dataset",
                            "resource": item["dataset"],
                            "scope": f"{latest['start_date']} → {latest['end_date']}",
                            "detail": (
                                "当前不完整分区仍处于上游发布与自动复采窗口，"
                                f"截止时间 {pending_until}"
                            ),
                            "action": "等待后续计划轮次；截止后仍不完整将自动升级为故障",
                            "dataset": item["dataset"],
                            "partition_details": True,
                        }
                    )
                    continue
                issues.append(
                    {
                        "severity": "critical",
                        "confidence": "confirmed",
                        "kind": "coverage_gap",
                        "resource_type": "dataset",
                        "resource": item["dataset"],
                        "scope": f"{latest['start_date']} → {latest['end_date']}",
                        "detail": f"{missing} 个日期缺失，{partial} 个日期截面不完整",
                        "action": "查看日期明细并补采",
                        "dataset": item["dataset"],
                        "partition_details": True,
                    }
                )
            elif item.get("auditable") and item.get("scheduled") and not latest:
                issues.append(
                    {
                        "severity": "unknown",
                        "confidence": "unknown",
                        "kind": "coverage_not_audited",
                        "resource_type": "dataset",
                        "resource": item["dataset"],
                        "scope": item.get("strategy") or "日期分区",
                        "detail": "数据集可以审计，但尚无覆盖审计记录",
                        "action": "执行首次覆盖审计",
                        "dataset": item["dataset"],
                    }
                )

        for item in freshness:
            status = item["status"]
            dataset = item["dataset"]
            if status == "stale":
                issues.append(
                    {
                        "severity": "critical",
                        "confidence": "confirmed",
                        "kind": "stale_dataset",
                        "resource_type": "dataset",
                        "resource": dataset,
                        "scope": str(item.get("latest_date") or "无日期"),
                        "detail": "最新分区已经超过数据集时效要求",
                        "action": "检查调度和上游发布时间并补采",
                        "dataset": dataset,
                        "partition_details": dataset in auditable_names,
                    }
                )
            elif status == "empty":
                # If the interface ledger already explains why the matching
                # dataset is empty (for example required fanout parameters),
                # show that actionable reason only once.
                if dataset in explained_dataset_names:
                    continue
                issues.append(
                    {
                        "severity": "warning",
                        "confidence": "confirmed",
                        "kind": "dataset_empty",
                        "resource_type": "dataset",
                        "resource": dataset,
                        "scope": "全表",
                        "detail": "当前标准数据服务没有可查询记录",
                        "action": "确认接口适用范围并执行首采",
                        "dataset": dataset,
                        "partition_details": dataset in auditable_names,
                    }
                )
            elif status == "not_configured":
                issues.append(
                    {
                        "severity": "unknown",
                        "confidence": "unknown",
                        "kind": "freshness_not_configured",
                        "resource_type": "dataset",
                        "resource": dataset,
                        "scope": str(item.get("latest_date") or "无日期"),
                        "detail": "有数据，但尚未定义何时算过期",
                        "action": "配置更新周期和发布时间容差",
                        "dataset": dataset,
                    }
                )

        issues.sort(
            key=lambda item: (
                _SEVERITY_ORDER[item["severity"]],
                item["kind"],
                item["resource"],
            )
        )
        return issues

    @staticmethod
    def _pending_coverage_deadline(
        coverage_item: dict[str, Any],
        delivery: dict[str, Any] | None,
    ) -> str | None:
        """Return a deadline when all reported gaps are still publishable.

        Collection-linked audits deliberately evaluate intraday partitions
        strictly so partial data cannot be promoted as complete. The operator
        view still respects the final delivery SLA and escalates only after
        the automatic retry window closes.
        """
        if not delivery:
            return None
        latest = coverage_item.get("latest") or {}
        issue_count = int(latest.get("missing_partitions") or 0) + int(
            latest.get("partial_partitions") or 0
        )
        if issue_count <= 0:
            return None
        start = str(latest.get("start_date") or "")
        end = str(latest.get("end_date") or "")
        recent = {
            str(value)
            for value in coverage_item.get("recent_missing") or []
            if start <= str(value) <= end
        }
        pending_dates: set[str] = set()
        deadlines: list[str] = []
        dataset = coverage_item["dataset"]
        for plan in delivery.get("items") or []:
            if plan.get("attention"):
                continue
            if plan.get("delivery_status") not in {
                "not_due",
                "queued",
                "running",
                "retrying",
                "waiting",
                "unverified",
                "verifying",
            }:
                continue
            expected_for = plan.get("expected_for")
            if not expected_for:
                continue
            if dataset not in _dataset_names_for_interface(
                str(plan.get("api_name") or "")
            ):
                continue
            expected = str(expected_for)
            if expected in recent:
                pending_dates.add(expected)
                deadlines.append(str(plan.get("due_at") or ""))
        if len(pending_dates) < issue_count:
            return None
        return max(deadlines) if deadlines else None

    @staticmethod
    def _pending_interface_deadline(
        api_name: str,
        latest: dict[str, Any],
        delivery: dict[str, Any] | None,
    ) -> str | None:
        """Return the deadline for the exact still-publishable queue job.

        Matching by durable work id is intentional: an unrelated future plan
        for the same interface must never hide a genuinely unverified older
        run.
        """
        if not delivery or latest.get("source") != "queue":
            return None
        work_id = latest.get("id")
        if work_id is None:
            return None
        pending_statuses = {
            "not_due", "queued", "running", "retrying", "waiting",
            "unverified", "verifying",
        }
        for plan in delivery.get("items") or []:
            if (
                plan.get("api_name") == api_name
                and plan.get("work_id") == work_id
                and not plan.get("attention")
                and plan.get("delivery_status") in pending_statuses
            ):
                return str(plan.get("due_at") or "") or None
        return None
