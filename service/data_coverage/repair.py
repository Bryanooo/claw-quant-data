"""V2-only repair planning for confirmed coverage gaps."""

from __future__ import annotations

from datetime import date

from service.config import COVERAGE_AUTO_REPAIR_ENABLED, COVERAGE_AUTO_REPAIR_LIMIT
from service.data_coverage.models import CoverageAuditResult
from service.orchestration_v2.catalog import acquisition_task_blueprints
from service.orchestration_v2.contracts import TaskDefinitionDocument
from service.orchestration_v2.gap_repair import create_repair_executions
from service.orchestration_v2.repair_planning import plan_period_repairs
from service.orchestration_v2.repository import OrchestrationV2Repository


def _dataset_tasks() -> dict[str, str]:
    mapping = {
        dataset: task.task_key
        for task in acquisition_task_blueprints()
        for dataset in task.output_datasets
    }
    mapping["stock_daily_basic"] = "daily_basic"
    return mapping


def is_safe_repair_dataset(dataset_name: str) -> bool:
    """A repair is safe only when an active V2 task owns the dataset."""
    return dataset_name in _dataset_tasks()


class CoverageRepairPlanner:
    def __init__(self, repository: OrchestrationV2Repository | None = None):
        self._repository = repository or OrchestrationV2Repository()

    def submit(self, result: CoverageAuditResult, *, as_of: date | None = None) -> dict:
        del as_of
        if not COVERAGE_AUTO_REPAIR_ENABLED or result.status == "unverified":
            return {"eligible": 0, "created": 0, "execution_ids": []}
        dates = [
            item.partition_date
            for item in result.partitions
            if item.status in {"missing", "partial"}
        ]
        return self.submit_dates_bulk(
            result.dataset_name,
            dates,
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
        del as_of
        return self.submit_dates_bulk(dataset_name, partition_dates, limit=limit)

    def submit_dates_bulk(
        self,
        dataset_name: str,
        partition_dates: list[date],
        *,
        as_of: date | None = None,
        limit: int,
    ) -> dict:
        del as_of
        task_key = _dataset_tasks().get(dataset_name)
        if not task_key:
            return {"eligible": 0, "created": 0, "execution_ids": []}
        definition = self._repository.get_active_definition(task_key)
        if not definition:
            return {"eligible": 0, "created": 0, "execution_ids": []}
        document = TaskDefinitionDocument.model_validate(definition["definition"])
        problems = {
            dataset_name: {
                item: "confirmed_coverage_gap"
                for item in sorted(set(partition_dates), reverse=True)[:limit]
            }
        }
        proposals = plan_period_repairs(
            task_key=task_key,
            contracts=document.validation_contract.dataset_audits,
            problem_partitions=problems,
        )
        result = create_repair_executions(
            self._repository,
            proposals=proposals,
            limit=limit,
        )
        result["eligible"] = len(proposals)
        result["execution_ids"] = result.pop("execution_id_sample", [])
        return result
