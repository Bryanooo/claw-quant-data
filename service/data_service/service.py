"""Use cases shared by REST and the future MCP adapter."""

from datetime import date, datetime, timezone
from math import ceil
from typing import Any

from service.data_service.models import (
    DatasetQuery,
    DatasetSpec,
    DateStorage,
    InvalidQueryError,
    RecordNotFoundError,
)
from service.data_service.registry import DatasetRegistry


class DataService:
    def __init__(self, repository, registry: DatasetRegistry):
        self._repository = repository
        self._registry = registry

    def list_datasets(self) -> list[dict]:
        return [self._dataset_summary(item) for item in self._registry.list()]

    def describe_dataset(self, name: str) -> dict:
        dataset = self._registry.get(name)
        return {
            **self._dataset_summary(dataset),
            "table": dataset.table,
            "read_view": dataset.current_view,
            "primary_keys": list(dataset.primary_keys),
            "storage_semantics": dataset.storage_semantics,
            "business_identity_fields": list(dataset.business_identity_fields),
            "identity_confidence": dataset.identity_confidence,
            "allowed_filters": sorted(dataset.exact_filters),
            "date_column": dataset.date_column,
            "max_page_size": dataset.max_page_size,
            "columns": self._repository.columns(dataset),
        }

    def query_dataset(
        self,
        name: str,
        *,
        exact_filters: dict[str, str],
        date_value: str | None,
        start_date: str | None,
        end_date: str | None,
        limit: int,
        offset: int,
        include_total: bool,
    ) -> dict:
        dataset = self._registry.get(name)
        self._validate_filters(dataset, exact_filters)
        if limit < 1 or limit > dataset.max_page_size:
            raise InvalidQueryError(
                f"limit must be between 1 and {dataset.max_page_size}"
            )
        if offset < 0:
            raise InvalidQueryError("offset must be zero or greater")
        if not dataset.date_column and any((date_value, start_date, end_date)):
            raise InvalidQueryError(f"dataset {name} does not support date filters")

        normalized_date = self._normalize_date(dataset, date_value)
        normalized_start = self._normalize_date(dataset, start_date)
        normalized_end = self._normalize_date(dataset, end_date)
        if normalized_start and normalized_end and normalized_start > normalized_end:
            raise InvalidQueryError("start_date must not be later than end_date")

        query = DatasetQuery(
            exact_filters=exact_filters,
            date=normalized_date,
            start_date=normalized_start,
            end_date=normalized_end,
            limit=limit,
            offset=offset,
            include_total=include_total,
        )
        rows = self._repository.records(dataset, query)
        total = self._repository.count(dataset, query) if include_total else None
        return {
            "data": rows,
            "meta": {
                "dataset": dataset.name,
                "source": dataset.source,
                "returned": len(rows),
            },
            "page": {
                "limit": limit,
                "offset": offset,
                "total": total,
                "has_more": (
                    offset + len(rows) < total
                    if total is not None
                    else len(rows) == limit
                ),
            },
        }

    def freshness(self, name: str | None = None) -> list[dict]:
        datasets = [self._registry.get(name)] if name else self._registry.list()
        return [self._freshness(item) for item in datasets]

    def stock_snapshot(self, ts_code: str) -> dict:
        basic_rows = self._latest_rows("stock_basic", {"ts_code": ts_code}, limit=1)
        if not basic_rows:
            raise RecordNotFoundError(f"stock not found: {ts_code}")

        components = {
            "basic": basic_rows[0],
            "daily": self._first_or_none(
                self._latest_rows("stock_daily", {"ts_code": ts_code})
            ),
            "daily_basic": self._first_or_none(
                self._latest_rows("stock_daily_basic", {"ts_code": ts_code})
            ),
            "moneyflow": self._first_or_none(
                self._latest_rows("moneyflow", {"ts_code": ts_code})
            ),
            "financial_indicator": self._first_or_none(
                self._latest_rows("financial_indicator", {"ts_code": ts_code})
            ),
            "limit": self._first_or_none(
                self._latest_rows("stock_limit", {"ts_code": ts_code})
            ),
            "suspension": self._first_or_none(
                self._latest_rows("stock_suspend", {"ts_code": ts_code})
            ),
        }
        return {
            "data": components,
            "meta": {
                "ts_code": ts_code,
                "generated_at": datetime.now(timezone.utc),
            },
        }

    def _latest_rows(
        self,
        dataset_name: str,
        filters: dict[str, str],
        *,
        limit: int = 1,
    ) -> list[dict]:
        result = self.query_dataset(
            dataset_name,
            exact_filters=filters,
            date_value=None,
            start_date=None,
            end_date=None,
            limit=limit,
            offset=0,
            include_total=False,
        )
        return result["data"]

    def _freshness(self, dataset: DatasetSpec) -> dict:
        latest = self._repository.latest_value(dataset)
        estimated_rows = self._repository.estimated_rows(dataset)
        expected_latest_date = None
        if not dataset.date_column:
            status = "not_applicable"
        elif latest is None:
            status = "empty"
        elif dataset.freshness_policy == "event_driven":
            # Event/disclosure tables do not promise one row per wall-clock
            # interval.  Their latest business date remains observable, while
            # collection-job evidence determines whether polling is healthy.
            status = "event_driven"
        elif dataset.freshness_policy == "quarterly_disclosure":
            latest_date = self._parse_stored_date(dataset, latest)
            expected_latest_date = self._latest_required_report_period(
                datetime.now(timezone.utc).date()
            )
            status = (
                "fresh" if latest_date >= expected_latest_date else "stale"
            )
        elif dataset.freshness_sla_hours is None:
            # A missing SLA is not a zero-hour SLA.  Keep the latest partition
            # visible without claiming that the dataset is stale.
            status = "not_configured"
        else:
            latest_date = self._parse_stored_date(dataset, latest)
            max_age_days = ceil(dataset.freshness_sla_hours / 24)
            age_days = (datetime.now(timezone.utc).date() - latest_date).days
            status = "fresh" if age_days <= max_age_days else "stale"

        return {
            "dataset": dataset.name,
            "latest_date": latest,
            "status": status,
            "freshness_sla_hours": dataset.freshness_sla_hours,
            "freshness_policy": dataset.freshness_policy,
            "expected_latest_date": expected_latest_date,
            "estimated_rows": estimated_rows,
        }

    @staticmethod
    def _latest_required_report_period(as_of: date) -> date:
        candidates: list[tuple[date, date]] = []
        for year in range(as_of.year - 2, as_of.year + 1):
            candidates.extend(
                (
                    (date(year, 3, 31), date(year, 4, 30)),
                    (date(year, 6, 30), date(year, 8, 31)),
                    (date(year, 9, 30), date(year, 10, 31)),
                    (date(year, 12, 31), date(year + 1, 4, 30)),
                )
            )
        return max(period for period, due_date in candidates if due_date <= as_of)

    @staticmethod
    def _dataset_summary(dataset: DatasetSpec) -> dict:
        return {
            "name": dataset.name,
            "description": dataset.description,
            "category": dataset.category,
            "source": dataset.source,
            "date_column": dataset.date_column,
        }

    @staticmethod
    def _validate_filters(
        dataset: DatasetSpec,
        exact_filters: dict[str, str],
    ) -> None:
        unknown = sorted(set(exact_filters) - set(dataset.exact_filters))
        if unknown:
            raise InvalidQueryError(
                f"unsupported filters for {dataset.name}: {', '.join(unknown)}"
            )

    @staticmethod
    def _normalize_date(dataset: DatasetSpec, value: str | None) -> Any:
        if value is None:
            return None
        try:
            parsed = (
                date(int(value[:4]), int(value[4:6]), int(value[6:8]))
                if len(value) == 8 and value.isdigit()
                else date.fromisoformat(value)
            )
        except ValueError as exc:
            raise InvalidQueryError(
                f"invalid date {value!r}; use YYYY-MM-DD or YYYYMMDD"
            ) from exc
        if dataset.date_storage == DateStorage.COMPACT:
            return parsed.strftime("%Y%m%d")
        return parsed

    @staticmethod
    def _parse_stored_date(dataset: DatasetSpec, value: Any) -> date:
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        text = str(value)
        if dataset.date_storage == DateStorage.COMPACT:
            return date(int(text[:4]), int(text[4:6]), int(text[6:8]))
        return date.fromisoformat(text)

    @staticmethod
    def _first_or_none(rows: list[dict]) -> dict | None:
        return rows[0] if rows else None
