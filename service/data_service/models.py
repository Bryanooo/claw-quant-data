"""Domain models and errors for the data service."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Any

DateValue = date | str


class DateStorage(str, Enum):
    DATE = "date"
    COMPACT = "compact"
    MONTH = "month"
    QUARTER = "quarter"


@dataclass(frozen=True, slots=True)
class DatasetSpec:
    """Public contract for one queryable dataset."""

    name: str
    table: str
    description: str
    category: str
    primary_keys: tuple[str, ...]
    exact_filters: Mapping[str, str] = field(default_factory=dict)
    # Empty means every exact filter is safe by default. Versioned generic
    # datasets set this explicitly so unindexed measure columns require the
    # bounded advanced-filter opt-in.
    standard_filters: tuple[str, ...] = ()
    date_column: str | None = None
    date_storage: DateStorage = DateStorage.DATE
    availability_column: str | None = None
    availability_storage: DateStorage = DateStorage.DATE
    default_order: tuple[str, ...] = ()
    default_descending: bool = True
    max_page_size: int = 1000
    max_offset: int = 10_000
    freshness_sla_hours: int | None = None
    freshness_policy: str = "unconfigured"
    source: str = "Tushare Pro"
    # Stable machine identities support canonical datasets assembled from
    # more than one provider while retaining the human-readable source label.
    source_ids: tuple[str, ...] = ("tushare",)
    merge_policy: str = "single_source"
    storage_semantics: str = "canonical_upsert"
    business_identity_fields: tuple[str, ...] = ()
    identity_confidence: str = "database_constraint"
    current_view: str | None = None
    # Freshness probes must not force an expensive deduplicating current view
    # to materialize merely to read MAX(date). The explicitly named storage
    # relation carries the same partition dates and can use its date index.
    freshness_table: str | None = None

    @property
    def read_table(self) -> str:
        return self.current_view or self.table

    @property
    def freshness_read_table(self) -> str:
        return self.freshness_table or self.table

    @property
    def standard_filter_names(self) -> tuple[str, ...]:
        return self.standard_filters or tuple(self.exact_filters)

    @property
    def stable_order(self) -> tuple[str, ...]:
        configured = self.default_order or self.primary_keys
        return tuple(dict.fromkeys((*configured, *self.primary_keys)))


@dataclass(frozen=True, slots=True)
class DatasetQuery:
    exact_filters: Mapping[str, str]
    date: DateValue | None = None
    start_date: DateValue | None = None
    end_date: DateValue | None = None
    as_of: DateValue | None = None
    limit: int = 100
    offset: int = 0
    include_total: bool = False
    cursor_values: tuple[Any, ...] | None = None


class DataServiceError(Exception):
    """Base class for errors safe to expose through the API."""


class DatasetNotFoundError(DataServiceError):
    pass


class InterfaceDataNotFoundError(DataServiceError):
    pass


class RecordNotFoundError(DataServiceError):
    pass


class InvalidQueryError(DataServiceError):
    pass


class UpstreamFallbackError(DataServiceError):
    pass
