"""Pure coverage comparison logic."""

from calendar import monthrange
from datetime import date, datetime, timedelta

from service.data_coverage.models import (
    ActualPartition,
    CoverageAuditResult,
    CoveragePartition,
    CoverageRule,
    CoverageStrategy,
)
from service.clock import SHANGHAI_TIMEZONE, business_now


def _quarter_end(year: int, quarter: int) -> date:
    month = quarter * 3
    return date(year, month, monthrange(year, month)[1])


def _quarter_due(period: date) -> date:
    if period.month == 3:
        return date(period.year, 4, 30)
    if period.month == 6:
        return date(period.year, 8, 31)
    if period.month == 9:
        return date(period.year, 10, 31)
    return date(period.year + 1, 4, 30)


def completed_quarters(start_date: date, end_date: date, as_of: date) -> list[date]:
    periods: list[date] = []
    for year in range(start_date.year - 1, end_date.year + 1):
        for quarter in range(1, 5):
            period = _quarter_end(year, quarter)
            if start_date <= period <= end_date and _quarter_due(period) <= as_of:
                periods.append(period)
    return sorted(periods)


def completed_months(start_date: date, end_date: date, as_of: date) -> list[date]:
    periods: list[date] = []
    cursor = date(start_date.year, start_date.month, 1)
    while cursor <= end_date:
        next_month = (
            date(cursor.year + 1, 1, 1)
            if cursor.month == 12
            else date(cursor.year, cursor.month + 1, 1)
        )
        period = next_month - timedelta(days=1)
        if start_date <= period <= end_date and period <= as_of:
            periods.append(period)
        cursor = next_month
    return periods


