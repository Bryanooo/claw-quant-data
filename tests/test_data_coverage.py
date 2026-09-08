from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from service.data_coverage.calculator import CoverageCalculator, completed_quarters
from service.data_coverage.models import (
    ActualPartition,
    CoverageAuditResult,
    CoverageRule,
    CoverageStrategy,
)
from service.data_coverage.worker import CoverageWorker
from service.data_coverage.registry import COVERAGE_RULES
import service.data_coverage.service as coverage_service
from service.data_service.registry import DATASETS
from service.data_service.models import DateStorage


class FakeCoverageRepository:
    def __init__(self, actual=(), expected=(), calendar_bounds=None, expected_entities=None):
        self.actual = list(actual)
        self.expected = list(expected)
        self.bounds = calendar_bounds or (date(1990, 1, 1), date(2030, 12, 31))
        self.expected_entities = expected_entities

    def actual_partitions(self, rule, start_date, end_date):
        return self.actual
    def expected_market_partitions(self, rule, start_date, cutoff_date):
        return [item for item in self.expected if item <= cutoff_date]

    def calendar_coverage(self, exchange, start_date, end_date):
        requested_days = (end_date - start_date).days + 1
        covered_days = (
            requested_days
            if self.bounds[0] <= start_date and self.bounds[1] >= end_date
            else max(0, requested_days - 1)
        )
        return self.bounds[0], self.bounds[1], covered_days

    def expected_entity_count(self, rule, partition_date):
        return self.expected_entities


def test_index_daily_rule_requires_a_market_entity_baseline():
    rule = COVERAGE_RULES.get("index_daily")

    assert rule.strategy is CoverageStrategy.TRADING_DAILY
    assert rule.entity_reference == "index_basic"
    assert rule.min_entity_ratio == 0.85
    assert rule.revision == 4
    assert rule.entity_reference_max_age_days == 120


def test_financial_rules_only_compare_recent_point_in_time_universe():
    for dataset_name in (
        "income", "balancesheet", "cashflow", "financial_indicator"
    ):
        rule = COVERAGE_RULES.get(dataset_name)
        assert rule.strategy is CoverageStrategy.REPORT_QUARTERLY
        assert rule.revision == 2
        assert rule.entity_reference_max_age_days == 1825


def test_old_financial_history_uses_exhausted_partition_not_current_universe():
    checked_rule = COVERAGE_RULES.get("income")
    result = CoverageCalculator(FakeCoverageRepository(
        actual=[ActualPartition(date(1990, 12, 31), 2, 2)],
        expected_entities=9,
    )).audit(
        checked_rule,
        date(1990, 12, 31),
        date(1990, 12, 31),
        as_of=date(2026, 9, 8),
        entity_reference_as_of=date(2026, 9, 8),
    )

    assert result.status == "complete"
    assert result.partitions[0].expected_entity_count is None


def test_margin_rules_detect_staggered_exchange_publication():
    summary = COVERAGE_RULES.get("margin")
    detail = COVERAGE_RULES.get("margin_detail")

    assert summary.entity_column == "exchange_id"
    assert summary.entity_reference == "margin_exchanges"
    assert summary.min_entity_ratio == 1.0
    assert detail.entity_column == "ts_code"
    assert detail.entity_reference == "margin_secs"
    assert detail.min_entity_ratio == 0.98


def test_kpl_concept_cons_missing_trade_dates_are_audited():
    rule = COVERAGE_RULES.get("kpl_concept_cons")

    assert rule.strategy is CoverageStrategy.TRADING_DAILY
    assert rule.entity_column is None
    assert rule.scheduled is True
    assert rule.accept_verified_empty is True


def test_verified_empty_partition_satisfies_event_like_daily_expectation():
    checked_rule = CoverageRule(
        dataset_name="kpl_concept_cons",
        table="kpl_concept_cons",
        date_column="trade_date",
        date_storage=DateStorage.COMPACT,
        strategy=CoverageStrategy.TRADING_DAILY,
        entity_column=None,
        grace_days=1,
        accept_verified_empty=True,
    )
    repository = FakeCoverageRepository(
        actual=[
            ActualPartition(
                date(2025, 10, 28), 0, None, verified_empty=True
            )
        ],
        expected=[date(2025, 10, 28)],
    )

    result = CoverageCalculator(repository).audit(
        checked_rule,
        date(2025, 10, 28),
        date(2025, 10, 28),
        as_of=date(2025, 10, 30),
    )

    assert result.status == "complete"
    assert result.present_partitions == 1
    assert result.missing_partitions == 0
    assert result.partitions[0].row_count == 0
    assert result.evidence["verified_empty_partitions"] == 1


