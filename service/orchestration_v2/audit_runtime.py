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
from service.data_coverage.registry import COVERAGE_RULES, CoverageRuleRegistry, AUDIT_PREVIOUS_RULE_REVISIONS
from service.data_coverage.repository import CoverageRepository
from service.orchestration_v2.contracts import (
    DataStatus,
    DatasetAuditContract,
    DatasetStateUpdate,
    TaskDefinitionDocument,
)
from service.data_coverage.publication import NEXT_DAY_EMPTY_CONFIRMATION
from service.data_coverage.transport import transport_manifest
from service.data_coverage.diagnostics import audit_issues
from service.orchestration_v2.audit_contracts import (
    coverage_rule_audit_contract,
)


class TaskAuditContractDriftError(RuntimeError):
    """The running code no longer agrees with the frozen task definition."""

    # Re-running the same immutable definition cannot heal a contract upgrade.
    # Publish/replan a compatible version instead of spending retry attempts.
    retryable = False


class TaskAuditNotImplementedError(RuntimeError):
    """A planned output has no executable audit implementation yet."""

    retryable = False


class TaskAuditNoMatureExpectedPartitionError(TaskAuditNotImplementedError):
    """A bounded scope is not yet an independently mature aggregate period.

    This is a preflight result, not an acquisition failure.  Repair workflows
    must still execute their bounded provider request so that transport proof
    can certify the exact slice; genuinely missing audit implementations keep
    raising :class:`TaskAuditNotImplementedError` and remain fail-closed.
    """


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
        expected_requests: list[dict] | None = None,
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
        contract = self._effective_contract(contract)
        # OBSERVED_ONLY datasets cannot infer a missing logical period from
        # table dates alone (for example dividend is requested by ann_date but
        # stored by ex_date). The current acquire node counts only when every
        # bounded request explicitly proved complete or empty.
        manifest = transport_manifest(transport_evidence, expected_requests)
        transport = manifest['records']
        transport_verified = manifest['verified'] and manifest['rows_fetched'] is not None
        verified_transport_dates = (
            set(
                start_date + timedelta(days=offset)
                for offset in range((end_date - start_date).days + 1)
            )
            if transport_verified
            else set()
        )
        fetched = manifest["rows_fetched"]
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
            and not any(p.row_count for p in result.partitions)
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
            and result.partial_partitions == 0
            and result.evidence.get("calendar_complete_for_range") is not False
        ):
            if (not transport_verified
                    or contract.period_granularity not in {"week", "month", "quarter"}
                    or start_date != end_date):
                raise TaskAuditNoMatureExpectedPartitionError(
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
            and result.partial_partitions == 0
            and not result.evidence.get("invalid_balance_rows")
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
        # A current failed/missing proof must not inherit old physical-row
        # readiness. Full acquisition plans are authoritative about transport,
        # never about business-value validity or the existence of a snapshot.
        if transport_evidence is not None and not transport_verified:
            result = replace(result, status="unverified", coverage_ratio=None,
                evidence={**result.evidence, "issues": [{"code": "transport_manifest_incomplete",
                    **{key: value for key, value in manifest.items() if key != "records"}}]})
        if transport_verified and fetched > 0 and (
            any(item.get("rows_inserted") == 0 for item in transport if int(item.get("rows_fetched") or 0) > 0)
            or (contract.audit_mode == "exhaustive_snapshot" and result.evidence.get("row_count") == 0)
        ):
            result = replace(result, status="unverified", coverage_ratio=None,
                evidence={**result.evidence, "issues": [{"code": "response_not_persisted"}]})
        if (transport_verified and fetched == 0 and contract.audit_mode == "exhaustive_snapshot"
                and result.evidence.get("row_count", 0) > 0):
            result = replace(result, status="unverified", coverage_ratio=None,
                evidence={**result.evidence, "issues": [{"code": "snapshot_response_storage_mismatch",
                    "response_rows": 0, "stored_rows": result.evidence["row_count"]}]})
        result = replace(result, evidence={**result.evidence,
            "transport_manifest": {key: value for key, value in manifest.items() if key != "records"}})
        provisional_preflight = (
            not transport_verified and dataset_name in NEXT_DAY_EMPTY_CONFIRMATION
            and result.status in {"complete", "empty"}
            and not any(part.row_count for part in result.partitions)
        )
        if provisional_preflight or (transport_verified and fetched == 0 and result.status == "empty"):
            rule = self._registry.get(dataset_name)
            min_age = getattr(rule, "verified_empty_min_age_days", None)
            if dataset_name in NEXT_DAY_EMPTY_CONFIRMATION:
                min_age = max(min_age or 0, 1)
            if min_age:
                earliest = end_date + timedelta(days=min_age)
                # Resuming validation tomorrow must not age yesterday's request.
                confirmed = transport_verified and all(
                    (item.get("request_day") or "") >= earliest.isoformat()
                    for item in transport
                )
                result = replace(
                    result, status="empty" if confirmed else "unverified",
                    coverage_ratio=result.coverage_ratio if confirmed else None,
                    evidence={**result.evidence, "empty_confirmed_after_window": confirmed,
                              "empty_confirm_on_or_after": earliest.isoformat(),
                              "verified_empty_persisted": confirmed},
                )
        status = {
            "complete": DataStatus.COMPLETE,
            "empty": DataStatus.EMPTY_VERIFIED,
            "gaps": DataStatus.GAPS,
            "unverified": DataStatus.INDETERMINATE,
        }[result.status]
        if result.status == "gaps" and result.partial_partitions and not result.missing_partitions:
            status = DataStatus.PARTIAL
        issues = audit_issues(result)
        validation = {
            "issues": issues[:50],
            "issue_count": len(issues),
            "verified": result.status in {"complete", "empty", "gaps"},
            "audit_status": result.status,
            "audit_mode": contract.audit_mode,
            "rule_revision": result.evidence.get('rule_revision', contract.rule_revision),
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
            contract_version=f"coverage-rule:{validation['rule_revision']}",
            expectation_status="expected",
            data_status=status,
            expected_count=result.expected_partitions,
            actual_count=result.present_partitions,
            gap_summary={
                "missing": result.missing_partitions,
                "partial": result.partial_partitions,
                "issues": issues[:20],
                "issue_count": len(issues),
            },
            validation_summary=validation,
        )
        if persist:
            # Keep the shared strict-audit partition ledger current so the
            # data calendar and migration reports observe V2 repairs without
            # creating a fake legacy coverage-job instance.
            self._repository.save_audit(None, result)
        return result, update

    def _effective_contract(self, contract: DatasetAuditContract) -> DatasetAuditContract:
        try:
            rule = self._registry.get(contract.dataset_name)
        except CoverageRuleNotFoundError as exc:
            raise TaskAuditNotImplementedError(
                f"no executable coverage rule for {contract.dataset_name}"
            ) from exc
        running_contract = coverage_rule_audit_contract(rule)
        # Existing chip jobs retain their acquisition checkpoints. Allow only
        # this audited, strictly stronger coverage migration; all other drift
        # still fails closed. Evidence records the running rule revision.
        if (contract.dataset_name == 'cyq_chips'
                and contract.rule_revision == 2
                and contract.min_entity_ratio == 0.90
                and contract.model_copy(update={
                    'rule_revision': 4, 'min_entity_ratio': 1.0, 'require_transport_proof': True,
                }) == running_contract):
            contract = running_contract
        if (contract.dataset_name in {'stk_factor', 'stk_factor_pro'}
                and contract.rule_revision == 5 and contract.min_entity_ratio == 0.90
                and contract.model_copy(update={
                    'rule_revision': 7, 'min_entity_ratio': 1.0, 'require_transport_proof': True,
                }) == running_contract):
            contract = running_contract
        # Explicit monotonic migration: old definitions retain checkpoints but
        # are evaluated with the stronger whole-request proof requirement.
        upgraded = contract.model_copy(update={
            "require_transport_proof": True, "rule_revision": contract.rule_revision + 1})
        if not contract.require_transport_proof and upgraded == running_contract:
            contract = running_contract
        # This engine upgrade also strengthens sparse/snapshot scope proof
        # and derived payload predicates. Identical frozen contract fields
        # may advance by this one code-owned revision, never weaken a rule.
        if (contract.rule_revision == AUDIT_PREVIOUS_RULE_REVISIONS.get(contract.dataset_name)
                and contract.model_copy(update={"rule_revision": contract.rule_revision + 1}) == running_contract):
            contract = running_contract
        if (contract.dataset_name in {'fina_mainbz', 'local_factor_snapshot'}
                and contract.rule_revision in {running_contract.rule_revision - 1, running_contract.rule_revision - 2}
                and contract.model_copy(update={'rule_revision': running_contract.rule_revision}) == running_contract):
            contract = running_contract
        # Migrate only the exact historical request-date contract. Old IPO
        # snapshots and event business dates are re-audited at the request date.
        legacy_dates = {'dividend':'end_date', 'stk_managers':'begin_date', 'new_share':None}
        if contract.dataset_name in {'fund_company','fut_weekly_detail'} and contract.rule_revision in {1,2}:
            previous_snapshot = contract.dataset_name == 'fut_weekly_detail'
            old = running_contract.model_copy(update={
                'date_column': None if previous_snapshot else 'end_date', 'rule_revision':contract.rule_revision,
                'audit_mode':'exhaustive_snapshot' if previous_snapshot else 'observed_scope_transport',
                'period_granularity':'snapshot' if previous_snapshot else 'day'})
            if old == contract:
                contract = running_contract
        if contract.dataset_name in legacy_dates and contract.rule_revision in {1,2}:
            snapshot = contract.dataset_name == 'new_share'
            old = running_contract.model_copy(update={
                'date_column':legacy_dates[contract.dataset_name], 'rule_revision':contract.rule_revision,
                'audit_mode':'exhaustive_snapshot' if snapshot else 'observed_scope_transport',
                'period_granularity':'snapshot' if snapshot else 'day'})
            if old == contract:
                contract = running_contract
        # The canonical daily_basic alias previously selected the generic
        # observed-only rule over the same physical table.
        if (contract.dataset_name == "daily_basic" and contract.rule_revision == 1
                and contract.audit_mode == "observed_scope_transport"
                and contract.date_column == "trade_date"
                and not contract.required_values and contract.entity_reference is None):
            contract = running_contract
        if running_contract != contract:
            raise TaskAuditContractDriftError(
                f"audit contract drift for {contract.dataset_name}: "
                f"frozen={contract.model_dump(mode='json')!r}, "
                f"running={running_contract.model_dump(mode='json')!r}"
            )
        return contract

    def _audit_registered_dataset(
        self,
        contract: DatasetAuditContract,
        start_date: date,
        end_date: date,
        as_of: date | datetime | None,
        verified_transport_dates: set[date],
        verified_empty_transport_dates: set[date],
    ) -> CoverageAuditResult:
        rule = self._registry.get(contract.dataset_name)
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
