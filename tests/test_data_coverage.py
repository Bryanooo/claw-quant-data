from datetime import date, datetime, time
from zoneinfo import ZoneInfo

import pytest

from service.data_coverage.calculator import (
    CoverageCalculator,
    completed_months,
    completed_quarters,
)
from service.data_coverage.models import (
    ActualPartition,
    CoverageRule,
    CoverageStrategy,
)
from service.data_coverage.repair import is_safe_repair_dataset
from service.data_coverage.registry import COVERAGE_RULES
from service.data_coverage.repository import CoverageRepository
import service.data_coverage.service as coverage_service
from service.data_service.registry import DATASETS
from service.data_service.models import DateStorage


class AuditSubmissionRepository:
    def __init__(self):
        self.calls = []

    def create_job(self, dataset_name, start_date, end_date, *, idempotency_key):
        self.calls.append((dataset_name, start_date, end_date, idempotency_key))
        return {"job_id": len(self.calls)}, True


class FakeCoverageRepository:
    def __init__(self, actual=(), expected=(), calendar_bounds=None, expected_entities=None):
        self.actual = list(actual)
        self.expected = list(expected)
        self.bounds = calendar_bounds or (date(1990, 1, 1), date(2030, 12, 31))
        self.expected_entities = expected_entities
        self.last_cutoff = None

    def actual_partitions(
        self,
        rule,
        start_date,
        end_date,
        *,
        verified_transport_dates=None,
        verified_empty_transport_dates=None,
    ):
        return self.actual
    def expected_market_partitions(self, rule, start_date, cutoff_date):
        self.last_cutoff = cutoff_date
        return [
            item for item in self.expected
            if start_date <= item <= cutoff_date
        ]

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

    def snapshot_evidence(self, rule):
        return {
            "api_name": rule.collection_api_name or rule.dataset_name,
            "row_count": 3,
            "latest_success": {
                "job_id": 7,
                "completion_status": "complete",
            },
            "verified": True,
            "unresolved_failures": 0,
            "active_history_jobs": 0,
        }

    def collection_scope_evidence(self, rule):
        return {
            "api_name": rule.collection_api_name or rule.dataset_name,
            "declared_jobs": 1,
            "active_jobs": 0,
            "verified_terminal_jobs": 1,
            "unresolved_failures": 0,
        }


class CoverageOverviewRepository:
    def latest_audits(self):
        return {
            "stock_daily": {
                "status": "complete", "coverage_ratio": 1,
                "missing_partitions": 0, "partial_partitions": 0,
            },
            "fund_nav": {
                "status": "unverified", "coverage_ratio": 0,
                "missing_partitions": 0, "partial_partitions": 0,
            },
            "trade_calendar": {
                "status": "empty", "coverage_ratio": 1,
                "missing_partitions": 0, "partial_partitions": 0,
            },
            "index_daily": {
                "status": "gaps", "coverage_ratio": 0.5,
                "missing_partitions": 1, "partial_partitions": 1,
            },
        }

    def recent_missing_by_dataset(self, *, limit):
        return {}

    def queue_counts(self):
        return {"queued": 0, "running": 0}


def test_index_daily_rule_requires_a_market_entity_baseline():
    rule = COVERAGE_RULES.get("index_daily")

    assert rule.strategy is CoverageStrategy.TRADING_DAILY
    assert rule.entity_reference == "index_basic"
    assert rule.min_entity_ratio == 0.85
    assert rule.revision == 4
    assert rule.entity_reference_max_age_days == 120


def test_coverage_overview_never_hides_unverified_behind_zero_missing():
    result = coverage_service.CoverageService(
        repository=CoverageOverviewRepository()
    ).overview()

    assert result["summary"]["audited"] == 4
    assert result["summary"]["strictly_verified"] == 2
    assert result["summary"]["complete"] == 1
    assert result["summary"]["verified_empty"] == 1
    assert result["summary"]["unverified"] == 1
    assert result["summary"]["with_gaps"] == 1


def test_stock_daily_rules_limit_entity_ratio_to_reconstructable_history():
    for dataset_name in ("stock_daily", "stock_daily_basic"):
        rule = COVERAGE_RULES.get(dataset_name)
        assert rule.min_entity_ratio == 0.90
        assert rule.entity_reference_max_age_days == 1825
        assert rule.revision == 2


def test_next_morning_margin_rules_do_not_expect_same_day_data():
    for dataset_name in ("margin", "margin_detail", "etf_share_size"):
        rule = COVERAGE_RULES.get(dataset_name)
        assert rule.grace_days == 1
        assert rule.release_after == time(9, 15)
    assert COVERAGE_RULES.get("margin").revision == 2
    assert COVERAGE_RULES.get("margin_detail").revision == 2