def rule(strategy=CoverageStrategy.TRADING_DAILY):
    return CoverageRule(
        dataset_name="stock_daily",
        table="daily",
        date_column="trade_date",
        date_storage=DateStorage.DATE,
        strategy=strategy,
        entity_column="ts_code",
        grace_days=1,
    )


def test_market_audit_distinguishes_present_missing_and_non_expected_dates():
    repository = FakeCoverageRepository(
        actual=[
            ActualPartition(date(2026, 8, 25), 5000, 5000),
            ActualPartition(date(2026, 8, 27), 12, 12),
        ],
        expected=[date(2026, 8, 25), date(2026, 8, 26)],
    )

    result = CoverageCalculator(repository).audit(
        rule(),
        date(2026, 8, 25),
        date(2026, 8, 27),
        as_of=date(2026, 8, 29),
    )

    assert result.status == "gaps"
    assert result.expected_partitions == 2
    assert result.present_partitions == 1
    assert result.missing_partitions == 1
    assert [item.status for item in result.partitions] == [
        "present",
        "missing",
        "observed_only",
    ]
    assert result.evidence["semantics"] == "partition_and_entity_completeness"


def test_next_morning_partition_is_not_a_gap_before_documented_release():
    repository = FakeCoverageRepository(expected=[date(2026, 8, 31)])
    checked_rule = CoverageRule(
        dataset_name="margin",
        table="tushare_norm_margin",
        date_column="trade_date",
        date_storage=DateStorage.DATE,
        strategy=CoverageStrategy.TRADING_DAILY,
        entity_column=None,
        grace_days=1,
        release_after=time(9, 15),
    )
    calculator = CoverageCalculator(repository)
    timezone = ZoneInfo("Asia/Shanghai")

    before = calculator.audit(
        checked_rule,
        date(2026, 8, 31),
        date(2026, 8, 31),
        as_of=datetime(2026, 9, 1, 9, 14, tzinfo=timezone),
    )
    after = calculator.audit(
        checked_rule,
        date(2026, 8, 31),
        date(2026, 8, 31),
        as_of=datetime(2026, 9, 1, 9, 15, tzinfo=timezone),
    )

    assert before.status == "empty"
    assert before.expected_partitions == 0
    assert before.evidence["before_release"] is True
    assert after.status == "gaps"
    assert after.missing_partitions == 1
    assert after.evidence["before_release"] is False


def test_market_audit_marks_thin_cross_section_as_partial():
    repository = FakeCoverageRepository(
        actual=[ActualPartition(date(2026, 8, 25), 50, 50)],
        expected=[date(2026, 8, 25)],
        expected_entities=100,
    )
    checked_rule = CoverageRule(
        dataset_name="stock_daily",
        table="daily",
        date_column="trade_date",
        date_storage=DateStorage.DATE,
        strategy=CoverageStrategy.TRADING_DAILY,
        entity_column="ts_code",
        grace_days=1,
        entity_reference="stock_basic",
        min_entity_ratio=0.9,
    )

    result = CoverageCalculator(repository).audit(
        checked_rule,
        date(2026, 8, 25),
        date(2026, 8, 25),
        as_of=date(2026, 8, 29),
    )

    assert result.status == "gaps"
    assert result.partial_partitions == 1
    assert result.partitions[0].status == "partial"
    assert result.partitions[0].entity_coverage_ratio == 0.5
    assert result.evidence["rule_revision"] == 1


def test_index_daily_allows_cross_market_holiday_but_rejects_page_loss():
    checked_rule = COVERAGE_RULES.get("index_daily")

    holiday = CoverageCalculator(FakeCoverageRepository(
        actual=[ActualPartition(date(2026, 7, 1), 9269, 9269)],
        expected=[date(2026, 7, 1)],
        expected_entities=10616,
    )).audit(
        checked_rule,
        date(2026, 7, 1),
        date(2026, 7, 1),
        as_of=date(2026, 7, 3),
        entity_reference_as_of=date(2026, 9, 8),
    )
    truncated = CoverageCalculator(FakeCoverageRepository(
        actual=[ActualPartition(date(2026, 7, 1), 8000, 8000)],
        expected=[date(2026, 7, 1)],
        expected_entities=10616,
    )).audit(
        checked_rule,
        date(2026, 7, 1),
        date(2026, 7, 1),
        as_of=date(2026, 7, 3),
        entity_reference_as_of=date(2026, 9, 8),
    )

    assert holiday.status == "complete"
    assert truncated.status == "gaps"


def test_index_daily_old_history_uses_transport_partition_not_current_universe():
    checked_rule = COVERAGE_RULES.get("index_daily")
    result = CoverageCalculator(FakeCoverageRepository(
        actual=[ActualPartition(date(1993, 1, 29), 3, 3)],
        expected=[date(1993, 1, 29)],
        expected_entities=6,
    )).audit(
        checked_rule,
        date(1993, 1, 29),
        date(1993, 1, 29),
        as_of=date(1993, 1, 31),
        entity_reference_as_of=date(2026, 9, 8),
    )

    assert result.status == "complete"
    assert result.partitions[0].expected_entity_count is None


