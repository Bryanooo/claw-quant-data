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


_SECTOR_PROVIDERS = {
    "ths": {
        "catalog": "ths_index",
        "daily": "industry_daily",
        "members": "ths_member",
        "flow": "moneyflow_cnt_ths",
        "category_field": "type",
        "count_field": "count",
    },
    "dc": {
        "catalog": "dc_index",
        "daily": "dc_daily",
        "members": "dc_member",
        "flow": "moneyflow_ind_dc",
        "category_field": "idx_type",
        "count_field": None,
    },
    "tdx": {
        "catalog": "tdx_index",
        "daily": "tdx_daily",
        "members": "tdx_member",
        "flow": None,
        "category_field": "idx_type",
        "count_field": "idx_count",
    },
}

_THS_CATEGORY_NAMES = {
    "N": "概念指数",
    "I": "行业指数",
    "R": "地域指数",
    "S": "特色指数",
    "ST": "风格指数",
    "TH": "主题指数",
    "BB": "宽基指数",
}


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
            "availability_column": dataset.availability_column,
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
        as_of: str | None = None,
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
        if as_of and not dataset.availability_column:
            raise InvalidQueryError(f"dataset {name} does not support as_of filtering")

        normalized_date = self._normalize_date(dataset, date_value)
        normalized_start = self._normalize_date(dataset, start_date)
        normalized_end = self._normalize_date(dataset, end_date)
        normalized_as_of = self._normalize_availability_date(dataset, as_of)
        if normalized_start and normalized_end and normalized_start > normalized_end:
            raise InvalidQueryError("start_date must not be later than end_date")

        query = DatasetQuery(
            exact_filters=exact_filters,
            date=normalized_date,
            start_date=normalized_start,
            end_date=normalized_end,
            as_of=normalized_as_of,
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
        historical_view = effective_as_of < datetime.now(timezone.utc).date()
        start_date = effective_as_of - timedelta(days=lookback_days - 1)
        basic_rows = self._latest_rows("stock_basic", {"ts_code": ts_code}, limit=1)
        if not basic_rows:
            raise RecordNotFoundError(f"stock not found: {ts_code}")

        datasets: dict[str, list[dict]] = {}
        provenance: list[dict] = [
            {
                "dataset": "stock_basic",
                "source": self._registry.get("stock_basic").source,
                "returned": 1,
                "date_column": None,
                "latest_value_in_pack": None,
                "earliest_value_in_pack": None,
                "availability_column": None,
                "point_in_time_status": (
                    "current_only" if historical_view else "not_applicable"
                ),
                "data_state": "available",
            }
        ]

        def load(
            name: str,
            *,
            filters: dict[str, str] | None = None,
            start: date | None = None,
            end: date | None = None,
            limit: int = 100,
            point_in_time: bool = False,
            required: bool = False,
        ) -> list[dict]:
            dataset = self._registry.get(name)
            availability_cutoff = (
                effective_as_of
                if point_in_time and dataset.availability_column
                else None
            )
            rows = self._rows(
                name,
                filters or {"ts_code": ts_code},
                start_date=start,
                end_date=end,
                limit=limit,
                as_of=availability_cutoff,
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
                    "availability_column": dataset.availability_column,
                    "point_in_time_status": (
                        "enforced"
                        if availability_cutoff
                        else "current_only"
                        if point_in_time
                        else "bounded_by_observation_date"
                        if end is not None
                        else "not_applicable"
                    ),
                    "data_state": (
                        "available"
                        if rows
                        else "missing"
                        if required
                        else "unknown_empty"
                    ),
                }
            )
            return rows

        profile = {
            "basic": basic_rows[0],
            "company": self._first_or_none(
                load("stock_company", limit=1, point_in_time=historical_view)
            ),
        }
        market = {
            "daily": load(
                "stock_daily", start=start_date, end=effective_as_of,
                limit=730, required=True
            ),
            "daily_basic": load(
                "stock_daily_basic", start=start_date, end=effective_as_of,
                limit=730, required=True
            ),
            "adjustment_factors": load(
                "adj_factor", start=start_date, end=effective_as_of,
                limit=730, required=True
            ),
            "moneyflow": load(
                "moneyflow", start=start_date, end=effective_as_of,
                limit=730, required=True
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
                "stock_limit", start=start_date, end=effective_as_of,
                limit=730, required=True
            ),
            "suspensions": load(
                "stock_suspend", start=start_date, end=effective_as_of, limit=200
            ),
            "benchmark_daily": load(
                "index_daily",
                filters={"ts_code": benchmark},
                start=start_date,
                end=effective_as_of,
                limit=730, required=True,
            ),
        }
        fundamentals = {
            "indicators": load(
                "financial_indicator", end=effective_as_of,
                limit=financial_periods, point_in_time=True, required=True
            ),
            "income": load(
                "income", end=effective_as_of,
                limit=financial_periods, point_in_time=True, required=True
            ),
            "balance_sheet": load(
                "balancesheet", end=effective_as_of,
                limit=financial_periods, point_in_time=True, required=True
            ),
            "cash_flow": load(
                "cashflow", end=effective_as_of,
                limit=financial_periods, point_in_time=True, required=True
            ),
            "forecasts": load(
                "forecast", end=effective_as_of,
                limit=financial_periods, point_in_time=True
            ),
            "express_reports": load(
                "express", end=effective_as_of,
                limit=financial_periods, point_in_time=True
            ),
        }
        ownership_and_events = {
            "holder_count": load(
                "stk_holdernumber", end=effective_as_of,
                limit=financial_periods * 2, point_in_time=True
            ),
            "holder_trades": load(
                "stk_holdertrade", end=effective_as_of,
                limit=100, point_in_time=True
            ),
            "top_holders": load(
                "top10_holders", end=effective_as_of,
                limit=financial_periods * 10, point_in_time=True
            ),
            "top_float_holders": load(
                "top10_floatholders", end=effective_as_of,
                limit=financial_periods * 10, point_in_time=True
            ),
            "pledge": load(
                "pledge_stat", end=effective_as_of,
                limit=financial_periods, point_in_time=True
            ),
            "repurchases": load(
                "repurchase", end=effective_as_of,
                limit=100, point_in_time=True
            ),
            "dividends": load(
                "dividend", end=effective_as_of,
                limit=financial_periods * 2, point_in_time=True
            ),
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
                "availability_column": "pub_time",
                "point_in_time_status": "enforced",
                "data_state": "available" if related_news else "unknown_empty",
            }
        )
        gaps = [
            {
                "dataset": item["dataset"],
                "reason": item["data_state"],
            }
            for item in provenance
            if item["data_state"] == "missing"
        ]
        unknown_empty = [
            {
                "dataset": item["dataset"],
                "reason": "no rows; absence of an event is not proven",
            }
            for item in provenance
            if item["data_state"] == "unknown_empty"
        ]
        point_in_time_warnings = [
            item["dataset"]
            for item in provenance
            if item["point_in_time_status"] == "current_only"
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
                "unknown_empty": unknown_empty,
                "quality": {
                    "status": (
                        "warning"
                        if gaps or unknown_empty or point_in_time_warnings
                        else "ready"
                    ),
                    "point_in_time_safe": not point_in_time_warnings,
                    "point_in_time_warnings": point_in_time_warnings,
                    "missing_datasets": [item["dataset"] for item in gaps],
                    "unknown_empty_datasets": [
                        item["dataset"] for item in unknown_empty
                    ],
                },
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

    def list_sectors(
        self,
        *,
        provider: str | None = None,
        query: str | None = None,
        category: str | None = None,
        market: str | None = None,
        as_of: date | None = None,
        limit: int = 100,
    ) -> dict:
        """Return one normalized sector universe across supported vendors."""
        providers = self._sector_providers(provider)
        effective_as_of = as_of or datetime.now(timezone.utc).date()
        needle = (query or "").strip().casefold()
        category_needle = (category or "").strip().casefold()
        market_needle = (market or "").strip().casefold()
        sectors: list[dict] = []
        for provider_name in providers:
            spec = _SECTOR_PROVIDERS[provider_name]
            rows = self._sector_catalog_rows(provider_name, effective_as_of)
            for row in rows:
                normalized = self._normalize_sector(provider_name, row, spec)
                searchable = f"{normalized['sector_code']} {normalized['name']}".casefold()
                if needle and needle not in searchable:
                    continue
                if category_needle and category_needle not in str(
                    normalized.get("category") or ""
                ).casefold():
                    continue
                if market_needle and market_needle != str(
                    normalized.get("market") or ""
                ).casefold():
                    continue
                sectors.append(normalized)
        sectors.sort(key=lambda item: (item["provider"], item["sector_code"]))
        total = len(sectors)
        return {
            "data": sectors[:limit],
            "meta": {
                "as_of": effective_as_of,
                "providers": providers,
                "query": query,
                "category": category,
                "market": market,
                "returned": min(total, limit),
                "matched": total,
                "generated_at": datetime.now(timezone.utc),
            },
        }

    def stock_sectors(
        self,
        ts_code: str,
        *,
        provider: str | None = None,
        as_of: date | None = None,
    ) -> dict:
        """Resolve vendor sector memberships for one stock at a point in time."""
        effective_as_of = as_of or datetime.now(timezone.utc).date()
        memberships: list[dict] = []
        unresolved_catalogs: list[dict] = []
        for provider_name in self._sector_providers(provider):
            rows, membership_date = self._stock_membership_rows(
                provider_name, ts_code, effective_as_of
            )
            for row in rows:
                sector_code = row.get("ts_code")
                if not sector_code:
                    continue
                try:
                    profile = self._sector_profile(
                        provider_name, sector_code, effective_as_of
                    )
                except RecordNotFoundError:
                    profile = {
                        "provider": provider_name,
                        "sector_code": sector_code,
                        "name": None,
                        "category": None,
                        "market": None,
                        "constituent_count": None,
                        "trade_date": membership_date,
                    }
                    unresolved_catalogs.append(
                        {"provider": provider_name, "sector_code": sector_code}
                    )
                memberships.append(
                    {
                        **profile,
                        "membership_effective_date": membership_date,
                        "weight": row.get("weight"),
                        "in_date": row.get("in_date"),
                        "out_date": row.get("out_date"),
                    }
                )
        memberships.sort(key=lambda item: (item["provider"], item["sector_code"]))
        return {
            "data": memberships,
            "meta": {
                "ts_code": ts_code,
                "as_of": effective_as_of,
                "returned": len(memberships),
                "quality": {
                    "status": "warning" if unresolved_catalogs else "ready",
                    "unresolved_catalogs": unresolved_catalogs,
                },
                "generated_at": datetime.now(timezone.utc),
            },
        }

    def stock_peers(
        self,
        ts_code: str,
        *,
        provider: str | None = None,
        as_of: date | None = None,
        max_sectors: int = 5,
        limit: int = 50,
    ) -> dict:
        """Rank peers by the number of point-in-time sector memberships shared."""
        if max_sectors < 1 or max_sectors > 10:
            raise InvalidQueryError("max_sectors must be between 1 and 10")
        if limit < 1 or limit > 200:
            raise InvalidQueryError("limit must be between 1 and 200")
        effective_as_of = as_of or datetime.now(timezone.utc).date()
        memberships = self.stock_sectors(
            ts_code, provider=provider, as_of=effective_as_of
        )["data"]
        category_priority = {
            "行业指数": 0,
            "概念指数": 1,
            "主题指数": 2,
            "地域指数": 3,
            "特色指数": 4,
            "风格指数": 5,
            "宽基指数": 9,
        }
        memberships = [
            item
            for item in memberships
            if item.get("category") != "宽基指数"
            and (item.get("market") in {None, "A"})
        ]
        memberships.sort(
            key=lambda item: (
                category_priority.get(item.get("category"), 6),
                item.get("constituent_count") or 999999,
                item["sector_code"],
            )
        )
        memberships = memberships[:max_sectors]
        peers: dict[str, dict] = {}
        selected_sectors: list[dict] = []
        for sector in memberships:
            members, membership_date, member_count = self._sector_member_rows(
                sector["provider"], sector["sector_code"], effective_as_of, 2000
            )
            selected_sectors.append(
                {
                    "provider": sector["provider"],
                    "sector_code": sector["sector_code"],
                    "name": sector.get("name"),
                    "category": sector.get("category"),
                    "market": sector.get("market"),
                    "membership_effective_date": membership_date,
                    "member_count": member_count,
                    "truncated": len(members) < member_count,
                }
            )
            for member in members:
                peer_code = member["ts_code"]
                if peer_code == ts_code:
                    continue
                peer = peers.setdefault(
                    peer_code,
                    {"ts_code": peer_code, "name": member.get("name"), "shared_sectors": []},
                )
                peer["shared_sectors"].append(
                    {
                        "provider": sector["provider"],
                        "sector_code": sector["sector_code"],
                        "name": sector.get("name"),
                    }
                )
        ranked = [
            {**peer, "shared_sector_count": len(peer["shared_sectors"])}
            for peer in peers.values()
        ]
        ranked.sort(key=lambda item: (-item["shared_sector_count"], item["ts_code"]))
        truncated = any(item["truncated"] for item in selected_sectors)
        return {
            "data": ranked[:limit],
            "meta": {
                "ts_code": ts_code,
                "as_of": effective_as_of,
                "selected_sectors": selected_sectors,
                "matched": len(ranked),
                "returned": min(len(ranked), limit),
                "quality": {
                    "status": "warning" if truncated else "ready",
                    "member_source_truncated": truncated,
                },
                "generated_at": datetime.now(timezone.utc),
            },
        }

    def sector_snapshot(
        self,
        provider: str,
        sector_code: str,
        *,
        as_of: date | None = None,
    ) -> dict:
        effective_as_of = as_of or datetime.now(timezone.utc).date()
        bundle = self._sector_bundle(
            provider, sector_code, effective_as_of, lookback_days=30,
            member_limit=20,
        )
        return {
            "data": {
                "profile": bundle["profile"],
                "latest": bundle["latest"],
                "membership": {
                    "effective_date": bundle["membership_date"],
                    "count": bundle["member_count"],
                    "sample": bundle["members"],
                },
            },
            "meta": bundle["meta"],
        }

    def sector_members(
        self,
        provider: str,
        sector_code: str,
        *,
        as_of: date | None = None,
        limit: int = 500,
    ) -> dict:
        effective_as_of = as_of or datetime.now(timezone.utc).date()
        provider_name = self._sector_providers(provider)[0]
        profile = self._sector_profile(provider_name, sector_code, effective_as_of)
        members, membership_date, member_count = self._sector_member_rows(
            provider_name, sector_code, effective_as_of, limit
        )
        return {
            "data": members,
            "meta": {
                "provider": provider_name,
                "sector_code": sector_code,
                "sector_name": profile["name"],
                "as_of": effective_as_of,
                "membership_effective_date": membership_date,
                "returned": len(members),
                "total": member_count,
                "has_more": len(members) < member_count,
                "generated_at": datetime.now(timezone.utc),
            },
        }

    def sector_research_pack(
        self,
        provider: str,
        sector_code: str,
        *,
        lookback_days: int = 180,
        member_limit: int = 500,
        as_of: date | None = None,
    ) -> dict:
        if lookback_days < 30 or lookback_days > 730:
            raise InvalidQueryError("lookback_days must be between 30 and 730")
        if member_limit < 1 or member_limit > 2000:
            raise InvalidQueryError("member_limit must be between 1 and 2000")
        effective_as_of = as_of or datetime.now(timezone.utc).date()
        bundle = self._sector_bundle(
            provider, sector_code, effective_as_of,
            lookback_days=lookback_days, member_limit=member_limit,
        )
        return {
            "data": {
                "profile": bundle["profile"],
                "latest": bundle["latest"],
                "daily": bundle["daily"],
                "members": bundle["members"],
                "capital_flow": bundle["flow"],
            },
            "meta": bundle["meta"],
        }

    def _sector_bundle(
        self,
        provider: str,
        sector_code: str,
        as_of: date,
        *,
        lookback_days: int,
        member_limit: int,
    ) -> dict:
        provider_name = self._sector_providers(provider)[0]
        spec = _SECTOR_PROVIDERS[provider_name]
        normalized_code = sector_code.upper()
        profile = self._sector_profile(provider_name, normalized_code, as_of)
        start_date = as_of - timedelta(days=lookback_days - 1)
        daily = self._rows(
            spec["daily"], {"ts_code": normalized_code},
            start_date=start_date, end_date=as_of, limit=730,
        )
        members, membership_date, member_count = self._sector_member_rows(
            provider_name, normalized_code, as_of, member_limit
        )
        flow = (
            self._rows(
                spec["flow"], {"ts_code": normalized_code},
                start_date=start_date, end_date=as_of, limit=730,
            )
            if spec["flow"]
            else []
        )
        essential_gaps = []
        if not daily:
            essential_gaps.append("daily")
        if not members:
            essential_gaps.append("members")
        observed_start = self._observed_date(daily[-1] if daily else None, "trade_date")
        observed_end = self._observed_date(daily[0] if daily else None, "trade_date")
        flow_state = "not_supported" if not spec["flow"] else (
            "available" if flow else "unknown_empty"
        )
        meta = {
            "provider": provider_name,
            "sector_code": normalized_code,
            "as_of": as_of,
            "start_date": start_date,
            "lookback_days": lookback_days,
            "membership_effective_date": membership_date,
            "member_count": member_count,
            "generated_at": datetime.now(timezone.utc),
            "provenance": [
                {"dataset": spec["catalog"], "source": "Tushare Pro", "returned": 1},
                {
                    "dataset": spec["daily"], "source": "Tushare Pro",
                    "returned": len(daily), "earliest_value_in_pack": observed_start,
                    "latest_value_in_pack": observed_end,
                },
                {
                    "dataset": spec["members"], "source": "Tushare Pro",
                    "returned": len(members), "effective_date": membership_date,
                },
                *(
                    [{"dataset": spec["flow"], "source": "Tushare Pro", "returned": len(flow)}]
                    if spec["flow"] else []
                ),
            ],
            "quality": {
                "status": "warning" if essential_gaps else "ready",
                "essential_gaps": essential_gaps,
                "daily_observed_start": observed_start,
                "daily_observed_end": observed_end,
                "capital_flow_state": flow_state,
                "member_result_truncated": len(members) < member_count,
            },
        }
        return {
            "profile": profile,
            "latest": daily[0] if daily else None,
            "daily": daily,
            "members": members,
            "member_count": member_count,
            "membership_date": membership_date,
            "flow": flow,
            "meta": meta,
        }

    def _sector_profile(self, provider: str, sector_code: str, as_of: date) -> dict:
        spec = _SECTOR_PROVIDERS[provider]
        rows = self._rows(
            spec["catalog"], {"ts_code": sector_code},
            start_date=None,
            end_date=as_of if self._registry.get(spec["catalog"]).date_column else None,
            limit=1,
        )
        if not rows:
            raise RecordNotFoundError(f"sector not found: {provider}/{sector_code}")
        return self._normalize_sector(provider, rows[0], spec)

    def _sector_catalog_rows(self, provider: str, as_of: date) -> list[dict]:
        dataset_name = _SECTOR_PROVIDERS[provider]["catalog"]
        dataset = self._registry.get(dataset_name)
        if dataset.date_column:
            latest = self._rows(
                dataset_name, {}, start_date=None, end_date=as_of, limit=1
            )
            if not latest:
                return []
            return self.query_dataset(
                dataset_name, exact_filters={},
                date_value=str(latest[0][dataset.date_column]),
                start_date=None, end_date=None, limit=1000, offset=0,
                include_total=False,
            )["data"]
        rows: list[dict] = []
        offset = 0
        while len(rows) < 5000:
            page = self.query_dataset(
                dataset_name, exact_filters={}, date_value=None,
                start_date=None, end_date=None, limit=1000, offset=offset,
                include_total=False,
            )
            rows.extend(page["data"])
            if not page["page"]["has_more"]:
                break
            offset += 1000
        return rows

    def _sector_member_rows(
        self,
        provider: str,
        sector_code: str,
        as_of: date,
        limit: int,
    ) -> tuple[list[dict], Any, int]:
        dataset_name = _SECTOR_PROVIDERS[provider]["members"]
        dataset = self._registry.get(dataset_name)
        rows: list[dict] = []
        effective_date = None
        offset = 0
        while offset < 6000:
            page = self.query_dataset(
                dataset_name,
                exact_filters={"ts_code": sector_code},
                date_value=None,
                start_date=None,
                end_date=as_of.isoformat() if dataset.date_column else None,
                limit=1000,
                offset=offset,
                include_total=False,
            )
            page_rows = page["data"]
            if dataset.date_column and page_rows:
                if effective_date is None:
                    effective_date = page_rows[0].get(dataset.date_column)
                rows.extend(
                    row for row in page_rows
                    if row.get(dataset.date_column) == effective_date
                )
                if page_rows[-1].get(dataset.date_column) != effective_date:
                    break
            else:
                rows.extend(page_rows)
            if not page["page"]["has_more"]:
                break
            offset += 1000
        if provider == "ths":
            rows = [row for row in rows if self._membership_active(row, as_of)]
            effective_date = as_of
        normalized = [
            {
                "ts_code": row.get("con_code"),
                "name": row.get("con_name") or row.get("name"),
                "weight": row.get("weight"),
                "in_date": row.get("in_date"),
                "out_date": row.get("out_date"),
            }
            for row in rows
            if row.get("con_code")
        ]
        total = len(normalized)
        return normalized[:limit], effective_date, total

    def _stock_membership_rows(
        self, provider: str, ts_code: str, as_of: date
    ) -> tuple[list[dict], Any]:
        dataset_name = _SECTOR_PROVIDERS[provider]["members"]
        dataset = self._registry.get(dataset_name)
        rows: list[dict] = []
        offset = 0
        effective_date = None
        while offset < 5000:
            page = self.query_dataset(
                dataset_name,
                exact_filters={"con_code": ts_code},
                date_value=None,
                start_date=None,
                end_date=as_of.isoformat() if dataset.date_column else None,
                limit=1000,
                offset=offset,
                include_total=False,
            )
            page_rows = page["data"]
            if dataset.date_column and page_rows:
                if effective_date is None:
                    effective_date = page_rows[0].get(dataset.date_column)
                rows.extend(
                    row for row in page_rows
                    if row.get(dataset.date_column) == effective_date
                )
                if page_rows[-1].get(dataset.date_column) != effective_date:
                    break
            else:
                rows.extend(page_rows)
            if not page["page"]["has_more"]:
                break
            offset += 1000
        if provider == "ths":
            rows = [row for row in rows if self._membership_active(row, as_of)]
            effective_date = as_of
        return rows, effective_date

    @staticmethod
    def _membership_active(row: dict, as_of: date) -> bool:
        def parse(value: Any) -> date | None:
            if not value:
                return None
            text = str(value)[:10].replace("-", "")
            try:
                return date(int(text[:4]), int(text[4:6]), int(text[6:8]))
            except (ValueError, TypeError):
                return None

        in_date = parse(row.get("in_date"))
        out_date = parse(row.get("out_date"))
        return (in_date is None or in_date <= as_of) and (
            out_date is None or out_date > as_of
        )

    @staticmethod
    def _normalize_sector(provider: str, row: dict, spec: dict) -> dict:
        count_field = spec["count_field"]
        raw_category = row.get(spec["category_field"])
        return {
            "provider": provider,
            "sector_code": row.get("ts_code"),
            "name": row.get("name"),
            "category": (
                _THS_CATEGORY_NAMES.get(raw_category, raw_category)
                if provider == "ths"
                else raw_category
            ),
            "market": row.get("exchange"),
            "constituent_count": row.get(count_field) if count_field else None,
            "trade_date": row.get("trade_date"),
        }

    @staticmethod
    def _sector_providers(provider: str | None) -> list[str]:
        if provider is None:
            return list(_SECTOR_PROVIDERS)
        normalized = provider.lower()
        if normalized not in _SECTOR_PROVIDERS:
            raise InvalidQueryError(
                f"unsupported sector provider: {provider}; use ths, dc or tdx"
            )
        return [normalized]

    @staticmethod
    def _observed_date(row: dict | None, field: str) -> Any:
        return row.get(field) if row else None

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
        as_of: date | None = None,
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
            as_of=as_of.isoformat() if as_of else None,
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
    def _normalize_availability_date(dataset: DatasetSpec, value: str | None) -> Any:
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
                f"invalid as_of {value!r}; use YYYY-MM-DD or YYYYMMDD"
            ) from exc
        if dataset.availability_storage == DateStorage.COMPACT:
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