def test_public_dataset_aliases_audit_their_actual_collection_api():
    assert COVERAGE_RULES.get("forex_daily").collection_api_name == "fx_daily"
    assert COVERAGE_RULES.get("stock_suspend").collection_api_name == "suspend_d"
    assert COVERAGE_RULES.get("trade_calendar").collection_api_name == "trade_cal"


def test_known_provider_history_boundaries_are_shared_with_coverage_rules():
    expected = {
        "bak_daily": date(2017, 6, 14),
        "cb_daily": date(1993, 2, 10),
        "ci_daily": date(2010, 1, 4),
        "etf_share_size": date(2009, 1, 5),
        "index_dailybasic": date(2004, 1, 2),
        "moneyflow_cnt_ths": date(2024, 9, 10),
        "moneyflow_ind_dc": date(2023, 9, 12),
        "moneyflow_ths": date(2024, 12, 19),
        "sw_daily": date(2000, 1, 4),
        "tdx_daily": date(2025, 3, 28),
        "tdx_index": date(2025, 3, 28),
        "ths_hot": date(2023, 8, 21),
    }
    for dataset_name, boundary in expected.items():
        rule = COVERAGE_RULES.get(dataset_name)
        assert rule.availability_start == boundary
        assert rule.revision >= 2

    shibor_lpr = COVERAGE_RULES.get("shibor_lpr")
    assert shibor_lpr.availability_start == date(2013, 10, 25)
    assert shibor_lpr.revision == 3


def test_authoritative_empty_exact_day_products_are_not_false_failures():
    for dataset_name in (
        "bak_daily",
        "cb_daily",
        "etf_share_size",
        "moneyflow_cnt_ths",
        "moneyflow_ind_dc",
        "moneyflow_ind_ths",
        "moneyflow_ths",
        "sz_daily_info",
        "ths_hot",
    ):
        assert COVERAGE_RULES.get(dataset_name).accept_verified_empty is True


def test_financial_rules_only_compare_recent_point_in_time_universe():
    for dataset_name in (
        "income", "balancesheet", "cashflow", "financial_indicator"
    ):
        rule = COVERAGE_RULES.get(dataset_name)
        assert rule.strategy is CoverageStrategy.REPORT_QUARTERLY
        assert rule.revision == 4
        assert rule.entity_reference_max_age_days == 1825
        assert rule.accept_verified_empty is True
        assert rule.verified_empty_min_age_days == 1825

    assert (
        COVERAGE_RULES.get("financial_indicator").collection_api_name
        == "fina_indicator"
    )


def test_public_dataset_aliases_map_to_collection_api_names():
    assert COVERAGE_RULES.get("stock_daily").collection_api_name == "daily"
    assert (
        COVERAGE_RULES.get("stock_daily_basic").collection_api_name
        == "daily_basic"
    )
    assert COVERAGE_RULES.get("stock_limit").collection_api_name == "stk_limit"


def test_research_market_series_have_exact_date_repair_paths():
    for dataset_name in (
        "adj_factor", "dc_daily", "etf_share_size", "fund_adj",
        "fund_daily", "sge_daily", "shibor", "shibor_lpr", "tdx_daily",
    ):
        assert is_safe_repair_dataset(dataset_name)


def test_monthly_date_series_normalizes_publication_day_to_month_end():
    expression = repr(CoverageRepository._date_expression(
        COVERAGE_RULES.get("shibor_lpr")
    ))

    assert "date_trunc('month'" in expression
    assert "1 month - 1 day" in expression


def test_quarterly_audit_allows_full_history_range():
    repository = AuditSubmissionRepository()
    service = coverage_service.CoverageService(repository=repository)

    result = service.submit_audits(
        ["income"],
        start_date=date(1990, 12, 31),
        end_date=date(2026, 6, 30),
        idempotency_key="full-finance-history",
    )

    assert result["created"] == 1
    assert repository.calls[0][:3] == (
        "income",
        date(1990, 12, 31),
        date(2026, 6, 30),
    )


def test_manual_all_dataset_audit_includes_unscheduled_rules():
    repository = AuditSubmissionRepository()
    service = coverage_service.CoverageService(repository=repository)

    result = service.submit_audits(
        start_date=date(2026, 9, 1),
        end_date=date(2026, 9, 2),
        idempotency_key="manual-all",
        include_unscheduled=True,
    )

    assert result["total"] == len(COVERAGE_RULES.list()) == 194
    assert {item[0] for item in repository.calls} == {
        rule.dataset_name for rule in COVERAGE_RULES.list()
    }


