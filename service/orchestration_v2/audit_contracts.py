"""Compile governed data-coverage rules into V2 task validation contracts."""

from __future__ import annotations

from service.data_coverage.models import (
    CoverageRule,
    CoverageRuleNotFoundError,
    CoverageStrategy,
)
from service.data_coverage.registry import COVERAGE_RULES
from service.orchestration_v2.contracts import (
    DatasetAuditContract,
    TaskValidationContract,
)


_PERIOD_BY_STRATEGY = {
    CoverageStrategy.TRADING_DAILY: "day",
    CoverageStrategy.TRADING_WEEKLY: "week",
    CoverageStrategy.TRADING_MONTHLY: "month",
    CoverageStrategy.CALENDAR_MONTHLY: "month",
    CoverageStrategy.REPORT_QUARTERLY: "quarter",
    CoverageStrategy.OBSERVED_ONLY: "day",
    CoverageStrategy.NON_TEMPORAL: "snapshot",
}

# These are planned materialized research products. Their tables and normal
# coverage rules are intentionally not published yet, but their V2 definition
# must already state how readiness will be proven before the task can go live.
_PLANNED_DERIVED_AUDITS: dict[str, tuple[str, str]] = {
    "adjusted_price_return": ("expected_partition", "day"),
    "canonical_period_bars": ("dependency_scoped", "dependency"),
    "technical_factor_snapshot": ("expected_partition", "day"),
    "valuation_percentile_snapshot": ("expected_partition", "day"),
    "market_breadth": ("expected_partition", "day"),
    "sector_breadth": ("expected_partition", "day"),
    "etf_flow": ("expected_partition", "day"),
    "sector_rotation": ("expected_partition", "day"),
    "industry_fundamental_snapshot": ("expected_partition", "quarter"),
    "repurchase_progress_snapshot": ("expected_partition", "month"),
    "investment_event_calendar": ("expected_partition", "day"),
    "macro_regime": ("expected_partition", "month"),
    "etf_state_team_signal": ("expected_partition", "day"),
}


def dataset_audit_contract(dataset_name: str) -> DatasetAuditContract:
    """Return the code-owned audit contract for a current or planned output."""
    try:
        rule = COVERAGE_RULES.get(dataset_name)
    except CoverageRuleNotFoundError:
        planned = _PLANNED_DERIVED_AUDITS.get(dataset_name)
        if planned is None:
            raise ValueError(
                f"no V2 audit contract is defined for output dataset: {dataset_name}"
            ) from None
        audit_mode, granularity = planned
        return DatasetAuditContract(
            dataset_name=dataset_name,
            audit_mode=audit_mode,
            period_granularity=granularity,
            require_transport_proof=True,
        )

    return coverage_rule_audit_contract(rule)


def coverage_rule_audit_contract(rule: CoverageRule) -> DatasetAuditContract:
    """Compile one executable coverage rule into its frozen V2 contract."""
    return DatasetAuditContract(
        dataset_name=rule.dataset_name,
        audit_mode=rule.strict_audit_mode,
        period_granularity=_PERIOD_BY_STRATEGY[rule.strategy],
        rule_revision=rule.revision,
        availability_start=rule.availability_start,
        date_column=rule.date_column,
        entity_reference=rule.entity_reference,
        min_entity_ratio=rule.min_entity_ratio,
        require_transport_proof=rule.require_transport_proof,
        accepts_verified_empty=rule.accept_verified_empty,
    )


def task_validation_contract(
    output_datasets: tuple[str, ...],
) -> TaskValidationContract:
    return TaskValidationContract(
        outputs=output_datasets,
        dataset_audits=tuple(
            dataset_audit_contract(dataset_name)
            for dataset_name in output_datasets
        ),
    )


def observation_granularity(contract: TaskValidationContract) -> str:
    """Return one unambiguous execution boundary for a task definition."""
    granularities = {
        item.period_granularity for item in contract.dataset_audits
    }
    if len(granularities) != 1:
        raise ValueError(
            "one task cannot publish outputs with different execution granularities"
        )
    return next(iter(granularities))
