"""Domain models and errors for the data service."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date
from enum import Enum

DateValue = date | str


class DateStorage(str, Enum):
    DATE = "date"
    COMPACT = "compact"


@dataclass(frozen=True, slots=True)
class DatasetSpec:
    """Public contract for one queryable dataset."""

    name: str
    table: str
    description: str
    category: str
    primary_keys: tuple[str, ...]
    exact_filters: Mapping[str, str] = field(default_factory=dict)
    date_column: str | None = None
    date_storage: DateStorage = DateStorage.DATE
    default_order: tuple[str, ...] = ()
    default_descending: bool = True
    max_page_size: int = 1000
    freshness_sla_hours: int | None = None
    freshness_policy: str = "unconfigured"
    source: str = "Tushare Pro"
    storage_semantics: str = "canonical_upsert"
    business_identity_fields: tuple[str, ...] = ()
    identity_confidence: str = "database_constraint"
    current_view: str | None = None

    @property
    def read_table(self) -> str:
        return self.current_view or self.table


@dataclass(frozen=True, slots=True)
class DatasetQuery:
    exact_filters: Mapping[str, str]
    date: DateValue | None = None
    start_date: DateValue | None = None
    end_date: DateValue | None = None
    limit: int = 100
    offset: int = 0
    include_total: bool = False


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
