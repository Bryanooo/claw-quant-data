"""Translate current strict-audit gaps into idempotent V2 repair executions."""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from typing import Iterable

import psycopg2
import psycopg2.extras

from service.config import APP_REVISION, DB_CONFIG
from service.data_coverage.registry import COVERAGE_RULES
from service.orchestration_v2.catalog import (
    acquisition_task_blueprints,
    transformation_task_blueprints,
)
from service.orchestration_v2.contracts import ExecutionRequest, TaskDefinitionDocument
from service.orchestration_v2.repair_planning import (
    RepairInstanceProposal,
    plan_period_repairs,
)
from service.orchestration_v2.service import OrchestrationV2Service


def dataset_task_map() -> dict[str, str]:
    tasks = (*acquisition_task_blueprints(), *transformation_task_blueprints())
    result = {
        dataset_name: task.task_key
        for task in tasks
        for dataset_name in task.output_datasets
    }
    result["stock_daily_basic"] = "daily_basic"
    return result


def current_problem_partitions(
    *,
    start_date: date | None = None,
    end_date: date | None = None,
) -> dict[str, dict[date, str]]:
    """Return only current-rule, post-availability confirmed problems."""
    with psycopg2.connect(**DB_CONFIG) as connection, connection.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    ) as cursor:
        cursor.execute(
            """
            WITH ranked AS (
                SELECT partition.dataset_name,
                       partition.partition_date,
                       partition.status,
                       COALESCE((audit.evidence->>'rule_revision')::INTEGER,1)
                           AS rule_revision,
                       row_number() OVER (
                           PARTITION BY partition.dataset_name,
                                        partition.partition_date,
                                        COALESCE((audit.evidence->>'rule_revision')::INTEGER,1)
                           ORDER BY audit.finished_at DESC NULLS LAST,
                                    partition.audit_id DESC
                       ) AS position
                FROM sys_data_coverage_partition AS partition
                JOIN sys_data_coverage_audit AS audit USING (audit_id)
            )
            SELECT dataset_name,
                   rule_revision,
                   array_agg(partition_date ORDER BY partition_date)
                       FILTER (WHERE status='missing') AS missing_dates,
                   array_agg(partition_date ORDER BY partition_date)
                       FILTER (WHERE status='partial') AS partial_dates,
                   min(partition_date) FILTER (
                       WHERE status IN ('present','observed_only','partial')
                   ) AS first_observed_partition
            FROM ranked
            WHERE position=1
            GROUP BY dataset_name, rule_revision
            """
        )
        rows = {
            (row["dataset_name"], int(row["rule_revision"])): dict(row)
            for row in cursor.fetchall()
        }
        cursor.execute(
            """
            SELECT dataset_name, observation_end AS partition_date
            FROM orchestration_v2.dataset_state
            WHERE data_status='empty_verified'
              AND ready
              AND observation_end IS NOT NULL
            """
        )
        verified_empty_dates: dict[str, set[date]] = defaultdict(set)
        for row in cursor.fetchall():
            verified_empty_dates[row["dataset_name"]].add(row["partition_date"])

    result: dict[str, dict[date, str]] = {}
    for rule in COVERAGE_RULES.list():
        row = rows.get((rule.dataset_name, rule.revision), {})
        proven_start = rule.availability_start or row.get(
            "first_observed_partition"
        )
        problems: dict[date, str] = {}
        for value in row.get("missing_dates") or ():
            if (
                proven_start is not None
                and value >= proven_start
                and (start_date is None or value >= start_date)
                and (end_date is None or value <= end_date)
                and value not in verified_empty_dates.get(rule.dataset_name, set())
            ):
                problems[value] = "missing"
        for value in row.get("partial_dates") or ():
            if (
                (start_date is None or value >= start_date)
                and (end_date is None or value <= end_date)
            ):
                problems[value] = "partial"
        if problems:
            result[rule.dataset_name] = problems
    return result


def plan_current_repairs(
    repository,
    *,
    start_date: date | None = None,
    end_date: date | None = None,
) -> tuple[RepairInstanceProposal, ...]:
    task_by_dataset = dataset_task_map()
    by_task: dict[str, dict[str, dict[date, str]]] = defaultdict(dict)
    for dataset_name, problems in current_problem_partitions(
        start_date=start_date,
        end_date=end_date,
    ).items():
        task_key = task_by_dataset.get(dataset_name)
        if task_key:
            by_task[task_key][dataset_name] = problems

    proposals: list[RepairInstanceProposal] = []
    for task_key, problems in sorted(by_task.items()):
        definition = repository.get_active_definition(task_key)
        if not definition:
            continue
        document = TaskDefinitionDocument.model_validate(definition["definition"])
        proposals.extend(plan_period_repairs(
            task_key=task_key,
            contracts=document.validation_contract.dataset_audits,
            problem_partitions=problems,
        ))
    return tuple(sorted(
        proposals,
        key=lambda item: (item.observation_start or date.min, item.task_key),
        reverse=True,
    ))


def create_repair_executions(
    repository,
    *,
    proposals: Iterable[RepairInstanceProposal],
    limit: int | None = None,
    actor_revision: str = APP_REVISION,
    image_digest: str = "runtime-local",
    purpose: str = "repair",
    trigger_source: str = "recovery",
    frozen_scope_extra: dict | None = None,
    idempotency_prefix: str | None = None,
) -> dict:
    service = OrchestrationV2Service(
        repository,
        allowed_handler_keys=(),
        known_datasets=(),
    )
    selected = tuple(proposals)
    if limit is not None:
        selected = selected[:limit]
    created = 0
    existing = 0
    execution_id_sample: list[int] = []
    first_execution_id: int | None = None
    last_execution_id: int | None = None
    by_task: dict[str, int] = defaultdict(int)
    for proposal in selected:
        row, was_created = service.create_execution(ExecutionRequest(
            task_key=proposal.task_key,
            purpose=purpose,
            trigger_source=trigger_source,
            idempotency_key=(
                f"{idempotency_prefix}:{proposal.task_key}:"
                f"{proposal.observation_key}"
                if idempotency_prefix
                else proposal.idempotency_key
            ),
            observation_key=proposal.observation_key,
            observation_start=proposal.observation_start,
            observation_end=proposal.observation_end,
            observation_period=proposal.observation_period,
            frozen_scope={
                "planner": "strict_audit_v2",
                "datasets": list(proposal.datasets),
                "reasons": list(proposal.reasons),
                **(frozen_scope_extra or {}),
            },
            app_revision=actor_revision,
            image_digest=image_digest,
        ))
        execution_id = int(row["task_execution_id"])
        first_execution_id = first_execution_id or execution_id
        last_execution_id = execution_id
        if len(execution_id_sample) < 20:
            execution_id_sample.append(execution_id)
        if was_created:
            created += 1
            by_task[proposal.task_key] += 1
        else:
            existing += 1
    return {
        "selected": len(selected),
        "created": created,
        "existing": existing,
        "by_task": dict(sorted(by_task.items())),
        "first_execution_id": first_execution_id,
        "last_execution_id": last_execution_id,
        "execution_id_sample": execution_id_sample,
    }