def test_tiny_early_stock_market_allows_one_legitimate_non_trading_symbol():
    repository = FakeCoverageRepository(
        actual=[ActualPartition(date(1991, 1, 31), 7, 7)],
        expected=[date(1991, 1, 31)],
        expected_entities=8,
    )
    rule = CoverageRule(
        dataset_name="stock_daily",
        table="daily",
        date_column="trade_date",
        date_storage=DateStorage.DATE,
        strategy=CoverageStrategy.TRADING_DAILY,
        entity_column="ts_code",
        entity_reference="stock_basic",
        min_entity_ratio=0.9,
    )

    result = CoverageCalculator(repository).audit(
        rule,
        date(1991, 1, 31),
        date(1991, 1, 31),
        as_of=date(1991, 2, 2),
    )

    assert result.status == "complete"
    assert result.partitions[0].entity_coverage_ratio == 0.875


def test_explicit_incomplete_job_evidence_overrides_physical_rows():
    repository = FakeCoverageRepository(
        actual=[
            ActualPartition(
                date(2026, 9, 4),
                2000,
                2000,
                known_incomplete=True,
            )
        ],
        expected=[date(2026, 9, 4)],
        expected_entities=2000,
    )
    checked_rule = CoverageRule(
        dataset_name="margin_detail",
        table="margin_detail",
        date_column="trade_date",
        date_storage=DateStorage.COMPACT,
        strategy=CoverageStrategy.TRADING_DAILY,
        entity_column="ts_code",
        entity_reference="stock_basic",
        min_entity_ratio=0.70,
    )

    result = CoverageCalculator(repository).audit(
        checked_rule,
        date(2026, 9, 4),
        date(2026, 9, 4),
        as_of=date(2026, 9, 6),
    )

    assert result.status == "gaps"
    assert result.partial_partitions == 1
    assert result.evidence["known_incomplete_partitions"] == 1


def test_observed_only_rule_never_invents_missing_dates():
    repository = FakeCoverageRepository(
        actual=[ActualPartition(date(2026, 8, 25), 20, 4)],
        expected=[date(2026, 8, 25), date(2026, 8, 26)],
    )

    result = CoverageCalculator(repository).audit(
        rule(CoverageStrategy.OBSERVED_ONLY),
        date(2026, 8, 25),
        date(2026, 8, 27),
        as_of=date(2026, 8, 29),
    )

    assert result.status == "observed_only"
    assert result.expected_partitions == 0
    assert result.missing_partitions == 0
    assert result.partitions[0].status == "observed_only"


def test_every_public_dataset_has_an_explicit_coverage_classification():
    rules = COVERAGE_RULES.list()

    assert len(rules) == len(DATASETS.list()) == 193
    assert {item.dataset_name for item in rules} == {
        item.name for item in DATASETS.list()
    }
    assert all(item.coverage_level for item in rules)
    assert all(item.date_column for item in rules if item.auditable)
    assert all(not item.auditable for item in rules if item.coverage_level == "not_applicable")


def test_only_proven_rules_are_automatically_scheduled():
    scheduled = COVERAGE_RULES.scheduled()

    assert len(scheduled) == 49
    assert all(item.auditable for item in scheduled)
    assert COVERAGE_RULES.get("adj_factor").scheduled is True
    assert COVERAGE_RULES.get("adj_factor").coverage_level == "expected_partitions"
    assert COVERAGE_RULES.get("ccass_hold").coverage_level == "observed_partitions"
    assert COVERAGE_RULES.get("ccass_hold").entity_column == "ts_code"
    assert COVERAGE_RULES.get("ccass_hold_detail").scheduled is False
    assert COVERAGE_RULES.get("ccass_hold_detail").entity_column == "ts_code"
    assert COVERAGE_RULES.get("hk_daily").scheduled is True


def test_manual_repair_queues_only_confirmed_problem_partitions():
    class Repository:
        def list_partitions(self, dataset_name, **options):
            assert dataset_name == "stock_daily"
            assert options["status"] == "problem"
            return [
                {"partition_date": date(2026, 9, 1), "status": "missing"},
                {"partition_date": date(2026, 9, 2), "status": "partial"},
            ]

    class Planner:
        def submit_dates_bulk(self, dataset_name, dates, *, limit):
            assert dataset_name == "stock_daily"
            assert dates == [date(2026, 9, 1), date(2026, 9, 2)]
            assert limit == 4000
            return {"eligible": 2, "created": 2, "job_ids": [7, 8]}

    service = coverage_service.CoverageService(
        repository=Repository(), repair_planner=Planner()
    )

    result = service.submit_repairs(
        "stock_daily",
        start_date=date(2026, 9, 1),
        end_date=date(2026, 9, 2),
    )

    assert result["created"] == 2
    assert result["dataset"] == "stock_daily"


