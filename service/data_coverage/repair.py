"""Conservative, idempotent repair planning for verified coverage gaps."""

from __future__ import annotations

from datetime import date
from typing import Any

from service.collection_jobs.models import BatchChildSpec
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


def is_safe_repair_dataset(dataset_name: str) -> bool:
    """Return whether confirmed gaps can be repaired without guessing scope."""
    return (
        dataset_name in _SAFE_PARTITION_REPAIRS
        or dataset_name in _SAFE_INTERFACE_REPAIRS
    )


class CoverageRepairPlanner:
    def __init__(self, job_repository: JobRepository | None = None):
        self._jobs = job_repository or JobRepository()

    def submit(self, result: CoverageAuditResult, *, as_of: date | None = None) -> dict:
        """Submit a bounded set of repairs; never guess unsupported fan-outs."""
        if not COVERAGE_AUTO_REPAIR_ENABLED or result.status == "unverified":
            return {"eligible": 0, "created": 0, "job_ids": []}
        missing = [
            item.partition_date
            for item in result.partitions
            if item.status in {"missing", "partial"}
        ]
        return self.submit_dates(
            result.dataset_name,
            missing,
            as_of=as_of,
            limit=COVERAGE_AUTO_REPAIR_LIMIT,
        )

    def submit_dates(
        self,
        dataset_name: str,
        partition_dates: list[date],
        *,
        as_of: date | None = None,
        limit: int,
    ) -> dict:
        """Queue repairs for dates already proven missing or partial by an audit."""
        mapping = _SAFE_PARTITION_REPAIRS.get(dataset_name)
        interface_repair = dataset_name in _SAFE_INTERFACE_REPAIRS
        if not mapping and not interface_repair:
            return {"eligible": 0, "created": 0, "job_ids": []}

        missing = sorted(set(partition_dates))
        target_day = as_of or business_today()
        jobs: list[int] = []
        for partition_date in missing[:limit]:
            child = self._repair_spec(
                dataset_name,
                partition_date,
                target_day=target_day,
                mapping=mapping,
                interface_repair=interface_repair,
            )
            job, created = self._jobs.create(
                child.task_name,
                child.parameters,
                max_attempts=child.max_attempts,
                idempotency_key=child.idempotency_key,
                cadence=child.cadence,
                api_name=child.api_name,
                period_key=child.period_key,
                expected_for=child.expected_for,
                handler_type=child.handler.handler_type,
                handler_key=child.handler.handler_key,
                handler_version=child.handler.handler_version,
                code_revision=child.handler.code_revision,
                priority=child.priority,
                resource_class=child.resource_class,
            )
            if created:
                jobs.append(job["job_id"])
        return {
            "eligible": len(missing),
            "created": len(jobs),
            "job_ids": jobs,
        }

    def submit_dates_bulk(
        self,
        dataset_name: str,
        partition_dates: list[date],
        *,
        as_of: date | None = None,
        limit: int,
    ) -> dict:
        """Bulk-create manually confirmed repairs in one database transaction."""
        mapping = _SAFE_PARTITION_REPAIRS.get(dataset_name)
        interface_repair = dataset_name in _SAFE_INTERFACE_REPAIRS
        if not mapping and not interface_repair:
            return {"eligible": 0, "created": 0, "job_ids": []}
        missing = sorted(set(partition_dates))[:limit]
        target_day = as_of or business_today()
        children = [
            self._repair_spec(
                dataset_name,
                partition_date,
                target_day=target_day,
                mapping=mapping,
                interface_repair=interface_repair,
            )
            for partition_date in missing
        ]
        jobs = self._jobs.create_many(children)
        return {
            "eligible": len(missing),
            "created": len(jobs),
            "job_ids": [int(job["job_id"]) for job in jobs],
        }

    @staticmethod
    def _repair_spec(
        dataset_name: str,
        partition_date: date,
        *,
        target_day: date,
        mapping: tuple[str, str] | None,
        interface_repair: bool,
    ) -> BatchChildSpec:
        if mapping:
            task_name, parameter_name = mapping
        else:
            task_name, parameter_name = "tushare_interface", "trade_date"
        compact = partition_date.strftime("%Y%m%d")
        if interface_repair:
            page_size = TusharePolicyRegistry().get(dataset_name).page_size
            parameters: dict[str, Any] = {
                "api_name": dataset_name,
                "parameters": {parameter_name: compact},
                "complete": True,
                "page_size": page_size,
                "resume": True,
            }
        else:
            parameters = {parameter_name: compact}
        return BatchChildSpec(
            task_name=task_name,
            parameters=parameters,
            idempotency_key=(
                f"coverage-repair-{dataset_name}-{compact}-{target_day:%Y%m%d}"
            )[:128],
            api_name=dataset_name if interface_repair else None,
            cadence="repair",
            period_key=partition_date.isoformat(),
            expected_for=partition_date,
            handler=TASKS.handler_metadata(task_name, parameters),
            priority=25,
            resource_class="backfill",
        )
