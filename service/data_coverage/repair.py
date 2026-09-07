"""Conservative, idempotent repair planning for verified coverage gaps."""

from __future__ import annotations

from datetime import date
from typing import Any

from service.collection_jobs.repository import JobRepository
from service.collection_jobs.registry import TASKS
from service.config import COVERAGE_AUTO_REPAIR_ENABLED, COVERAGE_AUTO_REPAIR_LIMIT
from service.data_coverage.models import CoverageAuditResult
from service.clock import business_today
from service.tushare_policy import TusharePolicyRegistry


# Only mappings that write the audited normalized table and can be safely
# partitioned by one trading date belong here. Other datasets remain visible
# for operator review until a trustworthy parameterized collector exists.
_SAFE_PARTITION_REPAIRS: dict[str, tuple[str, str]] = {
    "stock_daily": ("stock_daily", "trade_date"),
    "stock_daily_basic": ("stock_daily_basic", "trade_date"),
    "moneyflow": ("moneyflow", "trade_date"),
    "stock_limit": ("stock_limit", "trade_date"),
    "income": ("income_period", "period"),
    "balancesheet": ("balancesheet_period", "period"),
    "cashflow": ("cashflow_period", "period"),
    "financial_indicator": ("financial_indicator_period", "period"),
}

# These normalized interfaces are safely repairable as one market-wide date
# partition. Offset-capable collectors exhaust every page; small summary
# endpoints use a bounded request. No high-cardinality symbol fan-out is needed.
_SAFE_INTERFACE_REPAIRS = {
    "index_daily",
    "index_weekly",
    "index_monthly",
    "kpl_concept_cons",
    "margin",
    "margin_detail",
}


class CoverageRepairPlanner:
    def __init__(self, job_repository: JobRepository | None = None):
        self._jobs = job_repository or JobRepository()

    def submit(self, result: CoverageAuditResult, *, as_of: date | None = None) -> dict:
        """Submit a bounded set of repairs; never guess unsupported fan-outs."""
        if not COVERAGE_AUTO_REPAIR_ENABLED or result.status == "unverified":
            return {"eligible": 0, "created": 0, "job_ids": []}
        mapping = _SAFE_PARTITION_REPAIRS.get(result.dataset_name)
        interface_repair = result.dataset_name in _SAFE_INTERFACE_REPAIRS
        if not mapping and not interface_repair:
            return {"eligible": 0, "created": 0, "job_ids": []}

        if mapping:
            task_name, parameter_name = mapping
        else:
            task_name, parameter_name = "tushare_interface", "trade_date"
        missing = [
            item for item in result.partitions if item.status in {"missing", "partial"}
        ]
        target_day = as_of or business_today()
        jobs: list[int] = []
        for partition in missing[:COVERAGE_AUTO_REPAIR_LIMIT]:
            compact = partition.partition_date.strftime("%Y%m%d")
            if interface_repair:
                page_size = TusharePolicyRegistry().get(
                    result.dataset_name
                ).page_size
                parameters: dict[str, Any] = {
                    "api_name": result.dataset_name,
                    "parameters": {parameter_name: compact},
                    "complete": True,
                    "page_size": page_size,
                    "resume": True,
                }
            else:
                parameters = {parameter_name: compact}
            handler = TASKS.handler_metadata(task_name, parameters)
            job, created = self._jobs.create(
                task_name,
                parameters,
                max_attempts=3,
                idempotency_key=(
                    f"coverage-repair-{result.dataset_name}-{compact}-{target_day:%Y%m%d}"
                )[:128],
                cadence="repair",
                api_name=(result.dataset_name if interface_repair else None),
                period_key=partition.partition_date.isoformat(),
                expected_for=partition.partition_date,
                handler_type=handler.handler_type,
                handler_key=handler.handler_key,
                handler_version=handler.handler_version,
                code_revision=handler.code_revision,
                priority=25,
                resource_class="backfill",
            )
            if created:
                jobs.append(job["job_id"])
        return {
            "eligible": len(missing),
            "created": len(jobs),
            "job_ids": jobs,
        }