def test_completed_months_respects_release_cutoff():
    assert completed_months(
        date(2026, 1, 1),
        date(2026, 4, 30),
        date(2026, 3, 15),
    ) == [date(2026, 1, 31), date(2026, 2, 28)]


def test_audit_rejects_ranges_beyond_supported_market_history():
    service = coverage_service.CoverageService(
        repository=AuditSubmissionRepository()
    )

    with pytest.raises(
        coverage_service.InvalidCoverageRequestError,
        match="at most 20000 days",
    ):
        service.submit_audits(
            ["stock_daily"],
            start_date=date(1960, 1, 1),
            end_date=date(2026, 9, 5),
        )


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


def test_financial_verified_empty_is_only_accepted_for_old_history():
    checked_rule = COVERAGE_RULES.get("income")
    reference_as_of = date(2026, 9, 8)
    old = CoverageCalculator(FakeCoverageRepository(
        actual=[ActualPartition(
            date(1991, 3, 31), 0, None, verified_empty=True
        )],
    )).audit(
        checked_rule,
        date(1991, 3, 31),
        date(1991, 3, 31),
        as_of=reference_as_of,
        entity_reference_as_of=reference_as_of,
    )
    recent = CoverageCalculator(FakeCoverageRepository(
        actual=[ActualPartition(
            date(2025, 12, 31), 0, None, verified_empty=True
        )],
    )).audit(
        checked_rule,
        date(2025, 12, 31),
        date(2025, 12, 31),
        as_of=reference_as_of,
        entity_reference_as_of=reference_as_of,
    )

    assert old.status == "complete"
    assert old.partitions[0].status == "present"
    assert recent.status == "gaps"
    assert recent.partitions[0].status == "partial"


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


def test_aware_audit_time_uses_shanghai_business_date_inside_utc_container():
    repository = FakeCoverageRepository(expected=[date(2026, 9, 24)])
    checked_rule = CoverageRule(
        dataset_name="index_weekly",
        table="index_weekly",
        date_column="trade_date",
        date_storage=DateStorage.DATE,
        strategy=CoverageStrategy.TRADING_WEEKLY,
        entity_column=None,
        grace_days=2,
    )

    CoverageCalculator(repository).audit(
        checked_rule,
        date(2026, 9, 21),
        date(2026, 9, 27),
        as_of=datetime(
            2026, 9, 28, 16, 5, tzinfo=ZoneInfo("UTC")
        ),
    )

    assert repository.last_cutoff == date(2026, 9, 27)


def test_ths_hot_uses_same_day_final_publication_cutoff():
    checked_rule = COVERAGE_RULES.get("ths_hot")
    repository = FakeCoverageRepository(expected=[date(2026, 9, 14)])
    calculator = CoverageCalculator(repository)
    timezone = ZoneInfo("Asia/Shanghai")

    before = calculator.audit(
        checked_rule,
        date(2026, 9, 14),
        date(2026, 9, 14),
        as_of=datetime(2026, 9, 14, 23, 14, tzinfo=timezone),
    )
    after = calculator.audit(
        checked_rule,
        date(2026, 9, 14),
        date(2026, 9, 14),
        as_of=datetime(2026, 9, 14, 23, 15, tzinfo=timezone),
    )
    after_midnight = calculator.audit(
        checked_rule,
        date(2026, 9, 14),
        date(2026, 9, 14),
        as_of=datetime(2026, 9, 15, 0, 1, tzinfo=timezone),
    )

    assert checked_rule.grace_days == 0
    assert checked_rule.release_after == time(23, 15)
    assert before.expected_partitions == 0
    assert after.missing_partitions == 1
    assert after_midnight.missing_partitions == 1


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

    assert result.status == "complete"
    assert result.expected_partitions == 1
    assert result.missing_partitions == 0
    assert result.partitions[0].status == "present"


def test_upstream_availability_boundary_does_not_create_fake_history_gaps():
    checked_rule = CoverageRule(
        dataset_name="tdx_daily",
        table="tdx_daily",
        date_column="trade_date",
        date_storage=DateStorage.COMPACT,
        strategy=CoverageStrategy.TRADING_DAILY,
        availability_start=date(2025, 3, 28),
    )
    repository = FakeCoverageRepository(
        actual=[ActualPartition(date(2025, 3, 28), 485, None)],
        expected=[date(2024, 1, 2), date(2025, 3, 28)],
    )

    result = CoverageCalculator(repository).audit(
        checked_rule,
        date(2024, 1, 1),
        date(2025, 3, 28),
        as_of=date(2025, 3, 30),
    )

    assert result.status == "complete"
    assert result.expected_partitions == 1
    assert result.missing_partitions == 0
    assert result.evidence["availability_start"] == "2025-03-28"


