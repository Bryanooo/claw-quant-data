from datetime import date

import pytest

from service.data_coverage.models import (
    CoverageAuditResult,
    CoveragePartition,
    CoverageStrategy,
)
from service.orchestration_v2.audit_runtime import (
    TaskAuditContractDriftError,
    TaskAuditNotImplementedError,
    TaskAuditRuntime,
)
from service.orchestration_v2.contracts import TaskDefinitionDocument
from tests.test_orchestration_v2 import acquisition_definition


class FakeRule:
    dataset_name = "stock_daily_basic"
    strict_audit_mode = "expected_partition"
    revision = 1
    availability_start = None
    date_column = "trade_date"
    strategy = CoverageStrategy.TRADING_DAILY
    entity_reference = None
    min_entity_ratio = None
    require_transport_proof = False
    accept_verified_empty = False


class FakeRegistry:
    def __init__(self, rule=None):
        self.rule = rule or FakeRule()

    def get(self, _name):
        return self.rule


class FakeCalculator:
    def __init__(self):
        self.verified_transport_dates = None
        self.verified_empty_transport_dates = None

    def audit(
        self,
        rule,
        start_date,
        end_date,
        *,
        as_of=None,
        verified_transport_dates=None,
        verified_empty_transport_dates=None,
    ):
        self.verified_transport_dates = verified_transport_dates
        self.verified_empty_transport_dates = verified_empty_transport_dates
        return CoverageAuditResult(
            dataset_name=rule.dataset_name,
            strategy="trading_daily",
            start_date=start_date,
            end_date=end_date,
            status="gaps",
            expected_partitions=1,
            present_partitions=0,
            missing_partitions=1,
            observed_partitions=0,
            coverage_ratio=0.0,
            partitions=(CoveragePartition(
                partition_date=start_date,
                status="missing",
                row_count=0,
                entity_count=0,
                expected=True,
            ),),
            evidence={"transport_checked": True},
        )


def test_task_audit_runtime_keeps_collection_success_separate_from_data_state():
    runtime = TaskAuditRuntime(repository=object(), registry=FakeRegistry())
    runtime._calculator = FakeCalculator()
    document = TaskDefinitionDocument.model_validate(acquisition_definition())

    result, state = runtime.audit_output(
        document,
        dataset_name="stock_daily_basic",
        observation_key="2026-09-24",
        start_date=date(2026, 9, 24),
        end_date=date(2026, 9, 24),
    )

    assert result.status == "gaps"
    assert state.data_status.value == "gaps"
    assert state.ready is False
    assert state.validation_summary["verified"] is True


def test_task_audit_runtime_rejects_definition_code_drift():
    rule = FakeRule()
    rule.revision = 2
    runtime = TaskAuditRuntime(repository=object(), registry=FakeRegistry(rule))
    runtime._calculator = FakeCalculator()
    document = TaskDefinitionDocument.model_validate(acquisition_definition())

    with pytest.raises(TaskAuditContractDriftError, match="contract drift"):
        runtime.audit_output(
            document,
            dataset_name="stock_daily_basic",
            observation_key="2026-09-24",
            start_date=date(2026, 9, 24),
            end_date=date(2026, 9, 24),
        )


def test_verified_v2_transport_is_passed_to_partition_audit():
    runtime = TaskAuditRuntime(repository=object(), registry=FakeRegistry())
    calculator = FakeCalculator()
    runtime._calculator = calculator
    document = TaskDefinitionDocument.model_validate(acquisition_definition())

    runtime.audit_output(
        document,
        dataset_name="stock_daily_basic",
        observation_key="2026-09-24",
        start_date=date(2026, 9, 24),
        end_date=date(2026, 9, 24),
        transport_evidence=[
            {
                "completion_status": "complete",
                "completion_evidence": {"verified": True},
                "rows_fetched": 100,
            }
        ],
    )

    assert calculator.verified_transport_dates == {date(2026, 9, 24)}
    assert calculator.verified_empty_transport_dates == set()


def test_verified_empty_transport_is_distinct_from_nonempty_transport():
    runtime = TaskAuditRuntime(repository=object(), registry=FakeRegistry())
    calculator = FakeCalculator()
    runtime._calculator = calculator
    document = TaskDefinitionDocument.model_validate(acquisition_definition())

    runtime.audit_output(
        document,
        dataset_name="stock_daily_basic",
        observation_key="2026-09-24",
        start_date=date(2026, 9, 24),
        end_date=date(2026, 9, 24),
        transport_evidence=[{
            "completion_status": "empty",
            "completion_evidence": {"verified": True},
            "rows_fetched": 0,
        }],
    )

    assert calculator.verified_empty_transport_dates == {date(2026, 9, 24)}


