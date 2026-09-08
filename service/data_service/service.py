"""Use cases shared by REST and the future MCP adapter."""

from datetime import date, datetime, timedelta, timezone
from html import unescape
from math import ceil
import re
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

    def stock_research_pack(
        self,
        ts_code: str,
        *,
        lookback_days: int = 180,
        benchmark: str = "399006.SZ",
        financial_periods: int = 8,
        as_of: date | None = None,
    ) -> dict:
        """Aggregate governed source records needed by a stock-research Agent.

        This endpoint deliberately does not calculate factors, forecasts, ratings or
        trading advice.  It removes repetitive data-access plumbing while keeping
        derived research in the Agent layer.
        """
        if lookback_days < 30 or lookback_days > 730:
            raise InvalidQueryError("lookback_days must be between 30 and 730")
        if financial_periods < 1 or financial_periods > 12:
            raise InvalidQueryError("financial_periods must be between 1 and 12")

        effective_as_of = as_of or datetime.now(timezone.utc).date()
        start_date = effective_as_of - timedelta(days=lookback_days - 1)
        basic_rows = self._latest_rows("stock_basic", {"ts_code": ts_code}, limit=1)
        if not basic_rows:
            raise RecordNotFoundError(f"stock not found: {ts_code}")

        datasets: dict[str, list[dict]] = {}
        provenance: list[dict] = []

        def load(
            name: str,
            *,
            filters: dict[str, str] | None = None,
            start: date | None = None,
            end: date | None = None,
            limit: int = 100,
        ) -> list[dict]:
            dataset = self._registry.get(name)
            rows = self._rows(
                name,
                filters or {"ts_code": ts_code},
                start_date=start,
                end_date=end,
                limit=limit,
            )
            datasets[name] = rows
            observed_dates = (
                [row[dataset.date_column] for row in rows if row.get(dataset.date_column)]
                if dataset.date_column
                else []
            )
            provenance.append(
                {
                    "dataset": name,
                    "source": dataset.source,
                    "returned": len(rows),
                    "date_column": dataset.date_column,
                    "latest_value_in_pack": max(observed_dates) if observed_dates else None,
                    "earliest_value_in_pack": min(observed_dates) if observed_dates else None,
                }
            )
            return rows

        profile = {
            "basic": basic_rows[0],
            "company": self._first_or_none(load("stock_company", limit=1)),
        }
        market = {
            "daily": load(
                "stock_daily", start=start_date, end=effective_as_of, limit=730
            ),
            "daily_basic": load(
                "stock_daily_basic", start=start_date, end=effective_as_of, limit=730
            ),
            "adjustment_factors": load(
                "adj_factor", start=start_date, end=effective_as_of, limit=730
            ),
            "moneyflow": load(
                "moneyflow", start=start_date, end=effective_as_of, limit=730
            ),
            "cyq_performance": load(
                "cyq_perf", start=start_date, end=effective_as_of, limit=730
            ),
            "margin": load(
                "margin_detail", start=start_date, end=effective_as_of, limit=730
            ),
            "northbound_holding": load(
                "hk_hold", start=start_date, end=effective_as_of, limit=730
            ),
            "block_trades": load(
                "block_trade", start=start_date, end=effective_as_of, limit=200
            ),
            "limits": load(
                "stock_limit", start=start_date, end=effective_as_of, limit=730
            ),
            "suspensions": load(
                "stock_suspend", start=start_date, end=effective_as_of, limit=200
            ),
            "benchmark_daily": load(
                "index_daily",
                filters={"ts_code": benchmark},
                start=start_date,
                end=effective_as_of,
                limit=730,
            ),
        }
        fundamentals = {
            "indicators": load("financial_indicator", limit=financial_periods),
            "income": load("income", limit=financial_periods),
            "balance_sheet": load("balancesheet", limit=financial_periods),
            "cash_flow": load("cashflow", limit=financial_periods),
            "forecasts": load("forecast", limit=financial_periods),
            "express_reports": load("express", limit=financial_periods),
        }
        ownership_and_events = {
            "holder_count": load("stk_holdernumber", limit=financial_periods * 2),
            "holder_trades": load("stk_holdertrade", limit=100),
            "top_holders": load("top10_holders", limit=financial_periods * 10),
            "top_float_holders": load(
                "top10_floatholders", limit=financial_periods * 10
            ),
            "pledge": load("pledge_stat", limit=financial_periods),
            "repurchases": load("repurchase", limit=100),
            "dividends": load("dividend", limit=financial_periods * 2),
        }
        news_dataset = self._registry.get("major_news")
        news_terms = tuple(
            dict.fromkeys(
                value
                for value in (
                    str(profile["basic"].get("name") or "").strip(),
                    str(profile["basic"].get("enname") or "").strip(),
                    ts_code,
                )
                if value
            )
        )
        news_rows = self._repository.search_news(
            news_dataset,
            terms=news_terms,
            start_date=start_date,
            end_date=effective_as_of,
            limit=30,
        )
        related_news = []
        for row in news_rows:
            plain_content = re.sub(r"<[^>]+>", " ", str(row.get("content") or ""))
            related_news.append(
                {
                    **row,
                    "content": re.sub(r"\s+", " ", unescape(plain_content)).strip()[:600],
                }
            )
        ownership_and_events["related_news"] = related_news
        news_dates = [row["pub_time"] for row in related_news if row.get("pub_time")]
        provenance.append(
            {
                "dataset": "major_news",
                "source": news_dataset.source,
                "returned": len(related_news),
                "date_column": "pub_time",
                "latest_value_in_pack": max(news_dates) if news_dates else None,
                "earliest_value_in_pack": min(news_dates) if news_dates else None,
                "search_terms": list(news_terms),
            }
        )
        gaps = [
            {
                "dataset": item["dataset"],
                "reason": "no_rows_in_requested_scope",
            }
            for item in provenance
            if item["returned"] == 0
        ]

        return {
            "data": {
                "profile": profile,
                "market": market,
                "fundamentals": fundamentals,
                "ownership_and_events": ownership_and_events,
            },
            "meta": {
                "ts_code": ts_code,
                "benchmark": benchmark,
                "as_of": effective_as_of,
                "start_date": start_date,
                "lookback_days": lookback_days,
                "financial_periods": financial_periods,
                "generated_at": datetime.now(timezone.utc),
                "provenance": provenance,
                "gaps": gaps,
                "external_data_needed": [
                    {
                        "topic": "official_company_announcements",
                        "reason": (
                            "related_news is a keyword search over media data; "
                            "claw-quant-data currently has no exchange/company "
                            "announcement document search contract"
                        ),
                    }
                ],
            },
        }

    def _latest_rows(
        self,
        dataset_name: str,
        filters: dict[str, str],
        *,
        limit: int = 1,
    ) -> list[dict]:
        return self._rows(
            dataset_name,
            filters,
            start_date=None,
            end_date=None,
            limit=limit,
        )

    def _rows(
        self,
        dataset_name: str,
        filters: dict[str, str],
        *,
        start_date: date | None,
        end_date: date | None,
        limit: int,
    ) -> list[dict]:
        result = self.query_dataset(
            dataset_name,
            exact_filters=filters,
            date_value=None,
            start_date=start_date.isoformat() if start_date else None,
            end_date=end_date.isoformat() if end_date else None,
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
