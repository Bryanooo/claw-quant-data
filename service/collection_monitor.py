"""Unified interface-level collection status for API and dashboard."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from service.db import query
from service.fanout_scheduling import SCHEDULED_FANOUT_RECIPES
from service.tushare_catalog import TushareInterfaceCatalog
from service.tushare_policy import TusharePolicyRegistry
from service.tushare_scheduling import (
    DEDICATED_API_BY_RUN_ID,
    DEDICATED_RUN_IDS,
    DEDICATED_SCHEDULED_APIS,
)
from service.clock import business_now


class CollectionMonitorRepository:
    def service_health(self) -> list[dict]:
        return query(
            """
            SELECT DISTINCT ON (component)
                   component, instance_id, details, last_seen_at,
                   EXTRACT(EPOCH FROM (NOW() - last_seen_at)) AS age_seconds
            FROM sys_service_heartbeat
            ORDER BY component, last_seen_at DESC
            """
        )

    def queue_by_resource(self) -> list[dict]:
        return query(
            """
            SELECT resource_class,
                   COUNT(*) FILTER (WHERE job.status='queued')::INTEGER AS queued,
                   COUNT(*) FILTER (WHERE job.status='running' AND job.job_kind='leaf')::INTEGER AS running,
                   COUNT(*) FILTER (
                       WHERE job.status='failed'
                         AND job.finished_at >= NOW() - INTERVAL '24 hours'
                         AND NOT EXISTS (
                             SELECT 1 FROM sys_collection_job AS recovered
                             WHERE recovered.job_id > job.job_id
                               AND recovered.status='success'
                              AND COALESCE(
                                     recovered.api_name,
                                     recovered.parameters->>'api_name',
                                     recovered.task_name
                                   )=COALESCE(
                                     job.api_name,
                                     job.parameters->>'api_name',
                                     job.task_name
                                   )
                               AND (
                                     (job.expected_for IS NOT NULL
                                      AND recovered.expected_for=job.expected_for)
                                  OR (job.period_key IS NOT NULL
                                      AND recovered.period_key=job.period_key)
                                  OR (job.expected_for IS NULL
                                      AND job.period_key IS NULL)
                               )
                         )
                   )::INTEGER AS failed_24h
            FROM sys_collection_job AS job
            WHERE job.job_kind='leaf'
              AND (job.status IN ('queued','running') OR job.finished_at >= NOW() - INTERVAL '24 hours')
            GROUP BY resource_class
            ORDER BY resource_class
            """
        )

    def fanout_workloads(self) -> list[dict]:
        return query(
            """
            WITH campaign_work AS (
                SELECT campaign.campaign_id,
                       CASE
                           WHEN campaign.cadence IN ('backfill','initialization')
                           THEN 'historical'
                           ELSE 'routine'
                       END AS workload,
                       campaign.status,
                       COUNT(child.job_id) FILTER (
                           WHERE child.status='queued'
                       )::INTEGER AS queued,
                       COUNT(child.job_id) FILTER (
                           WHERE child.status='running'
                       )::INTEGER AS running
                FROM sys_collection_fanout_campaign AS campaign
                LEFT JOIN sys_collection_fanout_campaign_batch AS page
                  ON page.campaign_id=campaign.campaign_id
                LEFT JOIN sys_collection_job AS child
                  ON child.parent_job_id=page.batch_job_id
                WHERE campaign.status IN ('running','paused','attention')
                GROUP BY campaign.campaign_id, workload, campaign.status
            )
            SELECT workload,
                   COUNT(*) FILTER (WHERE status='running')::INTEGER AS active_campaigns,
                   COUNT(*) FILTER (
                       WHERE status IN ('paused','attention')
                   )::INTEGER AS attention_campaigns,
                   COALESCE(SUM(queued), 0)::INTEGER AS queued,
                   COALESCE(SUM(running), 0)::INTEGER AS running
            FROM campaign_work
            GROUP BY workload
            ORDER BY workload
            """
        )

    def latest_interface_jobs(self) -> dict[str, dict]:
        rows = query(
            """
            SELECT DISTINCT ON (COALESCE(api_name, parameters->>'api_name'))
                   job_id, task_name, parameters, status, attempt, max_attempts,
                   rows_inserted, rows_fetched, api_name, cadence, period_key,
                   expected_for, completion_status, completion_evidence,
                   error_message, created_at, started_at, finished_at,
                   recheck_of_job_id, recheck_root_job_id, recheck_generation,
                   job_kind, child_total, child_queued, child_running,
                   child_succeeded, child_failed
            FROM sys_collection_job AS job
            WHERE COALESCE(api_name, parameters->>'api_name') IS NOT NULL
              AND (
                parent_job_id IS NULL OR NOT EXISTS (
                    SELECT 1 FROM sys_collection_job AS parent
                    WHERE parent.job_id = job.parent_job_id
                      AND parent.job_kind = 'batch'
                )
              )
            ORDER BY COALESCE(api_name, parameters->>'api_name'),
                     created_at DESC, job_id DESC
            """
        )
        return {
            (row["api_name"] or row["parameters"].get("api_name")): row
            for row in rows
        }

    def latest_dedicated_runs(self) -> dict[str, dict]:
        rows = query(
            """
            SELECT DISTINCT ON (task_id)
                   run_id, task_id, trade_date, status, rows_inserted,
                   retry_count, error_message, started_at, finished_at
            FROM sys_collector_run
            ORDER BY task_id, started_at DESC, run_id DESC
            """
        )
        return {row["task_id"]: row for row in rows}

    def latest_scheduled_jobs(self) -> dict[str, dict]:
        """Return the durable queue record for each dedicated schedule.

        Early scheduled jobs predate the canonical ``api_name`` column
        population.  Their schedule identity and strict completion evidence
        are still durable in ``parameters``.  Reading them by ``schedule_id``
        keeps the operator view truthful without rewriting historical rows.
        """
        rows = query(
            """
            SELECT DISTINCT ON (parameters->>'schedule_id')
                   job_id, task_name, parameters, status, attempt, max_attempts,
                   rows_inserted, rows_fetched, api_name, cadence, period_key,
                   expected_for, completion_status, completion_evidence,
                   error_message, created_at, started_at, finished_at,
                   recheck_of_job_id, recheck_root_job_id, recheck_generation,
                   job_kind, child_total, child_queued, child_running,
                   child_succeeded, child_failed
            FROM sys_collection_job
            WHERE task_name='scheduled_collector'
              AND parameters->>'schedule_id' IS NOT NULL
            ORDER BY parameters->>'schedule_id', created_at DESC, job_id DESC
            """
        )
        return {row["parameters"]["schedule_id"]: row for row in rows}

    def latest_fanout_campaigns(self) -> dict[str, dict]:
        rows = query(
            """
            SELECT DISTINCT ON (api_name) *
            FROM sys_collection_fanout_campaign
            ORDER BY api_name, created_at DESC, campaign_id DESC
            """
        )
        return {row["api_name"]: row for row in rows}

    def unresolved_partition_failures(self) -> dict[str, dict]:
        """Return failures that have no later success for the same scope.

        A newer success for the interface must not hide a failed older day.
        Period-less exploratory jobs are excluded because they do not identify
        a recoverable data partition.
        """
        rows = query(
            """
            WITH failed AS (
                SELECT job_id,
                       COALESCE(api_name, parameters->>'api_name') AS api_name,
                       CASE COALESCE(api_name, parameters->>'api_name')
                           WHEN 'trade_cal' THEN 'trade_calendar'
                           WHEN 'daily' THEN 'stock_daily'
                           WHEN 'daily_basic' THEN 'stock_daily_basic'
                           WHEN 'bak_basic' THEN 'stock_daily_basic'
                           WHEN 'stk_limit' THEN 'stock_limit'
                           WHEN 'suspend_d' THEN 'stock_suspend'
                           WHEN 'fina_indicator' THEN 'financial_indicator'
                           WHEN 'fina_indicator_vip' THEN 'financial_indicator'
                           WHEN 'fx_daily' THEN 'forex_daily'
                           WHEN 'ths_daily' THEN 'industry_daily'
                           WHEN 'balancesheet_vip' THEN 'balancesheet'
                           WHEN 'cashflow_vip' THEN 'cashflow'
                           WHEN 'income_vip' THEN 'income'
                           WHEN 'express_vip' THEN 'express'
                           WHEN 'fina_mainbz_vip' THEN 'fina_mainbz'
                           WHEN 'forecast_vip' THEN 'forecast'
                           ELSE COALESCE(api_name, parameters->>'api_name')
                       END AS dataset_name,
                       task_name, parameters, period_key, expected_for, parent_job_id,
                       status, completion_status, completion_evidence,
                       error_message, finished_at
                FROM sys_collection_job
                WHERE (status='failed' OR completion_status='incomplete')
                  AND job_kind='leaf'
                  AND COALESCE(api_name, parameters->>'api_name') IS NOT NULL
                  AND (period_key IS NOT NULL OR expected_for IS NOT NULL)
            ), unresolved AS (
                SELECT failed.*
                FROM failed
                WHERE NOT (
                    failed.status='success'
                    AND failed.completion_status='incomplete'
                    AND failed.expected_for IS NOT NULL
                    AND EXISTS (
                        SELECT 1
                        FROM sys_collection_delivery_plan AS delivery
                        WHERE delivery.api_name=failed.api_name
                          AND delivery.expected_for=failed.expected_for
                          AND NOW() <= delivery.due_at
                    )
                )
                  AND NOT EXISTS (
                    SELECT 1
                    FROM sys_collection_job AS recovered
                    WHERE recovered.status='success'
                      AND recovered.job_kind='leaf'
                      AND recovered.job_id > failed.job_id
                      AND COALESCE(
                            recovered.api_name,
                            recovered.parameters->>'api_name'
                          ) = failed.api_name
                      AND (
                            (failed.expected_for IS NOT NULL
                             AND recovered.expected_for=failed.expected_for)
                         OR (failed.period_key IS NOT NULL
                             AND recovered.period_key=failed.period_key)
                      )
                      AND (
                            failed.status='failed'
                         OR recovered.completion_status='complete'
                      )
                )
                  AND NOT EXISTS (
                    SELECT 1
                    FROM sys_collection_fanout_campaign AS recovered_campaign
                    WHERE failed.parent_job_id IS NULL
                      AND recovered_campaign.api_name=failed.api_name
                      AND recovered_campaign.status='success'
                      AND recovered_campaign.completion_status='complete'
                      AND (
                            failed.expected_for IS NULL
                         OR recovered_campaign.expected_for >= failed.expected_for
                      )
                      AND recovered_campaign.request @>
                          jsonb_build_object('api_name', failed.api_name)
                      AND (
                            COALESCE(failed.parameters->'parameters', '{}'::jsonb)
                                = '{}'::jsonb
                         OR recovered_campaign.request @>
                            COALESCE(
                                failed.parameters->'parameters', '{}'::jsonb
                            )
                      )
                  )
                  AND NOT EXISTS (
                    SELECT 1
                    FROM sys_data_coverage_audit AS recovered_audit
                    WHERE failed.expected_for IS NOT NULL
                      AND recovered_audit.dataset_name=failed.dataset_name
                      AND recovered_audit.status='complete'
                      AND failed.expected_for BETWEEN
                          recovered_audit.start_date AND recovered_audit.end_date
                      AND recovered_audit.finished_at > failed.finished_at
                  )
            )
            SELECT DISTINCT ON (api_name)
                   api_name, job_id, period_key, expected_for,
                   status, completion_status, completion_evidence,
                   error_message, finished_at
            FROM unresolved
            ORDER BY api_name, finished_at DESC NULLS LAST, job_id DESC
            """
        )
        return {row["api_name"]: row for row in rows}


def _json_time(value: Any) -> Any:
    return value.isoformat() if isinstance(value, (date, datetime)) else value


def _coverage_failure_reason(evidence: dict[str, Any]) -> str:
    verification = evidence.get("verification") or {}
    missing = int(verification.get("missing_partitions") or 0)
    partial = int(verification.get("partial_partitions") or 0)
    return (
        f"覆盖审计未通过：{missing} 个日期分区缺失，"
        f"{partial} 个日期分区截面不完整"
    )


def _dedicated_completion(run: dict | None) -> tuple[str, str]:
    if not run:
        return "pending", "尚无运行记录"
    if run["status"] == "success":
        if (run.get("rows_inserted") or 0) > 0:
            return "unverified", "专项采集成功写入，但尚未提供分页/分区完整性证据"
        return (
            "unverified",
            "专项任务执行成功但返回 0；可能是真空结果或非交易日跳过，不能据此判空",
        )
    if run["status"] == "running":
        return "running", "专项采集任务正在运行"
    if run["status"] == "skipped":
        return "pending", "任务因非交易日或防重叠跳过"
    if run["status"] == "timeout":
        return "failed", "专项采集任务超时"
    return "failed", "专项采集任务失败"


def _queue_latest(job: dict) -> dict[str, Any]:
    completion = job.get("completion_status") or "unverified"
    evidence = job.get("completion_evidence") or {}
    verification = evidence.get("verification") or {}
    if (
        completion == "complete"
        and evidence.get("verified") is not True
        and verification.get("verified") is not True
    ):
        completion = "unverified"
    reasons = {
        "complete": "完整采集校验通过且返回了数据",
        "verifying": "采集已写入，正在执行日期与截面完整性审计",
        "empty": "完整性校验通过，上游在本周期返回空结果",
        "incomplete": "采集结果不完整，详见完整性证据",
        "unverified": "任务成功但未启用完整性校验",
        "running": "任务正在采集",
        "retrying": "临时失败，等待自动重试",
        "failed": "采集失败",
        "pending": "任务等待执行",
    }
    if completion == "incomplete" and verification:
        reasons["incomplete"] = _coverage_failure_reason(evidence)
    return {
        "source": "queue",
        "id": job["job_id"],
        "task_id": job["task_name"],
        "period_key": job.get("period_key") or "",
        "expected_for": (
            job["expected_for"].isoformat()
            if hasattr(job.get("expected_for"), "isoformat")
            else job.get("expected_for")
        ),
        "status": job["status"],
        "completion_status": completion,
        "completion_reason": reasons.get(completion, completion),
        "rows_fetched": job.get("rows_fetched"),
        "rows_inserted": job["rows_inserted"],
        "attempt": job["attempt"],
        "error_message": job["error_message"],
        "started_at": _json_time(job["started_at"]),
        "finished_at": _json_time(job["finished_at"]),
        "evidence": evidence,
        "failure": evidence.get("failure"),
        "parameters": job["parameters"],
        "recheck": (
            {
                "previous_job_id": job.get("recheck_of_job_id"),
                "root_job_id": job.get("recheck_root_job_id"),
                "generation": job.get("recheck_generation", 0),
            }
            if job.get("recheck_generation", 0)
            else None
        ),
        "job_kind": job.get("job_kind", "leaf"),
        "batch": (
            {
                "total": job.get("child_total", 0),
                "queued": job.get("child_queued", 0),
                "running": job.get("child_running", 0),
                "succeeded": job.get("child_succeeded", 0),
                "failed": job.get("child_failed", 0),
            }
            if job.get("job_kind") == "batch"
            else None
        ),
    }


def _fanout_latest(campaign: dict) -> dict[str, Any]:
    total = int(campaign.get("universe_total") or 0)
    completed = int(campaign.get("completed_offset") or 0)
    pages_created = int(campaign.get("pages_created") or 0)
    pages_completed = int(campaign.get("pages_completed") or 0)
    completion = campaign.get("completion_status") or "pending"
    reasons = {
        "complete": "全量依赖宇宙的所有分页均已通过完整性校验",
        "empty": "全量依赖宇宙已验证完成，但上游没有返回数据",
        "incomplete": "全量采集已暂停，或有分页尚未通过完整性校验",
        "running": "按固定依赖宇宙逐页采集，上一页验证后才会生成下一页",
        "pending": "等待生成首个受控分页",
    }
    request = campaign.get("request") or {}
    period_key = campaign.get("period_key") or next(
        (
            str(request[key])
            for key in ("trade_date", "ann_date", "period", "end_date")
            if request.get(key)
        ),
        "",
    )
    return {
        "source": "fanout_campaign",
        "id": campaign["campaign_id"],
        "task_id": "fanout_campaign",
        "period_key": period_key,
        "cadence": campaign.get("cadence") or "backfill",
        "status": campaign["status"],
        "completion_status": completion,
        "completion_reason": reasons.get(completion, completion),
        "rows_fetched": campaign.get("rows_fetched"),
        "rows_inserted": campaign.get("rows_inserted"),
        "attempt": None,
        "error_message": campaign.get("error_message"),
        "started_at": _json_time(campaign.get("created_at")),
        "finished_at": _json_time(
            campaign.get("finished_at") or campaign.get("updated_at")
        ),
        "evidence": {
            "universe_source": campaign.get("universe_source"),
            "universe_total": total,
            "universe_digest": campaign.get("universe_digest"),
            "completed_offset": completed,
            "progress_ratio": min(completed / total, 1.0) if total else 0.0,
        },
        "parameters": request,
        "recheck": None,
        "job_kind": "campaign",
        "batch": None,
        "campaign": {
            "pages_created": pages_created,
            "pages_completed": pages_completed,
            "universe_total": total,
            "completed_offset": completed,
        },
    }
class CollectionMonitorService:
    def __init__(self, repository: CollectionMonitorRepository | None = None):
        self._repository = repository or CollectionMonitorRepository()

    def overview(self) -> dict[str, Any]:
        jobs = self._repository.latest_interface_jobs()
        runs = self._repository.latest_dedicated_runs()
        scheduled_jobs = self._repository.latest_scheduled_jobs()
        campaigns = self._repository.latest_fanout_campaigns()
        unresolved_failures = self._repository.unresolved_partition_failures()
        service_rows = self._repository.service_health()
        queue_resources = {
            item["resource_class"]: item
            for item in self._repository.queue_by_resource()
        }
        fanout_workloads = self._repository.fanout_workloads()
        policies = TusharePolicyRegistry()
        fanout_recipes = {
            recipe.api_name: recipe for recipe in SCHEDULED_FANOUT_RECIPES
        }
        interfaces = []

        for contract in TushareInterfaceCatalog().list():
            policy = policies.get(contract.api_name)
            fanout_recipe = fanout_recipes.get(contract.api_name)
            automation_mode = "manual"
            effective_cadence = (
                fanout_recipe.cadence if fanout_recipe else policy.cadence
            )
            latest: dict[str, Any] | None = None
            if fanout_recipe is not None:
                automation_mode = "fanout"
                if contract.api_name in campaigns:
                    latest = _fanout_latest(campaigns[contract.api_name])
            elif contract.api_name in DEDICATED_SCHEDULED_APIS:
                automation_mode = "dedicated"
                canonical_api_names = {
                    DEDICATED_API_BY_RUN_ID[task_id]
                    for task_id in DEDICATED_RUN_IDS.get(contract.api_name, ())
                    if task_id in DEDICATED_API_BY_RUN_ID
                }
                queue_candidates = [
                    jobs[api_name]
                    for api_name in {contract.api_name, *canonical_api_names}
                    if api_name in jobs
                ]
                queue_candidates.extend(
                    scheduled_jobs[task_id]
                    for task_id in DEDICATED_RUN_IDS.get(contract.api_name, ())
                    if task_id in scheduled_jobs
                )
                queue_job = (
                    max(
                        queue_candidates,
                        key=lambda item: item.get("created_at")
                        or item.get("started_at"),
                    )
                    if queue_candidates
                    else None
                )
                candidates = [
                    runs[task_id]
                    for task_id in DEDICATED_RUN_IDS.get(contract.api_name, ())
                    if task_id in runs
                ]
                run = max(candidates, key=lambda item: item["started_at"]) if candidates else None
                completion, reason = _dedicated_completion(run)
                # The queue record wraps the same tracked callable and carries
                # retry plus post-write coverage evidence.  Prefer it whenever
                # available; sys_collector_run remains the compatibility view
                # for pre-queue executions.
                if queue_job:
                    latest = _queue_latest(queue_job)
                elif run:
                    latest = {
                        "source": "scheduler",
                        "id": run["run_id"],
                        "task_id": run["task_id"],
                        "period_key": str(run["trade_date"] or ""),
                        "status": run["status"],
                        "completion_status": completion,
                        "completion_reason": reason,
                        "rows_fetched": None,
                        "rows_inserted": run["rows_inserted"] or 0,
                        "attempt": (run["retry_count"] or 0) + 1,
                        "error_message": run["error_message"],
                        "started_at": _json_time(run["started_at"]),
                        "finished_at": _json_time(run["finished_at"]),
                    }
            elif policy.automatic_safe:
                automation_mode = "policy"
                job = jobs.get(contract.api_name)
                if job:
                    latest = _queue_latest(job)
            elif contract.api_name in campaigns:
                # An ad-hoc campaign remains visible for manual interfaces,
                # but must not mask a newer safe periodic policy forever.
                effective_cadence = (
                    campaigns[contract.api_name].get("cadence")
                    or policy.cadence
                )
                latest = _fanout_latest(campaigns[contract.api_name])
            elif contract.api_name in jobs:
                latest = _queue_latest(jobs[contract.api_name])

            interfaces.append(
                {
                    "api_name": contract.api_name,
                    "title": contract.title,
                    "category": contract.category_path,
                    "collectable": contract.collectable,
                    "permission_status": contract.permission.get("status", "unknown"),
                    "implementation_mode": contract.implementation.get("mode", "unavailable"),
                    "automation_mode": automation_mode,
                    "cadence": effective_cadence,
                    "automatic_safe": policy.automatic_safe or fanout_recipe is not None,
                    "automatic_reason": (
                        fanout_recipe.reason
                        if fanout_recipe is not None
                        else policy.automatic_reason
                    ),
                    "latest": latest,
                    "unresolved_failure": (
                        {
                            "job_id": unresolved_failures[contract.api_name]["job_id"],
                            "period_key": unresolved_failures[contract.api_name].get("period_key"),
                            "expected_for": _json_time(
                                unresolved_failures[contract.api_name].get("expected_for")
                            ),
                            "failure_type": (
                                "coverage_incomplete"
                                if unresolved_failures[contract.api_name].get("status") == "success"
                                else (
                                    "collection_incomplete"
                                    if unresolved_failures[contract.api_name].get("completion_status") == "incomplete"
                                    else "execution_failure"
                                )
                            ),
                            "failure": (
                                unresolved_failures[contract.api_name].get(
                                    "completion_evidence"
                                ) or {}
                            ).get("failure"),
                            "error_message": (
                                unresolved_failures[contract.api_name].get("error_message")
                                or (
                                    _coverage_failure_reason(
                                        unresolved_failures[contract.api_name].get(
                                            "completion_evidence"
                                        ) or {}
                                    )
                                    if unresolved_failures[contract.api_name].get("status") == "success"
                                    else "采集任务未完成且尚无严格完整的恢复任务"
                                )
                            ),
                            "finished_at": _json_time(
                                unresolved_failures[contract.api_name].get("finished_at")
                            ),
                        }
                        if contract.api_name in unresolved_failures
                        else None
                    ),
                }
            )

        counts: dict[str, int] = {
            "interfaces": len(interfaces),
            "collectable": sum(item["collectable"] for item in interfaces),
            "automated": sum(item["automation_mode"] != "manual" for item in interfaces),
            "complete": 0,
            "attention": 0,
            "manual_attention": 0,
            "unverified": 0,
            "pending": 0,
            "running": 0,
            "empty": 0,
            "unresolved_failures": len(unresolved_failures),
        }
        for item in interfaces:
            state = (item["latest"] or {}).get("completion_status", "pending")
            if item["unresolved_failure"]:
                counts["attention"] += 1
            elif state == "complete":
                counts["complete"] += 1
            elif state in {"running", "retrying", "verifying"}:
                counts["running"] += 1
            elif state == "empty":
                counts["empty"] += 1
            elif state == "unverified":
                counts["unverified"] += 1
            elif state == "pending":
                counts["pending"] += 1
            elif item["automation_mode"] == "manual":
                counts["manual_attention"] += 1
            else:
                counts["attention"] += 1

        return {
            "generated_at": business_now().isoformat(),
            "summary": counts,
            "services": [
                {
                    "component": item["component"],
                    "status": "healthy" if float(item["age_seconds"]) <= 90 else "stale",
                    "age_seconds": float(item["age_seconds"]),
                    "last_seen_at": _json_time(item["last_seen_at"]),
                    "instance_id": item.get("instance_id"),
                    "details": item.get("details") or {},
                    "queue": {
                        key: sum(
                            int(queue_resources.get(resource, {}).get(key) or 0)
                            for resource in (item.get("details") or {}).get(
                                "resource_classes", ()
                            )
                            if resource != "*"
                        )
                        for key in ("queued", "running", "failed_24h")
                    },
                }
                for item in service_rows
            ],
            "queue_resources": list(queue_resources.values()),
            "fanout_workloads": fanout_workloads,
            "interfaces": interfaces,
        }