def test_accepted_expected_empty_is_persisted_as_empty_verified():
    rule = FakeRule()
    rule.accept_verified_empty = True
    runtime = TaskAuditRuntime(repository=object(), registry=FakeRegistry(rule))
    calculator = FakeCalculator()
    original = calculator.audit

    def accepted_empty(*args, **kwargs):
        result = original(*args, **kwargs)
        return CoverageAuditResult(
            dataset_name=result.dataset_name,
            strategy=result.strategy,
            start_date=result.start_date,
            end_date=result.end_date,
            status="complete",
            expected_partitions=1,
            present_partitions=1,
            missing_partitions=0,
            observed_partitions=1,
            coverage_ratio=1.0,
            partitions=result.partitions,
            evidence={},
        )

    calculator.audit = accepted_empty
    runtime._calculator = calculator
    definition = acquisition_definition()
    definition["validation_contract"]["dataset_audits"][0][
        "accepts_verified_empty"
    ] = True
    document = TaskDefinitionDocument.model_validate(definition)

    result, state = runtime.audit_output(
        document,
        dataset_name="stock_daily_basic",
        observation_key="2026-09-24",
        start_date=date(2026, 9, 24),
        end_date=date(2026, 9, 24),
        transport_evidence=[{
            "completion_status": "empty",
            "completion_evidence": {"verified": True},
            "rows_fetched": 0,
        }],
    )

    assert result.status == "empty"
    assert state.data_status.value == "empty_verified"
    assert state.ready is True
    assert result.evidence["verified_empty_persisted"] is True


def test_expected_partition_cannot_succeed_with_zero_expectations():
    runtime = TaskAuditRuntime(repository=object(), registry=FakeRegistry())
    calculator = FakeCalculator()
    original = calculator.audit

    def empty_expectation(*args, **kwargs):
        result = original(*args, **kwargs)
        return CoverageAuditResult(
            dataset_name=result.dataset_name,
            strategy=result.strategy,
            start_date=result.start_date,
            end_date=result.end_date,
            status="empty",
            expected_partitions=0,
            present_partitions=0,
            missing_partitions=0,
            observed_partitions=0,
            coverage_ratio=None,
            partitions=(),
            evidence={},
        )

    calculator.audit = empty_expectation
    runtime._calculator = calculator
    document = TaskDefinitionDocument.model_validate(acquisition_definition())

    with pytest.raises(TaskAuditNotImplementedError, match="no mature expected"):
        runtime.audit_output(
            document,
            dataset_name="stock_daily_basic",
            observation_key="2026-09-24",
            start_date=date(2026, 9, 24),
            end_date=date(2026, 9, 24),
        )


def test_verified_exact_slice_can_complete_before_coarser_period_matures():
    runtime = TaskAuditRuntime(repository=object(), registry=FakeRegistry())
    calculator = FakeCalculator()
    original = calculator.audit

    def empty_expectation(*args, **kwargs):
        result = original(*args, **kwargs)
        return CoverageAuditResult(
            dataset_name=result.dataset_name,
            strategy=result.strategy,
            start_date=result.start_date,
            end_date=result.end_date,
            status="empty",
            expected_partitions=0,
            present_partitions=0,
            missing_partitions=0,
            observed_partitions=0,
            coverage_ratio=None,
            partitions=(),
            evidence={"aggregate_period": "not_yet_mature"},
        )

    calculator.audit = empty_expectation
    runtime._calculator = calculator
    document = TaskDefinitionDocument.model_validate(acquisition_definition())

    result, state = runtime.audit_output(
        document,
        dataset_name="stock_daily_basic",
        observation_key="2026-09-24",
        start_date=date(2026, 9, 24),
        end_date=date(2026, 9, 24),
        transport_evidence=[{
            "completion_status": "empty",
            "completion_evidence": {"verified": True},
            "rows_fetched": 0,
        }],
    )

    assert result.status == "empty"
    assert result.expected_partitions == 1
    assert result.evidence["aggregate_period_certified"] is False
    assert state.data_status.value == "empty_verified"
    assert state.ready is True