def test_scheduled_coverage_uses_distinct_pre_and_post_release_keys(monkeypatch):
    keys = []

    class FakeService:
        def submit_audits(self, **options):
            keys.append(options["idempotency_key"])
            return {"created": 0, "total": 0, "jobs": []}

    monkeypatch.setattr(coverage_service, "CoverageService", FakeService)
    timezone = ZoneInfo("Asia/Shanghai")
    target = date(2026, 9, 1)

    coverage_service.submit_scheduled_coverage_audits(
        target,
        now=datetime(2026, 9, 1, 0, 30, tzinfo=timezone),
    )
    coverage_service.submit_scheduled_coverage_audits(
        target,
        now=datetime(2026, 9, 1, 9, 30, tzinfo=timezone),
    )

    assert keys == [
        "scheduled-2026-09-01-pre-release",
        "scheduled-2026-09-01-post-release",
    ]


def test_non_temporal_rule_cannot_be_calculated():
    checked_rule = CoverageRule(
        dataset_name="stock_basic",
        table="stock_basic",
        date_column=None,
        date_storage=DateStorage.DATE,
        strategy=CoverageStrategy.NON_TEMPORAL,
    )

    try:
        CoverageCalculator(FakeCoverageRepository()).audit(
            checked_rule,
            date(2026, 8, 1),
            date(2026, 8, 2),
        )
    except ValueError as exc:
        assert "does not have auditable date partitions" in str(exc)
    else:
        raise AssertionError("non-temporal rule must not be audited")


def test_market_audit_is_unverified_when_calendar_does_not_cover_range():
    repository = FakeCoverageRepository(
        expected=[date(2026, 8, 25)],
        calendar_bounds=(date(2026, 8, 1), date(2027, 8, 1)),
    )

    result = CoverageCalculator(repository).audit(
        rule(),
        date(2026, 5, 1),
        date(2026, 8, 27),
        as_of=date(2026, 8, 29),
    )

    assert result.status == "unverified"
    assert result.evidence["calendar_complete_for_range"] is False


def test_quarter_periods_only_become_expected_after_disclosure_deadline():
    assert completed_quarters(
        date(2025, 12, 31),
        date(2026, 9, 30),
        date(2026, 8, 29),
    ) == [date(2025, 12, 31), date(2026, 3, 31)]

    assert completed_quarters(
        date(2025, 12, 31),
        date(2026, 9, 30),
        date(2026, 9, 1),
    ) == [date(2025, 12, 31), date(2026, 3, 31), date(2026, 6, 30)]


def test_linked_coverage_job_updates_original_collection_before_finish(monkeypatch):
    events = []

    class QueueRepository:
        job = {
            "job_id": 7,
            "dataset_name": "income",
            "start_date": date(2026, 9, 30),
            "end_date": date(2026, 9, 30),
            "collection_job_id": 19,
            "attempt": 1,
            "max_attempts": 2,
        }

        def claim_next(self, _worker_id):
            result, self.job = self.job, None
            return result

        def save_audit(self, job_id, _result):
            events.append(("save", job_id))
            return 31

        def finish_job(self, job_id):
            events.append(("finish", job_id))

        def fail_or_requeue(self, *_args):
            raise AssertionError("audit should not fail")

    class CollectionRepository:
        def apply_verification_result(self, collection_job_id, **options):
            events.append(("apply", collection_job_id, options["audit_status"]))

    result = CoverageAuditResult(
        dataset_name="income",
        strategy="report_quarterly",
        start_date=date(2026, 9, 30),
        end_date=date(2026, 9, 30),
        status="complete",
        expected_partitions=1,
        present_partitions=1,
        missing_partitions=0,
        observed_partitions=1,
        coverage_ratio=1.0,
        partitions=(),
        evidence={},
    )
    repository = QueueRepository()
    worker = CoverageWorker(
        repository,
        worker_id="test-auditor",
        collection_job_repository=CollectionRepository(),
    )
    audit_calls = []
    monkeypatch.setattr(
        worker._calculator,
        "audit",
        lambda rule, start, end, **options: (
            audit_calls.append((rule.dataset_name, start, end, options["as_of"])) or result
        ),
    )
    monkeypatch.setattr(
        worker._repair_planner,
        "submit",
        lambda _result: {"created": 0, "eligible": 0, "job_ids": []},
    )

    assert worker.run_once() is True
    assert audit_calls[0][3] == date(2027, 11, 4)
    assert events == [("save", 7), ("apply", 19, "complete"), ("finish", 7)]
