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
    ) -> CoverageAuditResult:
        if not rule.auditable:
            raise ValueError(
                f"dataset does not have auditable date partitions: {rule.dataset_name}"
            )
        audit_time = as_of or business_now()
        # A date-only caller describes an end-of-business-day observation.
        # Runtime audits use an aware datetime so publication cut-offs can be
        # enforced without making deterministic historical audits time-sensitive.
        as_of_date = audit_time.date() if isinstance(audit_time, datetime) else audit_time
        before_release = bool(
            isinstance(audit_time, datetime)
            and rule.release_after
            and audit_time.astimezone(SHANGHAI_TIMEZONE).time().replace(tzinfo=None)
            < rule.release_after
        )
        actual = {
            item.partition_date: item
            for item in self._repository.actual_partitions(rule, start_date, end_date)
        }

        if rule.strategy == CoverageStrategy.OBSERVED_ONLY:
            expected_dates: list[date] = []
            calendar_complete = None
            calendar_bounds = (None, None)
        elif rule.strategy == CoverageStrategy.REPORT_QUARTERLY:
            expected_dates = completed_quarters(start_date, end_date, as_of_date)
            calendar_complete = None
            calendar_bounds = (None, None)
        else:
            effective_grace_days = rule.grace_days + int(before_release)
            cutoff = min(end_date, as_of_date - timedelta(days=effective_grace_days))
            if cutoff < start_date:
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
                        start_date,
                        cutoff,
                    )
                )
                calendar_bounds = (calendar_min, calendar_max)
                required_calendar_days = (cutoff - start_date).days + 1
                calendar_complete = bool(
                    calendar_bounds[0]
                    and calendar_bounds[1]
                    and calendar_bounds[0] <= start_date
                    and calendar_bounds[1] >= cutoff
                    and calendar_days == required_calendar_days
                )
                expected_dates = self._repository.expected_market_partitions(
                    rule,
                    start_date,
                    cutoff,
                )

        expected_set = set(expected_dates)
        dates = sorted(expected_set | set(actual))
        partitions: list[CoveragePartition] = []
        for partition_date in dates:
            observed = actual.get(partition_date)
            expected = partition_date in expected_set
            expected_entities = (
                self._repository.expected_entity_count(rule, partition_date)
                if expected and observed and rule.entity_reference
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
            if expected and observed:
                status = (
                    "partial"
                    if observed.known_incomplete
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
            status = "observed_only"
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
                "calendar_exchange": (
                    rule.calendar_exchange if rule.detects_missing_partitions else None
                ),
                "grace_days": rule.grace_days,
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
                        CoverageStrategy.REPORT_QUARTERLY,
                    }
                    else None
                ),
                "entity_reference": rule.entity_reference,
                "min_entity_ratio": rule.min_entity_ratio,
                "small_early_market_absolute_tolerance": (
                    1
                    if rule.dataset_name in {"stock_daily", "stock_daily_basic"}
                    else None
                ),
                "verified_empty_partitions": sum(
                    item.verified_empty for item in actual.values()
                ),
                "known_incomplete_partitions": sum(
                    item.known_incomplete for item in actual.values()
                ),
                "warning": "entity completeness is only enforced when a non-empty point-in-time reference universe is available",
            },
            partial_partitions=partial,
        )
