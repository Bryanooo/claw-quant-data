from datetime import date

from service.data_coverage.models import CoverageAuditResult, CoveragePartition
from service.data_coverage.repair import CoverageRepairPlanner, is_safe_repair_dataset


class FakeJobRepository:
    def __init__(self):
        self.created = []

    def create(self, task_name, parameters, **options):
        self.created.append((task_name, parameters, options))
        return {"job_id": len(self.created)}, True

    def create_many(self, children):
        jobs = []
        for child in children:
            self.created.append((child.task_name, child.parameters, child))
            jobs.append({"job_id": len(self.created)})
        return jobs


def audit(dataset="stock_daily", status="gaps"):
    partitions = (
        (date(2026, 3, 31), date(2026, 6, 30))
        if dataset in {"income", "balancesheet", "cashflow", "financial_indicator"}
        else (date(2026, 8, 25), date(2026, 8, 26))
    )
    return CoverageAuditResult(
        dataset_name=dataset,
        strategy="trading_daily",
        start_date=partitions[0],
        end_date=partitions[1],
        status=status,
        expected_partitions=2,
        present_partitions=0,
        missing_partitions=2,
        observed_partitions=0,
        coverage_ratio=0,
        partitions=(
            CoveragePartition(partitions[0], "missing", 0, 0, True),
            CoveragePartition(partitions[1], "missing", 0, 0, True),
        ),
        evidence={},
    )


def test_repair_planner_submits_bounded_idempotent_normalized_jobs(monkeypatch):
    monkeypatch.setattr("service.data_coverage.repair.COVERAGE_AUTO_REPAIR_LIMIT", 1)
    repository = FakeJobRepository()

    result = CoverageRepairPlanner(repository).submit(
        audit(), as_of=date(2026, 8, 29)
    )

    assert result == {"eligible": 2, "created": 1, "job_ids": [1]}
    task, parameters, options = repository.created[0]
    assert task == "stock_daily"
    assert parameters == {"trade_date": "20260825"}
    assert options["idempotency_key"] == "coverage-repair-stock_daily-20260825-20260829"
    assert options["resource_class"] == "backfill"
    assert options["priority"] == 25


def test_repair_planner_never_repairs_unverified_or_unsupported_datasets():
    repository = FakeJobRepository()
    planner = CoverageRepairPlanner(repository)

    assert planner.submit(audit(status="unverified"))["created"] == 0
    assert planner.submit(audit(dataset="forex_daily"))["created"] == 0
    assert repository.created == []


def test_safe_repair_capability_is_explicit_and_shared_with_dashboard():
    assert is_safe_repair_dataset("stock_daily") is True
    assert is_safe_repair_dataset("index_daily") is True
    assert is_safe_repair_dataset("forex_daily") is False


def test_manual_repair_accepts_confirmed_partition_dates_only():
    repository = FakeJobRepository()

    result = CoverageRepairPlanner(repository).submit_dates(
        "stock_daily",
        [date(2026, 8, 26), date(2026, 8, 25), date(2026, 8, 25)],
        as_of=date(2026, 9, 8),
        limit=10,
    )

    assert result["eligible"] == 2
    assert result["created"] == 2
    assert [parameters for _, parameters, _ in repository.created] == [
        {"trade_date": "20260825"},
        {"trade_date": "20260826"},
    ]


def test_manual_range_repair_bulk_inserts_independent_retryable_leaves():
    repository = FakeJobRepository()

    result = CoverageRepairPlanner(repository).submit_dates_bulk(
        "index_daily",
        [date(2026, 8, 25), date(2026, 8, 26)],
        as_of=date(2026, 9, 8),
        limit=4000,
    )

    assert result == {"eligible": 2, "created": 2, "job_ids": [1, 2]}
    first = repository.created[0][2]
    assert first.resource_class == "backfill"
    assert first.max_attempts == 3
    assert first.parameters["complete"] is True


def test_repair_planner_uses_report_period_task_for_financial_gaps():
    repository = FakeJobRepository()
    result = CoverageRepairPlanner(repository).submit(
        audit(dataset="income"), as_of=date(2026, 8, 29)
    )

    assert result["created"] == 2
    assert repository.created[0][0] == "income_period"
    assert repository.created[0][1] == {"period": "20260331"}


def test_repair_planner_uses_complete_offset_interface_for_index_periods():
    repository = FakeJobRepository()

    result = CoverageRepairPlanner(repository).submit(
        audit(dataset="index_monthly"), as_of=date(2026, 9, 3)
    )

    assert result["created"] == 2
    task, parameters, options = repository.created[0]
    assert task == "tushare_interface"
    assert parameters == {
        "api_name": "index_monthly",
        "parameters": {"trade_date": "20260825"},
        "complete": True,
        "page_size": 1000,
        "resume": True,
    }
    assert options["handler_type"] == "specialized"


def test_repair_planner_uses_complete_offset_interface_for_index_daily():
    repository = FakeJobRepository()

    result = CoverageRepairPlanner(repository).submit(
        audit(dataset="index_daily"), as_of=date(2026, 9, 3)
    )

    assert result["created"] == 2
    assert repository.created[0][0] == "tushare_interface"
    assert repository.created[0][1]["api_name"] == "index_daily"
    assert repository.created[0][1]["parameters"] == {"trade_date": "20260825"}


def test_kpl_concept_cons_gap_uses_complete_offset_repair():
    repository = FakeJobRepository()

    result = CoverageRepairPlanner(repository).submit(
        audit(dataset="kpl_concept_cons"), as_of=date(2026, 9, 3)
    )

    assert result["created"] == 2
    task, parameters, options = repository.created[0]
    assert task == "tushare_interface"
    assert parameters["api_name"] == "kpl_concept_cons"
    assert parameters["complete"] is True
    assert parameters["page_size"] == 3000
    assert options["resource_class"] == "backfill"


def test_margin_detail_gap_uses_bounded_offset_repair():
    repository = FakeJobRepository()

    result = CoverageRepairPlanner(repository).submit(
        audit(dataset="margin_detail"), as_of=date(2026, 9, 6)
    )

    assert result["created"] == 2
    task, parameters, options = repository.created[0]
    assert task == "tushare_interface"
    assert parameters["api_name"] == "margin_detail"
    assert parameters["page_size"] == 1000
    assert options["resource_class"] == "backfill"
    assert options["api_name"] == "margin_detail"


def test_persistent_margin_gap_is_retried_once_per_business_day():
    repository = FakeJobRepository()
    planner = CoverageRepairPlanner(repository)

    planner.submit(audit(dataset="margin_detail"), as_of=date(2026, 9, 6))
    planner.submit(audit(dataset="margin_detail"), as_of=date(2026, 9, 7))

    keys = [options["idempotency_key"] for _, _, options in repository.created]
    assert keys[0] == "coverage-repair-margin_detail-20260825-20260906"
    assert keys[2] == "coverage-repair-margin_detail-20260825-20260907"