class CoverageCalculator:
    def __init__(self, repository):
        self._repository = repository

    def audit(
        self,
        rule: CoverageRule,
        start_date: date,
        end_date: date,
        *,
        as_of: date | datetime | None = None,
        entity_reference_as_of: date | None = None,
        verified_transport_dates: set[date] | None = None,
        verified_empty_transport_dates: set[date] | None = None,
    ) -> CoverageAuditResult:
        audit_time = as_of or business_now()
        # A date-only caller describes an end-of-business-day observation.
        # Runtime audits use an aware datetime so publication cut-offs can be
        # enforced without making deterministic historical audits time-sensitive.
        as_of_date = (
            audit_time.astimezone(SHANGHAI_TIMEZONE).date()
            if isinstance(audit_time, datetime)
            else audit_time
        )
        reference_as_of = entity_reference_as_of or business_now().date()
        if rule.strategy == CoverageStrategy.NON_TEMPORAL:
            snapshot = self._repository.snapshot_evidence(rule)
            latest = snapshot["latest_success"]
            verified_empty = bool(
                latest and latest.get("completion_status") == "empty_verified"
            )
            complete = bool(
                snapshot["verified"]
                and snapshot["unresolved_failures"] == 0
                and snapshot["active_history_jobs"] == 0
                and (snapshot["row_count"] > 0 or verified_empty)
            )
            return CoverageAuditResult(
                dataset_name=rule.dataset_name,
                strategy=rule.strategy.value,
                start_date=start_date,
                end_date=end_date,
                status="complete" if complete else "unverified",
                expected_partitions=1,
                present_partitions=int(complete),
                missing_partitions=0,
                observed_partitions=int(snapshot["row_count"] > 0),
                coverage_ratio=1.0 if complete else None,
                partitions=(),
                evidence={
                    "semantics": "exhaustive_snapshot_and_transport_proof",
                    "strict_audit_mode": rule.strict_audit_mode,
                    "rule_revision": rule.revision,
                    "row_count": snapshot["row_count"],
                    "api_name": snapshot["api_name"],
                    "verified_transport": snapshot["verified"],
                    "verified_empty": verified_empty,
                    "unresolved_failures": snapshot["unresolved_failures"],
                    "active_history_jobs": snapshot["active_history_jobs"],
                    "latest_success_job_id": (
                        latest.get("job_id") if latest else None
                    ),
                },
            )
        before_release = bool(
            isinstance(audit_time, datetime)
            and rule.release_after
            and audit_time.astimezone(SHANGHAI_TIMEZONE).time().replace(tzinfo=None)
            < rule.release_after
        )
        actual = {
            item.partition_date: item
            for item in self._repository.actual_partitions(
                rule,
                start_date,
                end_date,
                verified_transport_dates=verified_transport_dates,
                verified_empty_transport_dates=verified_empty_transport_dates,
            )
        }
        expectation_start = max(
            start_date,
            rule.availability_start or start_date,
        )

        if rule.strategy == CoverageStrategy.OBSERVED_ONLY:
            # Sparse/event datasets do not invent a daily calendar. Every
            # physically observed logical partition is nevertheless expected
            # to carry a successful, exhaustive transport certificate.
            expected_dates = list(actual)
            calendar_complete = None
            calendar_bounds = (None, None)
        elif rule.strategy == CoverageStrategy.REPORT_QUARTERLY:
            expected_dates = completed_quarters(
                expectation_start, end_date, as_of_date
            )
            calendar_complete = None
            calendar_bounds = (None, None)
        elif rule.strategy == CoverageStrategy.CALENDAR_MONTHLY:
            expected_dates = completed_months(
                expectation_start,
                end_date,
                as_of_date - timedelta(days=rule.grace_days),
            )
            calendar_complete = None
            calendar_bounds = (None, None)
        else:
            effective_grace_days = rule.grace_days + int(before_release)
            cutoff = min(end_date, as_of_date - timedelta(days=effective_grace_days))
            if cutoff < expectation_start:
                # The requested range only contains a not-yet-mature partition.
                # This is a verified empty expectation, not a calendar outage.
                calendar_bounds = (None, None)
                calendar_days = 0
                calendar_complete = True
                expected_dates = []
            else:
                calendar_min, calendar_max, calendar_days = (
                    self._repository.calendar_coverage(
                        rule.calendar_exchange,
                        expectation_start,
                        cutoff,
                    )
                )
                calendar_bounds = (calendar_min, calendar_max)
                required_calendar_days = (cutoff - expectation_start).days + 1
                calendar_complete = bool(
                    calendar_bounds[0]
                    and calendar_bounds[1]
                    and calendar_bounds[0] <= expectation_start
                    and calendar_bounds[1] >= cutoff
                    and calendar_days == required_calendar_days
                )
                expected_dates = self._repository.expected_market_partitions(
                    rule,
                    expectation_start,
                    cutoff,
                )

        scope_evidence = (
            self._repository.collection_scope_evidence(rule)
            if rule.strategy == CoverageStrategy.OBSERVED_ONLY
            else None
        )
        expected_set = set(expected_dates)
        entity_dates = [
            partition_date
            for partition_date in expected_dates
            if partition_date in actual
            and rule.entity_reference
            and (
                rule.entity_reference_max_age_days is None
                or partition_date
                >= reference_as_of
                - timedelta(days=rule.entity_reference_max_age_days - 1)
            )
        ]
        batch_entity_counts = getattr(
            self._repository, "expected_entity_counts", None
        )
        expected_entity_counts = (
            batch_entity_counts(rule, entity_dates)
            if callable(batch_entity_counts)
            else {}
        )
        dates = sorted(expected_set | set(actual))
        partitions: list[CoveragePartition] = []
        for partition_date in dates:
            observed = actual.get(partition_date)
            expected = partition_date in expected_set
            expected_entities = (
                expected_entity_counts[partition_date]
                if partition_date in expected_entity_counts
                else self._repository.expected_entity_count(rule, partition_date)
                if expected
                and observed
                and rule.entity_reference
                and (
                    rule.entity_reference_max_age_days is None
                    or partition_date
                    >= reference_as_of
                    - timedelta(days=rule.entity_reference_max_age_days - 1)
                )
                else None
            )
            entity_ratio = (
                observed.entity_count / expected_entities
                if observed
                and observed.entity_count is not None
                and expected_entities
                else None
            )
            small_early_market_tolerance = bool(
                rule.dataset_name in {"stock_daily", "stock_daily_basic"}
                and partition_date < date(1993, 1, 1)
                and observed
                and observed.entity_count is not None
                and expected_entities is not None
                and expected_entities <= 20
                and observed.entity_count >= expected_entities - 1
            )
            verified_empty_too_recent = bool(
                observed
                and observed.verified_empty
                and rule.verified_empty_min_age_days is not None
                and partition_date
                >= reference_as_of
                - timedelta(days=rule.verified_empty_min_age_days - 1)
            )
            if expected and observed:
                status = (
                    "partial"
                    if observed.known_incomplete
                    or verified_empty_too_recent
                    or (
                        rule.min_entity_ratio is not None
                        and entity_ratio is not None
                        and entity_ratio < rule.min_entity_ratio
                        and not small_early_market_tolerance
                    )
                    else "present"
                )
            elif expected:
                status = "missing"
            else:
                status = "observed_only"
            partitions.append(
                CoveragePartition(
                    partition_date=partition_date,
                    status=status,
                    row_count=observed.row_count if observed else 0,
                    entity_count=observed.entity_count if observed else 0,
                    expected=expected,
                    expected_entity_count=expected_entities,
                    entity_coverage_ratio=entity_ratio,
                )
            )

        present = sum(item.status == "present" for item in partitions)
        missing = sum(item.status == "missing" for item in partitions)
        partial = sum(item.status == "partial" for item in partitions)
        observed_count = len(actual)
        expected_count = len(expected_set)
        ratio = present / expected_count if expected_count else None
        if calendar_complete is False:
            status = "unverified"
        elif rule.strategy == CoverageStrategy.OBSERVED_ONLY:
            status = (
                "empty"
                if not observed_count
                and scope_evidence["verified_terminal_jobs"] > 0
                and scope_evidence["active_jobs"] == 0
                and scope_evidence["unresolved_failures"] == 0
                else "unverified"
                if scope_evidence["declared_jobs"] == 0
                or scope_evidence["active_jobs"] > 0
                or scope_evidence["verified_terminal_jobs"] == 0
                else "gaps"
                if missing or partial or scope_evidence["unresolved_failures"] > 0
                else "complete"
            )
        elif not expected_count and not observed_count:
            status = "empty"
        elif missing or partial:
            status = "gaps"
        else:
            status = "complete"

        return CoverageAuditResult(
            dataset_name=rule.dataset_name,
            strategy=rule.strategy.value,
            start_date=start_date,
            end_date=end_date,
            status=status,
            expected_partitions=expected_count,
            present_partitions=present,
            missing_partitions=missing,
            observed_partitions=observed_count,
            coverage_ratio=ratio,
            partitions=tuple(partitions),
            evidence={
                "semantics": "partition_and_entity_completeness",
                "strict_audit_mode": rule.strict_audit_mode,
                "absence_detection": (
                    "expected_calendar"
                    if rule.detects_missing_partitions
                    else "declared_collection_scope_required"
                ),
                "rule_revision": rule.revision,
                "calendar_exchange": (
                    rule.calendar_exchange if rule.detects_missing_partitions else None
                ),
                "grace_days": rule.grace_days,
                "availability_start": (
                    rule.availability_start.isoformat()
                    if rule.availability_start
                    else None
                ),
                "release_after": (
                    rule.release_after.isoformat(timespec="minutes")
                    if rule.release_after
                    else None
                ),
                "before_release": before_release,
                "detects_missing_partitions": rule.detects_missing_partitions,
                "calendar_complete_for_range": calendar_complete,
                "calendar_min_date": (
                    calendar_bounds[0].isoformat() if calendar_bounds[0] else None
                ),
                "calendar_max_date": (
                    calendar_bounds[1].isoformat() if calendar_bounds[1] else None
                ),
                "calendar_days_in_range": (
                    calendar_days
                    if rule.strategy not in {
                        CoverageStrategy.OBSERVED_ONLY,
                        CoverageStrategy.CALENDAR_MONTHLY,
                        CoverageStrategy.REPORT_QUARTERLY,
                    }
                    else None
                ),
                "entity_reference": rule.entity_reference,
                "entity_reference_max_age_days": (
                    rule.entity_reference_max_age_days
                ),
                "entity_reference_as_of": reference_as_of.isoformat(),
                "min_entity_ratio": rule.min_entity_ratio,
                "small_early_market_absolute_tolerance": (
                    1
                    if rule.dataset_name in {"stock_daily", "stock_daily_basic"}
                    else None
                ),
                "verified_empty_partitions": sum(
                    item.verified_empty for item in actual.values()
                ),
                "require_transport_proof": rule.require_transport_proof,
                "verified_empty_min_age_days": (
                    rule.verified_empty_min_age_days
                ),
                "known_incomplete_partitions": sum(
                    item.known_incomplete for item in actual.values()
                ),
                "v2_verified_transport_dates": sorted(
                    item.isoformat() for item in (verified_transport_dates or set())
                ),
                "v2_verified_empty_transport_dates": sorted(
                    item.isoformat()
                    for item in (verified_empty_transport_dates or set())
                ),
                "declared_scope_evidence": scope_evidence,
                "warning": "entity completeness is only enforced when a non-empty point-in-time reference universe is available",
            },
            partial_partitions=partial,
        )
