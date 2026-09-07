"""Stable contracts shared by every collector implementation.

The contracts deliberately contain no scheduler or database dependencies.  A
collector can therefore be inspected and tested without constructing a
Tushare client, while workers receive a structured outcome instead of an
ambiguous integer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import Any, Mapping


class WriteMode(StrEnum):
    UPSERT = "upsert"
    SNAPSHOT = "snapshot"
    RAW_UPSERT = "raw_upsert"


class PaginationMode(StrEnum):
    NONE = "none"
    DATE_RANGE = "date_range"
    OFFSET = "offset"
    PARTITIONED = "partitioned"


class EmptyPolicy(StrEnum):
    """How a zero-row upstream response must be interpreted."""

    REQUIRES_VERIFICATION = "requires_verification"
    ALLOWED = "allowed"
    NON_TRADING_DAY_ONLY = "non_trading_day_only"
    RETRYABLE = "retryable"
    FATAL = "fatal"


class ResourceClass(StrEnum):
    REFERENCE = "reference"
    MARKET = "market"
    FINANCE = "finance"
    GENERIC = "generic"
    BACKFILL = "backfill"


@dataclass(frozen=True, slots=True)
class CollectorSpec:
    qualified_name: str
    api_name: str
    table_name: str
    primary_keys: tuple[str, ...]
    write_mode: WriteMode
    pagination_mode: PaginationMode
    empty_policy: EmptyPolicy
    resource_class: ResourceClass
    version: str = "1"
    required_parameters: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class CollectorRequest:
    """Validated-at-the-boundary request handed to a collector."""

    parameters: Mapping[str, Any] = field(default_factory=dict)
    skip_store: bool = False
    partition_key: str | None = None

    def __post_init__(self) -> None:
        # Prevent a caller from mutating parameters while a request is running.
        object.__setattr__(self, "parameters", MappingProxyType(dict(self.parameters)))


@dataclass(frozen=True, slots=True)
class CollectorResult:
    """Unambiguous result of one collector execution."""

    collector_name: str
    collector_version: str
    api_name: str
    table_name: str
    fetched_rows: int
    stored_rows: int
    request_count: int = 1
    partitions: tuple[str, ...] = ()
    empty_reason: str | None = None
    warnings: tuple[str, ...] = ()
    evidence: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "evidence", MappingProxyType(dict(self.evidence)))

    @property
    def is_empty(self) -> bool:
        return self.fetched_rows == 0
