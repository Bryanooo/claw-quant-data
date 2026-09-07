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
from service.initialization.service import FULL_FANOUT_BASELINES, InitializationService


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


def _dataset_names_for_interface(api_name: str) -> set[str]:
    """Return public dataset names that are backed by one upstream API."""
    return {api_name} | {
        dataset
        for dataset, interface in _DATASET_INTERFACE_ALIASES.items()
        if interface == api_name
    }


class DataHealthService:
    def __init__(
        self,
        *,
        collection_service: CollectionMonitorService,
        coverage_service: CoverageService,
        data_service: DataService,
        initialization_service: InitializationService,
    ):
        self._collection = collection_service
        self._coverage = coverage_service
        self._data = data_service
        self._initialization = initialization_service

    def overview(self) -> dict[str, Any]:
        collection = self._collection.overview()
        coverage = self._coverage.overview()
        freshness = self._effective_freshness(
            collection, self._data.freshness()
        )
        initialization = self._initialization.overview()
        issues = self._issues(collection, coverage, freshness, initialization)

        collection_summary = collection["summary"]
        coverage_summary = coverage["summary"]
        collectable_interfaces = [
            item for item in collection["interfaces"] if item.get("collectable")
        ]
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
                "strictly_complete_interfaces": collection_summary["complete"],
                "never_collected_interfaces": sum(
                    not item.get("latest") for item in collectable_interfaces
                ),
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
            period_key = latest.get("period_key")
            try:
                checked_for = date.fromisoformat(str(period_key))
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
    ) -> list[dict[str, Any]]:
        issues: list[dict[str, Any]] = []
        auditable_names = {
            item["dataset"]
            for item in coverage["datasets"]
            if item.get("auditable")
        }
        campaign = initialization.get("active") or initialization.get("latest")
        initialization_running = bool(
            campaign and campaign.get("status") == "running"
        )
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
                        "partition_details": bool(
                            interface_datasets.intersection(auditable_names)
                        ),
                    }
                )
            elif not latest and item.get("collectable"):
                explained_dataset_names.update(_dataset_names_for_interface(api_name))
                pending_initialization = bool(
                    initialization_running
                    and (
                        item.get("automatic_safe")
                        or api_name in FULL_FANOUT_BASELINES
                    )
                )
                issues.append(
                    {
                        "severity": "info" if pending_initialization else "warning",
                        "confidence": (
                            "planned" if pending_initialization else "unknown"
                        ),
                        "kind": (
                            "initialization_pending"
                            if pending_initialization
                            else "never_collected"
                        ),
                        "resource_type": "interface",
                        "resource": api_name,
                        "scope": item.get("cadence") or "未配置",
                        "detail": (
                            "有权限接口将在当前全量初始化的后续基线阶段首采"
                            if pending_initialization
                            else "有权限接口尚无任何采集任务记录"
                        ),
                        "action": (
                            "等待初始化进入最新基线阶段"
                            if pending_initialization
                            else "配置安全参数或扇出策略后执行首采"
                        ),
                        "api_name": api_name,
                    }
                )
            elif latest.get("completion_status") == "unverified":
                issues.append(
                    {
                        "severity": "unknown",
                        "confidence": "unknown",
                        "kind": "collection_unverified",
                        "resource_type": "interface",
                        "resource": api_name,
                        "scope": latest.get("period_key") or "最近一次任务",
                        "detail": latest.get("completion_reason")
                        or "任务成功，但没有严格完整性证据",
                        "action": "补充分区、分页或标的覆盖证明",
                        "api_name": api_name,
                    }
                )
            elif latest.get("completion_status") == "failed":
                explained_dataset_names.update(_dataset_names_for_interface(api_name))
                pending_initialization = bool(
                    initialization_running and api_name in FULL_FANOUT_BASELINES
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
