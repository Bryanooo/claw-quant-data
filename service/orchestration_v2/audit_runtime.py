"""Code-owned validation runtime for V2 task outputs.

Collection success and data readiness are deliberately separate facts.  This
module is the implementation behind the V2 ``validate`` node: it evaluates a
frozen audit contract against business tables and transport evidence without
trusting the preceding acquire/transform node's exit status.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime, timedelta
from typing import Callable

from service.data_coverage.calculator import CoverageCalculator
from service.data_coverage.models import (
    CoverageAuditResult,
    CoverageRuleNotFoundError,
)
from service.data_coverage.registry import COVERAGE_RULES, CoverageRuleRegistry
from service.data_coverage.repository import CoverageRepository
from service.orchestration_v2.contracts import (
    DataStatus,
    DatasetAuditContract,
    DatasetStateUpdate,
    TaskDefinitionDocument,
)
from service.orchestration_v2.audit_contracts import (
    coverage_rule_audit_contract,
)


class TaskAuditContractDriftError(RuntimeError):
    """The running code no longer agrees with the frozen task definition."""


class TaskAuditNotImplementedError(RuntimeError):
    """A planned output has no executable audit implementation yet."""


AuditHandler = Callable[
    [
        DatasetAuditContract,
        date,
        date,
        date | datetime | None,
        set[date],
        set[date],
    ],
    CoverageAuditResult,
]


class TaskAuditRuntime:
    """Dispatch V2 output audits through a code-owned handler allow-list."""

    def __init__(
        self,
        repository: CoverageRepository | None = None,
        registry: CoverageRuleRegistry = COVERAGE_RULES,
    ):
        self._repository = repository or CoverageRepository()
        self._registry = registry
        self._calculator = CoverageCalculator(self._repository)
        self._handlers: dict[str, AuditHandler] = {
            "expected_partition": self._audit_registered_dataset,
            "observed_scope_transport": self._audit_registered_dataset,
            "exhaustive_snapshot": self._audit_registered_dataset,
            # Dependency-scoped derived outputs become executable only after a
            # governed dataset rule/table exists. Draft metadata alone never
            # gets to certify readiness.
            "dependency_scoped": self._audit_dependency_scoped,
        }

    @property
    def handler_keys(self) -> frozenset[str]:
        return frozenset(self._handlers)

    def audit_output(
        self,
        document: TaskDefinitionDocument,
        *,
        dataset_name: str,
        observation_key: str,
        start_date: date,
        end_date: date,
        as_of: date | datetime | None = None,
        persist: bool = False,
        transport_evidence: list[dict] | None = None,
    ) -> tuple[CoverageAuditResult, DatasetStateUpdate]:
        contracts = {
            item.dataset_name: item
            for item in document.validation_contract.dataset_audits
        }
        try:
            contract = contracts[dataset_name]
        except KeyError as exc:
            raise ValueError(
                f"task {document.task_key} has no audit contract for {dataset_name}"
            ) from exc
        # OBSERVED_ONLY datasets cannot infer a missing logical period from
        # table dates alone (for example dividend is requested by ann_date but
        # stored by ex_date). The current acquire node counts only when every
        # bounded request explicitly proved complete or empty.
        transport = tuple(transport_evidence or ())
        transport_verified = bool(transport) and all(
            item.get("completion_status") in {"complete", "empty"}
            and (item.get("completion_evidence") or {}).get("verified") is True
            for item in transport
        )
        verified_transport_dates = (
            set(
                start_date + timedelta(days=offset)
                for offset in range((end_date - start_date).days + 1)
            )
            if transport_verified
            else set()
        )
        fetched = sum(int(item.get("rows_fetched") or 0) for item in transport)
        verified_empty_transport_dates = (
            set(verified_transport_dates)
            if transport_verified and fetched == 0
            else set()
        )
        result = self._handlers[contract.audit_mode](
            contract,
            start_date,
            end_date,
            as_of,
            verified_transport_dates,
            verified_empty_transport_dates,
        )
        if (
            contract.audit_mode == "expected_partition"
            and transport_verified
            and fetched == 0
            and result.status == "complete"
        ):
            # The calculator represents an accepted provider-authoritative
            # empty day as a synthetic present partition so completeness can
            # be evaluated.  Persist the stronger state explicitly; otherwise
            # the next independent full audit cannot distinguish that proof
            # from a still-missing physical row and rediscovers a false gap.
            result = replace(
                result,
                status="empty",
                present_partitions=0,
                observed_partitions=0,
                coverage_ratio=1.0,
                evidence={
                    **result.evidence,
                    "v2_transport_verified": True,
                    "v2_transport_rows_fetched": 0,
                    "verified_empty_persisted": True,
                },
            )
        if (
            contract.audit_mode == "expected_partition"
            and result.expected_partitions == 0
        ):
            if not transport_verified:
                raise TaskAuditNotImplementedError(
                    f"{contract.dataset_name} scope {start_date}..{end_date} "
                    "contains no mature expected partition"
                )
            # A routine exact-date request can be a slice inside a coarser
            # monthly audit period.  Exhaustive provider evidence certifies
            # that slice without pretending that the whole month is complete.
            # The independent monthly audit remains responsible for the
            # aggregate period.
            result = replace(
                result,
                status="complete" if fetched > 0 else "empty",
                expected_partitions=1,
                present_partitions=1 if fetched > 0 else 0,
                missing_partitions=0,
                partial_partitions=0,
                coverage_ratio=1.0,
                evidence={
                    **result.evidence,
                    "v2_transport_verified": True,
                    "v2_transport_requests": len(transport),
                    "v2_transport_rows_fetched": fetched,
                    "v2_transport_scope": "exact_execution_slice",
                    "aggregate_period_certified": False,
                },
            )
        if (
            contract.audit_mode in {
                "observed_scope_transport",
                "exhaustive_snapshot",
            }
            and transport_verified
        ):
            result = replace(
                result,
                status="complete" if fetched > 0 else "empty",
                expected_partitions=max(result.expected_partitions, 1),
                present_partitions=(
                    max(result.present_partitions, 1) if fetched > 0 else 0
                ),
                missing_partitions=0,
                partial_partitions=0,
                evidence={
                    **result.evidence,
                    "v2_transport_verified": True,
                    "v2_transport_requests": len(transport),
                    "v2_transport_rows_fetched": fetched,
                    "v2_transport_scope": "current_execution_logical_period",
                },
            )
        status = {
            "complete": DataStatus.COMPLETE,
            "empty": DataStatus.EMPTY_VERIFIED,
            "gaps": DataStatus.GAPS,
            "unverified": DataStatus.INDETERMINATE,
        }[result.status]
        validation = {
            "verified": result.status in {"complete", "empty", "gaps"},
            "audit_status": result.status,
            "audit_mode": contract.audit_mode,
            "rule_revision": contract.rule_revision,
            "expected_partitions": result.expected_partitions,
            "present_partitions": result.present_partitions,
            "missing_partitions": result.missing_partitions,
            "partial_partitions": result.partial_partitions,
            "evidence": result.evidence,
        }
        update = DatasetStateUpdate(
            dataset_name=dataset_name,
            observation_key=observation_key,
            observation_start=start_date,
            observation_end=end_date,
            observation_period=observation_key,
            contract_version=f"coverage-rule:{contract.rule_revision}",
            expectation_status="expected",
            data_status=status,
            expected_count=result.expected_partitions,
            actual_count=result.present_partitions,
            gap_summary={
                "missing": result.missing_partitions,
                "partial": result.partial_partitions,
            },
            validation_summary=validation,
        )
        if persist:
            # Keep the shared strict-audit partition ledger current so the
            # data calendar and migration reports observe V2 repairs without
            # creating a fake legacy coverage-job instance.
            self._repository.save_audit(None, result)
        return result, update

    def _audit_registered_dataset(
        self,
        contract: DatasetAuditContract,
        start_date: date,
        end_date: date,
        as_of: date | datetime | None,
        verified_transport_dates: set[date],
        verified_empty_transport_dates: set[date],
    ) -> CoverageAuditResult:
        try:
            rule = self._registry.get(contract.dataset_name)
        except CoverageRuleNotFoundError as exc:
            raise TaskAuditNotImplementedError(
                f"no executable coverage rule for {contract.dataset_name}"
            ) from exc
        running_contract = coverage_rule_audit_contract(rule)
        if running_contract != contract:
            raise TaskAuditContractDriftError(
                f"audit contract drift for {contract.dataset_name}: "
                f"frozen={contract.model_dump(mode='json')!r}, "
                f"running={running_contract.model_dump(mode='json')!r}"
            )
        # A task execution explicitly claims that its logical period is due.
        # Coverage grace belongs to discovery/scheduling; applying it again in
        # the validate node would turn today's required partition into an
        # empty expectation and manufacture a false success. Advance the
        # deterministic audit horizon just enough to include the claimed day.
        audit_as_of = as_of
        if contract.period_granularity == "day" and start_date == end_date:
            supplied_date = (
                as_of.date() if isinstance(as_of, datetime) else as_of
            )
            required_date = end_date + timedelta(
                days=getattr(rule, "grace_days", 0)
            )
            if supplied_date is None or supplied_date < required_date:
                audit_as_of = required_date
        return self._calculator.audit(
            rule,
            start_date,
            end_date,
            as_of=audit_as_of,
            verified_transport_dates=verified_transport_dates,
            verified_empty_transport_dates=verified_empty_transport_dates,
        )

    @staticmethod
    def _audit_dependency_scoped(
        contract: DatasetAuditContract,
        _start_date: date,
        _end_date: date,
        _as_of: date | datetime | None,
        _verified_transport_dates: set[date],
        _verified_empty_transport_dates: set[date],
    ) -> CoverageAuditResult:
        raise TaskAuditNotImplementedError(
            f"dependency-scoped audit is not published for {contract.dataset_name}"
        )
