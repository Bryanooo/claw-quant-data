#!/usr/bin/env python3
"""Generate a point-in-time, per-dataset assurance and repair report."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import date, datetime
import json
from pathlib import Path
from typing import Any

import psycopg2
import psycopg2.extras

from service.config import DB_CONFIG
from service.data_coverage.registry import COVERAGE_RULES
from service.data_coverage.repository import CoverageRepository
from service.clock import business_now
from service.orchestration_v2.catalog import (
    acquisition_task_blueprints,
    transformation_task_blueprints,
)
from service.orchestration_v2.audit_contracts import dataset_audit_contract
from service.orchestration_v2.repair_planning import observation_identity
from service.source_connectors.registry import SOURCE_REGISTRY


def _json_default(value: Any) -> str:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    raise TypeError(f"unsupported JSON value: {type(value).__name__}")


def _fetch_map(
    cursor, key: str, statement: str, parameters: tuple[Any, ...] = ()
) -> dict:
    cursor.execute(statement, parameters)
    return {row[key]: dict(row) for row in cursor.fetchall()}


def classify_repair_state(
    *,
    active: int,
    has_problem: bool,
    dataset_name: str,
    boundary_unverified_count: int,
    current_problem_count: int,
    stale_problem_count: int,
    automatic_safe: bool,
    latest_status: str,
    current_attention: int,
) -> str:
    """Name the operator action without inventing a missing-data claim."""

    if active:
        return "backfill_in_progress"
    if not has_problem:
        return "not_needed"
    if dataset_name == "tushare_raw":
        return "evidence_sidecar_not_applicable"
    if boundary_unverified_count and not current_problem_count:
        return "history_boundary_review"
    if stale_problem_count and not current_problem_count:
        return "reaudit_required"
    if current_problem_count and current_attention:
        return "attention_after_retry"
    if not automatic_safe:
        return "manual_scope_required"
    if latest_status == "unverified" and not current_problem_count:
        # A declared/observed scope can be fully present while the provider
        # exposes no authoritative per-dataset historical availability start
        # (a market trading calendar cannot prove that an API existed or
        # published that dataset on the same date). Calling that condition
        # "not_backfilled"
        # invents a missing-data claim and sends operators toward a repair
        # that cannot prove anything new.  Keep it fail-closed, but name the
        # assurance boundary.
        return "observed_scope_not_globally_provable"
    return "not_backfilled"


def build_report(job_start: int | None, job_end: int | None) -> dict:
    acquisition_tasks = acquisition_task_blueprints()
    all_tasks = (*acquisition_tasks, *transformation_task_blueprints())
    v2_task_by_dataset = {
        dataset_name: task.task_key
        for task in all_tasks
        for dataset_name in task.output_datasets
    }
    # stock_daily_basic is the governed public read view of daily_basic, not a
    # second acquisition product. tushare_raw is evidence written beside every
    # generic acquisition, so it intentionally has no standalone task.
    v2_task_by_dataset["stock_daily_basic"] = "daily_basic"
    automatic_task = {
        task.task_key: any(
            bool(
                SOURCE_REGISTRY.get_endpoint(
                    endpoint.source_id,
                    endpoint.endpoint_key,
                ).completeness_policy.get("automatic_safe")
            )
            for endpoint in task.endpoints
        )
        for task in acquisition_tasks
    }
    audit_filter = ""
    params: tuple[Any, ...] = ()
    if job_start is not None and job_end is not None:
        audit_filter = "WHERE job_id BETWEEN %s AND %s"
        params = (job_start, job_end)
    representative_audits = (
        CoverageRepository().latest_audits()
        if job_start is None and job_end is None
        else None
    )
    with psycopg2.connect(**DB_CONFIG) as connection, connection.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    ) as cursor:
        audits = representative_audits or _fetch_map(
            cursor,
            "dataset_name",
            f"""
                SELECT DISTINCT ON (dataset_name)
                       dataset_name, audit_id, job_id, status, start_date, end_date,
                       expected_partitions, present_partitions, missing_partitions,
                       partial_partitions, observed_partitions, coverage_ratio,
                       evidence, finished_at
                FROM sys_data_coverage_audit
                {audit_filter}
                ORDER BY dataset_name, end_date DESC, start_date ASC,
                         finished_at DESC, audit_id DESC
            """,
            params,
        )
        cursor.execute(
            """
            SELECT task_key AS api_name,
                   count(*) FILTER (
                       WHERE purpose IN ('backfill','initialization','repair')
                         AND status IN ('created','queued','waiting_dependency','retrying')
                   )::bigint AS queued,
                   count(*) FILTER (
                       WHERE purpose IN ('backfill','initialization','repair')
                         AND status='running'
                   )::bigint AS running,
                   count(*) FILTER (
                       WHERE purpose IN ('backfill','initialization','repair')
                         AND status='success'
                   )::bigint AS successful,
                   count(*) FILTER (
                       WHERE purpose IN ('backfill','initialization','repair')
                         AND status='attention'
                         AND NOT EXISTS (
                           SELECT 1
                           FROM orchestration_v2.task_execution AS recovered
                           WHERE recovered.task_key=execution.task_key
                             AND recovered.observation_key=execution.observation_key
                             AND recovered.status='success'
                             AND recovered.task_execution_id > execution.task_execution_id
                         )
                   )::bigint AS failure_history,
                   count(*) FILTER (
                       WHERE status='attention'
                         AND NOT EXISTS (
                           SELECT 1
                           FROM orchestration_v2.task_execution AS recovered
                           WHERE recovered.task_key=execution.task_key
                             AND recovered.observation_key=execution.observation_key
                             AND recovered.status='success'
                             AND recovered.task_execution_id > execution.task_execution_id
                         )
                   )::bigint AS current_attention
            FROM orchestration_v2.task_execution AS execution
            GROUP BY task_key
            """
        )
        job_stats = {row["api_name"]: dict(row) for row in cursor.fetchall()}
        cursor.execute(
            """
            WITH ranked AS (
                SELECT partition.dataset_name,
                       partition.partition_date,
                       partition.status,
                       COALESCE(
                           (audit.evidence->>'rule_revision')::INTEGER,
                           1
                       ) AS rule_revision,
                       row_number() OVER (
                           PARTITION BY partition.dataset_name,
                                        partition.partition_date,
                                        COALESCE(
                                            (audit.evidence->>'rule_revision')::INTEGER,
                                            1
                                        )
                           ORDER BY audit.finished_at DESC NULLS LAST,
                                    partition.audit_id DESC
                       ) AS position
                FROM sys_data_coverage_partition AS partition
                JOIN sys_data_coverage_audit AS audit USING (audit_id)
            )
            SELECT dataset_name,
                   rule_revision,
                   count(*) FILTER (WHERE status='missing')::INTEGER
                       AS missing_count,
                   count(*) FILTER (WHERE status='partial')::INTEGER
                       AS partial_count,
                   array_agg(partition_date ORDER BY partition_date)
                       FILTER (WHERE status='missing') AS missing_dates,
                   array_agg(partition_date ORDER BY partition_date)
                       FILTER (WHERE status='partial') AS partial_dates
            FROM ranked
            WHERE position=1 AND status IN ('missing','partial')
            GROUP BY dataset_name, rule_revision
            """
        )
        problems_by_revision: dict[tuple[str, int], dict] = {}
        stale_problem_totals: Counter[str] = Counter()
        for raw in cursor.fetchall():
            row = dict(raw)
            problems_by_revision[(row["dataset_name"], row["rule_revision"])] = row
            stale_problem_totals[row["dataset_name"]] += (
                int(row["missing_count"] or 0) + int(row["partial_count"] or 0)
            )
        cursor.execute(
            """
            SELECT partition.dataset_name,
                   COALESCE((audit.evidence->>'rule_revision')::INTEGER, 1)
                       AS rule_revision,
                   min(partition.partition_date) FILTER (
                       WHERE partition.status IN ('present','observed_only','partial')
                   ) AS first_observed_partition,
                   max(partition.partition_date) FILTER (
                       WHERE partition.status IN ('present','observed_only','partial')
                   ) AS last_observed_partition
            FROM sys_data_coverage_partition AS partition
            JOIN sys_data_coverage_audit AS audit USING (audit_id)
            GROUP BY partition.dataset_name,
                     COALESCE((audit.evidence->>'rule_revision')::INTEGER, 1)
            """
        )
        observed_bounds_by_revision = {
            (row["dataset_name"], row["rule_revision"]): dict(row)
            for row in cursor.fetchall()
        }
        cursor.execute(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema='orchestration_v2'
              AND table_type='BASE TABLE'
            """
        )
        v2_tables = {row["table_name"] for row in cursor.fetchall()}
        required_v2_tables = {
            "acquisition_endpoint",
            "task_definition",
            "task_execution",
            "task_execution_event",
            "dataset_state",
        }
        if not v2_tables:
            v2_control_plane_status = "not_installed"
        elif required_v2_tables <= v2_tables:
            v2_control_plane_status = "installed"
        else:
            v2_control_plane_status = "partial"

        v2_definitions: dict[str, str] = {}
        v2_repair_executions: dict[str, dict[str, int]] = {}
        verified_empty_dates: dict[str, set[date]] = defaultdict(set)
        if v2_control_plane_status == "installed":
            cursor.execute(
                """
                SELECT DISTINCT ON (task_key) task_key, lifecycle_status
                FROM orchestration_v2.task_definition
                ORDER BY task_key, version DESC
                """
            )
            v2_definitions = {
                row["task_key"]: row["lifecycle_status"]
                for row in cursor.fetchall()
            }
            cursor.execute(
                """
                SELECT task_key, status, count(*)::INTEGER AS count
                FROM orchestration_v2.task_execution
                WHERE purpose IN ('backfill','repair')
                GROUP BY task_key, status
                """
            )
            for row in cursor.fetchall():
                v2_repair_executions.setdefault(row["task_key"], {})[
                    row["status"]
                ] = row["count"]
            cursor.execute(
                """
                SELECT dataset_name, observation_end AS partition_date
                FROM orchestration_v2.dataset_state
                WHERE data_status='empty_verified'
                  AND ready
                  AND observation_end IS NOT NULL
                """
            )
            for row in cursor.fetchall():
                verified_empty_dates[row["dataset_name"]].add(
                    row["partition_date"]
                )

    rows: list[dict] = []
    for rule in COVERAGE_RULES.list():
        audit = audits.get(rule.dataset_name)
        api_name = rule.collection_api_name or rule.dataset_name
        job_keys = {api_name, rule.dataset_name}
        jobs = {
            field: sum(
                int(job_stats.get(key, {}).get(field) or 0) for key in job_keys
            )
            for field in (
                "queued", "running", "successful", "failure_history",
                "current_attention",
            )
        }
        problems = problems_by_revision.get(
            (rule.dataset_name, rule.revision),
            {},
        )
        raw_missing_dates = list(problems.get("missing_dates") or [])
        bounds = observed_bounds_by_revision.get(
            (rule.dataset_name, rule.revision),
            {},
        )
        proven_start = rule.availability_start or bounds.get(
            "first_observed_partition"
        )
        confirmed_missing_dates = [
            value for value in raw_missing_dates
            if (
                proven_start is not None
                and value >= proven_start
                and value not in verified_empty_dates[rule.dataset_name]
            )
        ]
        boundary_unverified_dates = [
            value for value in raw_missing_dates
            if (
                (proven_start is None or value < proven_start)
                and value not in verified_empty_dates[rule.dataset_name]
            )
        ]
        current_problem_count = len(confirmed_missing_dates) + int(
            problems.get("partial_count") or 0
        )
        current_rule_problem_count = len(raw_missing_dates) + int(
            problems.get("partial_count") or 0
        )
        stale_problem_count = max(
            0,
            stale_problem_totals[rule.dataset_name] - current_rule_problem_count,
        )
        v2_task_key = v2_task_by_dataset.get(rule.dataset_name)
        missing = len(confirmed_missing_dates)
        partial = int(problems.get("partial_count") or 0)
        audit_contract = dataset_audit_contract(rule.dataset_name)
        current_problem_dates = sorted({
            *confirmed_missing_dates,
            *(problems.get("partial_dates") or []),
        })
        repair_observation_keys = (
            sorted({
                observation_identity(
                    partition_date,
                    audit_contract.period_granularity,
                )
                for partition_date in current_problem_dates
            })
            if audit_contract.period_granularity
            not in {"snapshot", "dependency"}
            else []
        )
        active = int(jobs.get("queued") or 0) + int(jobs.get("running") or 0)
        latest_status = audit["status"] if audit else "not_audited"
        if missing or partial:
            assurance_status = "gaps"
        elif (
            boundary_unverified_dates
            or active
            or stale_problem_count
            or latest_status == "unverified"
        ):
            assurance_status = "unverified"
        else:
            assurance_status = latest_status
        has_problem = assurance_status in {"gaps", "unverified", "not_audited"}
        repair_state = classify_repair_state(
            active=active,
            has_problem=has_problem,
            dataset_name=rule.dataset_name,
            boundary_unverified_count=len(boundary_unverified_dates),
            current_problem_count=current_problem_count,
            stale_problem_count=stale_problem_count,
            automatic_safe=(
                automatic_task.get(v2_task_key, True)
                if v2_task_key else True
            ),
            latest_status=latest_status,
            current_attention=int(jobs.get("current_attention") or 0),
        )
        rows.append(
            {
                "dataset": rule.dataset_name,
                "table": rule.table,
                "api_name": api_name,
                "audit_capability": "available",
                "audit_mode": rule.strict_audit_mode,
                "absence_detection": (
                    "expected_calendar"
                    if rule.detects_missing_partitions
                    else "declared_collection_scope"
                    if rule.date_partitioned
                    else "exhaustive_snapshot"
                ),
                "audit_status": assurance_status,
                "latest_audit_status": latest_status,
                "audit_start": audit["start_date"] if audit else None,
                "audit_end": audit["end_date"] if audit else None,
                "verified_start": audit.get("verified_start_date") if audit else None,
                "verified_end": audit.get("verified_end_date") if audit else None,
                "expected_partitions": (
                    int(audit["expected_partitions"]) if audit else None
                ),
                "present_partitions": (
                    int(audit["present_partitions"]) if audit else None
                ),
                "missing_partitions": missing,
                "partial_or_unproven_partitions": partial,
                "stale_rule_problem_partitions": stale_problem_count,
                "missing_date_sample": confirmed_missing_dates[:20],
                "first_missing_date": (
                    confirmed_missing_dates[0]
                    if confirmed_missing_dates else None
                ),
                "last_missing_date": (
                    confirmed_missing_dates[-1]
                    if confirmed_missing_dates else None
                ),
                "history_boundary_unverified_partitions": len(
                    boundary_unverified_dates
                ),
                "history_boundary_unverified_sample": boundary_unverified_dates[:20],
                "history_boundary_unverified_start": (
                    boundary_unverified_dates[0]
                    if boundary_unverified_dates else None
                ),
                "history_boundary_unverified_end": (
                    boundary_unverified_dates[-1]
                    if boundary_unverified_dates else None
                ),
                "history_proven_start": proven_start,
                "partial_date_sample": list(problems.get("partial_dates") or [])[:20],
                "v2_period_granularity": audit_contract.period_granularity,
                "v2_repair_instance_count": len(repair_observation_keys),
                "v2_repair_observation_sample": repair_observation_keys[:20],
                "backfill_queued": int(jobs.get("queued") or 0),
                "backfill_running": int(jobs.get("running") or 0),
                "backfill_successful": int(jobs.get("successful") or 0),
                "failure_history": int(jobs.get("failure_history") or 0),
                "current_attention": int(jobs.get("current_attention") or 0),
                "repair_state": repair_state,
                "data_role": (
                    "collection_evidence"
                    if rule.dataset_name == "tushare_raw"
                    else "business_dataset"
                ),
                "v2_task_key": v2_task_key,
                "v2_baseline_covered": v2_task_key is not None,
                "v2_definition_status": (
                    v2_definitions.get(v2_task_key, "not_staged")
                    if v2_task_key
                    and v2_control_plane_status == "installed"
                    else v2_control_plane_status
                    if v2_task_key
                    else "not_applicable"
                ),
                "v2_repair_executions": (
                    v2_repair_executions.get(v2_task_key, {})
                    if v2_task_key
                    else {}
                ),
            }
        )

    task_periods: dict[str, set[str]] = {}
    task_datasets: dict[str, set[str]] = {}
    for row in rows:
        task_key = row["v2_task_key"]
        if not task_key or row["data_role"] != "business_dataset":
            continue
        task_periods.setdefault(task_key, set()).update(
            row["v2_repair_observation_sample"]
        )
        task_datasets.setdefault(task_key, set()).add(row["dataset"])
    task_repair_plan = [
        {
            "task_key": task_key,
            "datasets": sorted(task_datasets[task_key]),
            # Exact count is calculated from current partition rows below;
            # samples remain bounded in the per-dataset presentation.
            "repair_instance_count": 0,
            "observation_sample": sorted(task_periods[task_key])[:20],
        }
        for task_key in sorted(task_datasets)
    ]
    # Compute exact unique task-period counts without materializing task
    # executions. Alias datasets (for example stock_daily_basic/daily_basic)
    # intentionally collapse into the same execution identity.
    task_period_identities: dict[str, set[str]] = {}
    for row in rows:
        task_key = row["v2_task_key"]
        if not task_key or row["data_role"] != "business_dataset":
            continue
        problem = problems_by_revision.get((row["dataset"], COVERAGE_RULES.get(row["dataset"]).revision), {})
        granularity = row["v2_period_granularity"]
        if granularity in {"snapshot", "dependency"}:
            continue
        proven_start = row["history_proven_start"]
        dates = {
            *(
                value
                for value in (problem.get("missing_dates") or [])
                if (
                    proven_start is not None
                    and value >= proven_start
                    and value not in verified_empty_dates[row["dataset"]]
                )
            ),
            *(problem.get("partial_dates") or []),
        }
        task_period_identities.setdefault(task_key, set()).update(
            observation_identity(value, granularity) for value in dates
        )
    for item in task_repair_plan:
        identities = task_period_identities.get(item["task_key"], set())
        item["repair_instance_count"] = len(identities)
        item["observation_sample"] = sorted(identities)[:20]

    audit_statuses = Counter(row["audit_status"] for row in rows)
    latest_audit_statuses = Counter(row["latest_audit_status"] for row in rows)
    repair_states = Counter(row["repair_state"] for row in rows)
    modes = Counter(row["audit_mode"] for row in rows)
    business_rows = [row for row in rows if row["data_role"] == "business_dataset"]
    business_statuses = Counter(row["audit_status"] for row in business_rows)
    return {
        "generated_at": business_now(),
        "scope": {
            "job_start_id": job_start,
            "job_end_id": job_end,
            "datasets": len(rows),
            "business_datasets": len(business_rows),
            "evidence_datasets": len(rows) - len(business_rows),
        },
        "semantics": {
            "task_success_is_not_data_completeness": True,
            "missing": "expected logical partition has no verified data",
            "partial": "data exists but entity or exhaustive transport proof is incomplete",
            "unverified": "the system cannot yet prove completeness; it is not treated as complete",
            "failure_history": "immutable historical count; consult effective failures for current incidents",
        },
        "summary": {
            "audit_capability_available": sum(
                row["audit_capability"] == "available" for row in rows
            ),
            "audit_capability_missing": sum(
                row["audit_capability"] != "available" for row in rows
            ),
            "audit_modes": dict(sorted(modes.items())),
            "audit_statuses": dict(sorted(audit_statuses.items())),
            "business_assurance_statuses": dict(sorted(business_statuses.items())),
            "latest_scoped_audit_statuses": dict(
                sorted(latest_audit_statuses.items())
            ),
            "repair_states": dict(sorted(repair_states.items())),
            "v2_control_plane_status": v2_control_plane_status,
            "v2_baseline_covered_business_datasets": sum(
                row["v2_baseline_covered"] for row in business_rows
            ),
            "v2_baseline_unmapped_business_datasets": sum(
                not row["v2_baseline_covered"] for row in business_rows
            ),
            "v2_backfill_or_repair_executions": sum(
                sum(row["v2_repair_executions"].values()) for row in rows
            ),
            "v2_repair_instances_required": sum(
                len(values) for values in task_period_identities.values()
            ),
            "confirmed_missing_partitions": sum(
                row["missing_partitions"] or 0 for row in rows
            ),
            "partial_or_unproven_partitions": sum(
                row["partial_or_unproven_partitions"] or 0 for row in rows
            ),
            "history_boundary_unverified_partitions": sum(
                row["history_boundary_unverified_partitions"] for row in rows
            ),
            "stale_rule_problem_partitions": sum(
                row["stale_rule_problem_partitions"] for row in rows
            ),
        },
        "datasets": rows,
        "v2_task_repair_plan": task_repair_plan,
    }