def test_every_public_dataset_has_an_explicit_coverage_classification():
    rules = COVERAGE_RULES.list()

    assert len(rules) == len(DATASETS.list()) == 194
    assert {item.dataset_name for item in rules} == {
        item.name for item in DATASETS.list()
    }
    assert all(item.coverage_level for item in rules)
    assert all(item.auditable for item in rules)
    assert all(
        item.date_column for item in rules if item.strict_audit_mode != "exhaustive_snapshot"
    )
    assert all(
        item.date_column is None
        for item in rules
        if item.strict_audit_mode == "exhaustive_snapshot"
    )


def test_fund_nav_audit_matches_history_partition_contract():
    rule = COVERAGE_RULES.get("fund_nav")

    assert DATASETS.get("fund_nav").date_column == "nav_date"
    assert rule.date_column == "nav_date"
    assert rule.date_storage == DateStorage.DATE


def test_fund_share_is_event_sparse_not_daily_expected():
    """Fund shares publish on irregular disclosure dates, not every SSE day."""

    rule = COVERAGE_RULES.get("fund_share")

    assert rule.strategy == CoverageStrategy.OBSERVED_ONLY
    assert rule.scheduled is False


def test_only_proven_rules_are_automatically_scheduled():
    scheduled = COVERAGE_RULES.scheduled()

    assert len(scheduled) == 58
    assert all(item.auditable for item in scheduled)
    assert COVERAGE_RULES.get("adj_factor").scheduled is True
    assert COVERAGE_RULES.get("adj_factor").coverage_level == "expected_partitions"
    assert COVERAGE_RULES.get("ccass_hold").coverage_level == "observed_scope_transport"
    assert COVERAGE_RULES.get("ccass_hold").entity_column == "ts_code"
    assert COVERAGE_RULES.get("ccass_hold_detail").scheduled is False
    assert COVERAGE_RULES.get("ccass_hold_detail").entity_column == "ts_code"
    assert COVERAGE_RULES.get("hk_daily").scheduled is True
    assert COVERAGE_RULES.get("cn_gdp").strategy.value == "report_quarterly"
    assert COVERAGE_RULES.get("cn_gdp").availability_start == date(1992, 3, 31)
    assert COVERAGE_RULES.get("cn_pmi").strategy.value == "calendar_monthly"
    assert COVERAGE_RULES.get("cn_pmi").availability_start == date(2005, 1, 1)
    assert COVERAGE_RULES.get("sf_month").strategy.value == "calendar_monthly"
    assert COVERAGE_RULES.get("sf_month").availability_start == date(2002, 1, 1)
    assert COVERAGE_RULES.get("cn_ppi").availability_start == date(1993, 1, 1)
    assert COVERAGE_RULES.get("industry_daily").availability_start == date(2020, 1, 1)
    assert COVERAGE_RULES.get("stock_limit").availability_start == date(2007, 1, 4)
    assert COVERAGE_RULES.get("ggt_monthly").collection_api_name == "ggt_monthly"
    assert COVERAGE_RULES.get("ggt_monthly").availability_start == date(2014, 11, 1)
    assert COVERAGE_RULES.get("shibor").strategy.value == "trading_daily"
    assert COVERAGE_RULES.get("shibor_lpr").strategy.value == "calendar_monthly"
    assert COVERAGE_RULES.get("sge_daily").strategy.value == "trading_daily"
    etf_share = COVERAGE_RULES.get("etf_share_size")
    assert etf_share.accept_verified_empty is True
    assert etf_share.revision == 3
    tdx_daily = COVERAGE_RULES.get("tdx_daily")
    assert tdx_daily.availability_start == date(2025, 3, 28)
    assert tdx_daily.revision == 2
    repurchase = COVERAGE_RULES.get("repurchase")
    assert repurchase.strategy.value == "calendar_monthly"
    assert repurchase.availability_start == date(2015, 1, 1)
    assert repurchase.accept_verified_empty is True
    assert repurchase.require_transport_proof is True
    assert repurchase.revision == 3


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


def test_non_temporal_rule_requires_verified_exhaustive_snapshot():
    checked_rule = CoverageRule(
        dataset_name="stock_basic",
        table="stock_basic",
        date_column=None,
        date_storage=DateStorage.DATE,
        strategy=CoverageStrategy.NON_TEMPORAL,
    )

    result = CoverageCalculator(FakeCoverageRepository()).audit(
        checked_rule,
        date(2026, 8, 1),
        date(2026, 8, 2),
    )

    assert result.status == "complete"
    assert result.expected_partitions == 1
    assert result.present_partitions == 1
    assert result.evidence["strict_audit_mode"] == "exhaustive_snapshot"


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
