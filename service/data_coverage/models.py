"""Domain contracts for bounded dataset coverage audits."""

from dataclasses import dataclass
from datetime import date, time
from enum import Enum

from service.data_service.models import DateStorage


class CoverageStrategy(str, Enum):
    TRADING_DAILY = "trading_daily"
    TRADING_WEEKLY = "trading_weekly"
    TRADING_MONTHLY = "trading_monthly"
    REPORT_QUARTERLY = "report_quarterly"
    OBSERVED_ONLY = "observed_only"
    NON_TEMPORAL = "non_temporal"


@dataclass(frozen=True, slots=True)
class CoverageRule:
    dataset_name: str
    table: str
    date_column: str | None
    date_storage: DateStorage
    strategy: CoverageStrategy
    entity_column: str | None = None
    calendar_exchange: str = "SSE"
    grace_days: int = 1
    # Some daily interfaces publish the previous trading-day partition on the
    # following morning.  Before this Shanghai-local time, the newest date is
    # not mature and must not be reported or auto-repaired as a gap.
    release_after: time | None = None
    default_lookback_days: int = 120
    description: str = ""
    entity_reference: str | None = None
    min_entity_ratio: float | None = None
    scheduled: bool = False
    # Some event-like daily interfaces legitimately publish no rows on an
    # otherwise open market day. Only a successful, verified empty collection
    # job for the exact partition may satisfy such an expectation.
    accept_verified_empty: bool = False

    @property
    def auditable(self) -> bool:
        return bool(
            self.date_column and self.strategy != CoverageStrategy.NON_TEMPORAL
        )

    @property
    def coverage_level(self) -> str:
        if self.strategy == CoverageStrategy.NON_TEMPORAL:
            return "not_applicable"
        if self.strategy == CoverageStrategy.OBSERVED_ONLY:
            return "observed_partitions"
        return "expected_partitions"

    @property
    def detects_missing_partitions(self) -> bool:
        return self.strategy not in {
            CoverageStrategy.OBSERVED_ONLY,
            CoverageStrategy.NON_TEMPORAL,
        }


@dataclass(frozen=True, slots=True)
class ActualPartition:
    partition_date: date
    row_count: int
    entity_count: int | None
    verified_empty: bool = False
    # Physical rows do not override an explicit truncated/incomplete attempt.
    known_incomplete: bool = False


@dataclass(frozen=True, slots=True)
class CoveragePartition:
    partition_date: date
    status: str
    row_count: int
    entity_count: int | None
    expected: bool
    expected_entity_count: int | None = None
    entity_coverage_ratio: float | None = None


@dataclass(frozen=True, slots=True)
class CoverageAuditResult:
    dataset_name: str
    strategy: str
    start_date: date
    end_date: date
    status: str
    expected_partitions: int
    present_partitions: int
    missing_partitions: int
    observed_partitions: int
    coverage_ratio: float | None
    partitions: tuple[CoveragePartition, ...]
    evidence: dict
    partial_partitions: int = 0


class CoverageError(Exception):
    """Base error safe to return from the coverage API."""


class CoverageRuleNotFoundError(CoverageError):
    pass


class InvalidCoverageRequestError(CoverageError):
    pass