def render_markdown(report: dict) -> str:
    summary = report["summary"]
    lines = [
        "# 全量数据集严格审计报告",
        "",
        f"生成时间：`{report['generated_at'].isoformat()}`",
        "",
        "## 结论摘要",
        "",
        f"- 数据集：{report['scope']['datasets']}；具备审计能力：{summary['audit_capability_available']}；缺少审计能力：{summary['audit_capability_missing']}。",
        f"- 审计模式：`{summary['audit_modes']}`。",
        f"- 业务数据综合状态：`{summary['business_assurance_statuses']}`；最新有界审计状态：`{summary['latest_scoped_audit_statuses']}`。",
        f"- 已确认缺失分区：{summary['confirmed_missing_partitions']}；存在数据但不完整/缺少传输证明：{summary['partial_or_unproven_partitions']}。",
        f"- 数据集历史可用起点尚未证明、不得直接当成缺失的候选分区：{summary['history_boundary_unverified_partitions']}。",
        f"- 旧规则遗留、必须重审后才能判定的分区：{summary['stale_rule_problem_partitions']}。",
        f"- 补采状态：`{summary['repair_states']}`。",
        f"- V2：控制面 `{summary['v2_control_plane_status']}`；业务数据集基线映射 {summary['v2_baseline_covered_business_datasets']}/{report['scope']['business_datasets']}；现有 V2 补采/修复实例 {summary['v2_backfill_or_repair_executions']}；按任务×逻辑周期仍需 {summary['v2_repair_instances_required']} 个实例。",
        "",
        "> `success` 只表示任务执行完成；“最新有界审计通过”也不自动等于全部历史完整。综合状态还会合并全历史分区账本、旧规则版本和活动补采。`unverified` 不得解释为完整。",
        "",
        "## 逐数据集明细",
        "",
        "| 数据集 | 审计模式 | 状态 | 缺失 | 部分/未证明 | 补采队列/运行 | 处理状态 | V2 任务/定义 | 缺失日期样例 |",
        "|---|---|---:|---:|---:|---:|---|---|---|",
    ]
    for row in report["datasets"]:
        sample = ", ".join(str(item) for item in row["missing_date_sample"][:5])
        if not sample:
            sample = ", ".join(str(item) for item in row["partial_date_sample"][:5])
        lines.append(
            "| {dataset} | {audit_mode} | {audit_status} | {missing} | {partial} | {queued}/{running} | {repair_state} | {v2_task}/{v2_definition} | {sample} |".format(
                dataset=row["dataset"],
                audit_mode=row["audit_mode"],
                audit_status=row["audit_status"],
                missing=row["missing_partitions"] if row["missing_partitions"] is not None else "—",
                partial=row["partial_or_unproven_partitions"] if row["partial_or_unproven_partitions"] is not None else "—",
                queued=row["backfill_queued"],
                running=row["backfill_running"],
                repair_state=row["repair_state"],
                v2_task=row["v2_task_key"] or "—",
                v2_definition=row["v2_definition_status"],
                sample=sample or "—",
            )
        )
    planned = [
        item for item in report["v2_task_repair_plan"]
        if item["repair_instance_count"]
    ]
    lines.extend([
        "",
        "## V2 缺口实例规划（只读）",
        "",
        "| 任务 | 逻辑周期实例数 | 输出数据集 | 周期样例 |",
        "|---|---:|---|---|",
    ])
    for item in sorted(
        planned,
        key=lambda value: (-value["repair_instance_count"], value["task_key"]),
    ):
        lines.append(
            "| {task} | {count} | {datasets} | {sample} |".format(
                task=item["task_key"],
                count=item["repair_instance_count"],
                datasets=", ".join(item["datasets"]),
                sample=", ".join(item["observation_sample"][:5]) or "—",
            )
        )
    lines.extend(
        [
            "",
            "## 口径",
            "",
            "- `expected_partition`：有明确交易日/月/季度预期，可发现从未采集的日期。",
            "- `observed_scope_transport`：稀疏事件不虚构每日必须有数据；按声明的采集范围、分页耗尽和终态证明审计。",
            "- `exhaustive_snapshot`：无日期数据必须有全量快照成功证明、有效空结果证明或完整分页证明。",
            "- `backfill_in_progress`：存在历史/初始化/修复 V2 执行实例；盘中统一延后到 16:00 后执行。",
            "- `not_backfilled`：存在缺口或未验证状态，但当前没有对应 V2 执行实例，需要补计划或人工判定上游边界。",
            "- `history_boundary_review`：候选日期早于本地首个已观测分区，但上游没有给出该数据集的权威可用起点。交易日历只能证明市场开市，不能证明接口当日已经存在或应发布；在补充契约起点前不得把这些日期误报为缺失。",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--job-start-id", type=int)
    parser.add_argument("--job-end-id", type=int)
    parser.add_argument(
        "--json-output", default="reports/dataset_audit_latest.json"
    )
    parser.add_argument(
        "--markdown-output", default="reports/dataset_audit_latest.md"
    )
    args = parser.parse_args()
    report = build_report(args.job_start_id, args.job_end_id)
    json_path = Path(args.json_output)
    markdown_path = Path(args.markdown_output)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, default=_json_default) + "\n",
        encoding="utf-8",
    )
    markdown_path.write_text(render_markdown(report), encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False, default=_json_default))


if __name__ == "__main__":
    main()
