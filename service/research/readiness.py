"""Research capability lineage and strict data-readiness evaluation.

Task execution and data readiness are deliberately different dimensions.  A
successful V2 execution is useful transport evidence, but it does not prove
that every expected historical partition exists or that the latest published
partition is fresh.  This module is the machine-readable contract connecting
research outputs to their source datasets and evaluates only data evidence.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any


def _dependency(
    dataset: str,
    role: str,
    *,
    required: bool = True,
    history_days: int | None = None,
    full_history_start: str | None = None,
) -> dict[str, Any]:
    if history_days is not None and full_history_start is not None:
        raise ValueError("a dependency cannot declare two history scopes")
    return {
        "dataset": dataset,
        "role": role,
        "required": required,
        "history_days": history_days,
        "full_history_start": full_history_start,
    }


# One row represents a stable research resource, not one calculation hidden
# inside it.  Techniques in ``catalog.py`` reference these endpoint ids.  The
# dependency list is intentionally explicit so CI can reject a new research
# resource that has no data lineage or acceptance scope.
RESEARCH_DATA_CONTRACTS: tuple[dict[str, Any], ...] = (
    {
        "id": "fundamentals",
        "path": "/api/v1/research/stocks/{ts_code}/fundamentals",
        "domain": "stock_fundamental",
        "dependencies": (
            _dependency("stock_basic", "security identity"),
            _dependency("financial_indicator", "profitability and ratios", history_days=1825),
            _dependency("income", "revenue and earnings", history_days=1825),
            _dependency("balancesheet", "assets, liabilities and equity", history_days=1825),
            _dependency("cashflow", "cash conversion and free cash flow", history_days=1825),
            _dependency("fina_mainbz", "business-segment composition", required=False, history_days=1825),
        ),
    },
    {
        "id": "valuation",
        "path": "/api/v1/research/stocks/{ts_code}/valuation",
        "domain": "stock_fundamental",
        "dependencies": (
            _dependency("stock_basic", "security identity"),
            _dependency("stock_daily_basic", "valuation history", history_days=730),
            _dependency("financial_indicator", "intrinsic-value inputs", history_days=730),
            _dependency("ths_member", "peer membership", required=False),
            _dependency("dc_member", "peer membership", required=False),
        ),
    },
    {
        "id": "technicals",
        "path": "/api/v1/research/stocks/{ts_code}/technicals",
        "domain": "stock_technical",
        "dependencies": (
            _dependency("stock_basic", "security identity"),
            _dependency("stock_daily", "OHLCV and returns", history_days=1825),
            _dependency("adj_factor", "corporate-action adjustment", history_days=1825),
            _dependency("stock_daily_basic", "turnover and market value", history_days=1825),
            _dependency("index_daily", "benchmark and relative risk", history_days=1825),
        ),
    },
    {
        "id": "instrument-technicals-index",
        "path": "/api/v1/research/instruments/index/{code}/technicals",
        "domain": "cross_asset_technical",
        "dependencies": (
            _dependency("index_basic", "instrument identity"),
            _dependency("index_daily", "index OHLCV", history_days=1825),
        ),
    },
    {
        "id": "instrument-technicals-etf",
        "path": "/api/v1/research/instruments/etf/{code}/technicals",
        "domain": "cross_asset_technical",
        "dependencies": (
            _dependency("fund_basic", "fund identity"),
            _dependency("fund_daily", "ETF OHLCV", history_days=1825),
            _dependency("fund_adj", "ETF adjustment", history_days=1825),
            _dependency("index_daily", "benchmark and tracked-index return", history_days=1825),
        ),
    },
    {
        "id": "instrument-technicals-sector",
        "path": "/api/v1/research/instruments/sector/{code}/technicals",
        "domain": "cross_asset_technical",
        "dependencies": (
            _dependency("industry_daily", "THS sector OHLCV", required=False, history_days=1095),
            _dependency("dc_daily", "Eastmoney sector OHLCV", required=False, history_days=1095),
            _dependency("tdx_daily", "Tongdaxin sector OHLCV", required=False, history_days=1095),
        ),
        "minimum_optional_ready": 1,
    },
    {
        "id": "instrument-technicals-spot",
        "path": "/api/v1/research/instruments/spot/{code}/technicals",
        "domain": "cross_asset_technical",
        "dependencies": (
            _dependency("sge_basic", "spot instrument identity"),
            _dependency("sge_daily", "spot OHLCV", history_days=1825),
        ),
    },
    {
        "id": "capital-flow",
        "path": "/api/v1/research/stocks/{ts_code}/capital-flow",
        "domain": "stock_flow",
        "dependencies": (
            _dependency("moneyflow", "main-fund flow", history_days=365),
            _dependency("margin_detail", "margin financing", required=False, history_days=365),
            _dependency("hk_hold", "northbound holdings", required=False, history_days=365),
            _dependency("block_trade", "block trades", required=False, history_days=365),
            _dependency("cyq_perf", "chip distribution", required=False, history_days=365),
        ),
    },
    {
        "id": "repurchase-progress",
        "path": "/api/v1/research/stocks/{ts_code}/repurchase-progress",
        "domain": "shareholder_return",
        "dependencies": (
            _dependency("repurchase", "repurchase plan and execution", full_history_start="2015-01-01"),
            _dependency("stock_daily", "issuer market reaction", history_days=1825),
            _dependency("index_daily", "benchmark market reaction", history_days=1825),
        ),
    },
    {
        "id": "event-study",
        "path": "/api/v1/research/stocks/{ts_code}/event-study",
        "domain": "event_research",
        "dependencies": (
            _dependency("stock_daily", "issuer event-window returns", history_days=365),
            _dependency("index_daily", "benchmark event-window returns", history_days=365),
        ),
    },
    {
        "id": "market-breadth",
        "path": "/api/v1/research/market/breadth",
        "domain": "market_research",
        "dependencies": (
            _dependency("stock_daily", "market cross-section", history_days=120),
            _dependency("limit_list_d", "limit-up/down breadth", required=False, history_days=120),
        ),
    },
    {
        "id": "macro-regime",
        "path": "/api/v1/research/macro/regime",
        "domain": "macro_research",
        "dependencies": (
            _dependency("cn_gdp", "growth regime", history_days=3650),
            _dependency("cn_pmi", "business cycle", history_days=3650),
            _dependency("cn_cpi", "consumer inflation", history_days=3650),
            _dependency("cn_ppi", "producer inflation", history_days=3650),
            _dependency("cn_m", "money supply", history_days=3650),
            _dependency("sf_month", "social financing", history_days=3650),
            _dependency("shibor", "money-market rates", history_days=1095),
            _dependency("cn_lpr", "loan prime rate", history_days=3650),
        ),
    },
    {
        "id": "etf-flows",
        "path": "/api/v1/research/etfs/flows",
        "domain": "etf_research",
        "dependencies": (
            _dependency("etf_share_size", "share creation/redemption", full_history_start="2009-01-05"),
            _dependency("etf_basic", "tracked exposure identity"),
            _dependency("fund_basic", "fund classification"),
            _dependency("index_daily", "tracked-index performance", history_days=1825),
        ),
    },
    {
        "id": "state-team-signals",
        "path": "/api/v1/research/etfs/state-team-signals",
        "domain": "etf_research",
        "dependencies": (
            _dependency("etf_share_size", "market-flow evidence", full_history_start="2009-01-05"),
            _dependency("etf_basic", "tracked exposure identity"),
            _dependency("fund_basic", "fund classification"),
            _dependency("index_daily", "counter-cyclical market context", history_days=1825),
        ),
    },
    {
        "id": "sector-rotation",
        "path": "/api/v1/research/sectors/{provider}/rotation",
        "domain": "industry_research",
        "dependencies": (
            _dependency("industry_daily", "THS sector return", required=False, history_days=365),
            _dependency("dc_daily", "Eastmoney sector return", required=False, history_days=365),
            _dependency("tdx_daily", "Tongdaxin sector return", required=False, history_days=365),
        ),
        "minimum_optional_ready": 1,
    },
    {
        "id": "industry-fundamentals",
        "path": "/api/v1/research/sectors/{provider}/{sector_code}/fundamentals",
        "domain": "industry_research",
        "dependencies": (
            _dependency("income", "member revenue and earnings", history_days=1825),
            _dependency("cashflow", "member cash generation", history_days=1825),
            _dependency("financial_indicator", "member quality metrics", history_days=1825),
            _dependency("stock_daily_basic", "member valuation", history_days=730),
            _dependency("ths_member", "THS point-in-time membership", required=False),
            _dependency("dc_member", "Eastmoney point-in-time membership", required=False),
            _dependency("tdx_member", "Tongdaxin point-in-time membership", required=False),
        ),
        "minimum_optional_ready": 1,
    },
    {
        "id": "industry-breadth",
        "path": "/api/v1/research/sectors/{provider}/{sector_code}/breadth",
        "domain": "industry_research",
        "dependencies": (
            _dependency("stock_daily", "member market breadth", history_days=120),
            _dependency("ths_member", "THS point-in-time membership", required=False),
            _dependency("dc_member", "Eastmoney point-in-time membership", required=False),
            _dependency("tdx_member", "Tongdaxin point-in-time membership", required=False),
        ),
        "minimum_optional_ready": 1,
    },
)


_READY_FRESHNESS = {"fresh", "event_driven", "not_applicable"}
_STRICT_HISTORY = {"complete", "empty"}


def _required_start(dependency: dict[str, Any], as_of: date) -> date | None:
    if dependency.get("full_history_start"):
        return date.fromisoformat(dependency["full_history_start"])
    if dependency.get("history_days"):
        return as_of - timedelta(days=int(dependency["history_days"]) - 1)
    return None


def evaluate_research_readiness(
    *,
    coverage: dict[str, Any],
    freshness: list[dict[str, Any]],
    as_of: date,
) -> dict[str, Any]:
    """Evaluate research readiness exclusively from persisted data evidence."""

    coverage_by_name = {
        item["dataset"]: item for item in coverage.get("datasets", [])
    }
    freshness_by_name = {item["dataset"]: item for item in freshness}
    dataset_states: dict[tuple[str, date | None], dict[str, Any]] = {}

    def evaluate_dependency(dependency: dict[str, Any]) -> dict[str, Any]:
        dataset = dependency["dataset"]
        required_start = _required_start(dependency, as_of)
        cache_key = (dataset, required_start)
        if cache_key in dataset_states:
            return {**dataset_states[cache_key], **dependency}

        coverage_item = coverage_by_name.get(dataset)
        freshness_item = freshness_by_name.get(dataset)
        latest = (coverage_item or {}).get("latest") or {}
        availability_start = (latest.get("evidence") or {}).get(
            "availability_start"
        )
        if isinstance(availability_start, str):
            availability_start = date.fromisoformat(availability_start)
        effective_required_start = (
            max(required_start, availability_start)
            if required_start is not None and availability_start is not None
            else required_start
        )
        rows = int((freshness_item or {}).get("estimated_rows") or 0)
        freshness_status = (freshness_item or {}).get("status") or "unknown"
        freshness_ready = freshness_status in _READY_FRESHNESS and rows > 0

        if required_start is None:
            history_status = "not_applicable"
            history_ready = True
        elif coverage_item is None:
            history_status = "unclassified"
            history_ready = False
        elif not coverage_item.get("auditable"):
            history_status = "not_auditable"
            history_ready = False
        elif not latest:
            history_status = "unaudited"
            history_ready = False
        elif latest.get("status") == "gaps":
            history_status = "gaps"
            history_ready = False
        elif latest.get("status") == "unverified":
            history_status = "unverified"
            history_ready = False
        elif latest.get("status") == "observed_only":
            history_status = "observed_only"
            history_ready = False
        elif latest.get("status") in _STRICT_HISTORY:
            audited_start = (
                latest.get("verified_start_date") or latest.get("start_date")
            )
            audited_end = (
                latest.get("verified_end_date") or latest.get("end_date")
            )
            if isinstance(audited_start, str):
                audited_start = date.fromisoformat(audited_start)
            if isinstance(audited_end, str):
                audited_end = date.fromisoformat(audited_end)
            latest_date = (freshness_item or {}).get("latest_date")
            if isinstance(latest_date, str):
                try:
                    latest_date = date.fromisoformat(latest_date)
                except ValueError:
                    latest_date = None
            if (
                not audited_start
                or audited_start > effective_required_start
            ):
                history_status = "range_insufficient"
                history_ready = False
            elif latest_date and (
                not audited_end or audited_end < latest_date
            ):
                history_status = "audit_behind_latest_data"
                history_ready = False
            else:
                history_status = (
                    "verified_empty"
                    if latest.get("status") == "empty"
                    else "strictly_verified"
                )
                history_ready = True
        else:
            history_status = str(latest.get("status") or "unknown")
            history_ready = False

        if not rows:
            state = "missing"
        elif not freshness_ready:
            state = "stale" if freshness_status == "stale" else "unknown"
        elif not history_ready:
            state = "unverified"
        else:
            state = "ready"
        value = {
            "dataset": dataset,
            "state": state,
            "rows_present": rows > 0,
            "estimated_rows": rows,
            "freshness_status": freshness_status,
            "latest_date": (freshness_item or {}).get("latest_date"),
            "history_status": history_status,
            "required_history_start": required_start,
            "provider_availability_start": availability_start,
            "effective_required_history_start": effective_required_start,
            "audited_start": (
                latest.get("verified_start_date") or latest.get("start_date")
            ),
            "audited_end": (
                latest.get("verified_end_date") or latest.get("end_date")
            ),
            "missing_partitions": int(latest.get("missing_partitions") or 0),
            "partial_partitions": int(latest.get("partial_partitions") or 0),
        }
        dataset_states[cache_key] = value
        return {**value, **dependency}

    capabilities: list[dict[str, Any]] = []
    for contract in RESEARCH_DATA_CONTRACTS:
        dependencies = [
            evaluate_dependency(item) for item in contract["dependencies"]
        ]
        required = [item for item in dependencies if item["required"]]
        optional = [item for item in dependencies if not item["required"]]
        optional_ready = sum(item["state"] == "ready" for item in optional)
        minimum_optional = int(contract.get("minimum_optional_ready") or 0)
        unavailable = [
            item for item in required if item["state"] in {"missing", "stale"}
        ]
        unverified = [item for item in required if item["state"] == "unverified"]
        if unavailable:
            status = "unavailable"
        elif unverified or optional_ready < minimum_optional:
            status = "degraded"
        else:
            status = "ready"
        capabilities.append(
            {
                "id": contract["id"],
                "path": contract["path"],
                "domain": contract["domain"],
                "status": status,
                "required_datasets": len(required),
                "required_ready": sum(item["state"] == "ready" for item in required),
                "minimum_optional_ready": minimum_optional,
                "optional_ready": optional_ready,
                "dependencies": dependencies,
            }
        )

    flattened: dict[str, dict[str, Any]] = {}
    for capability in capabilities:
        for item in capability["dependencies"]:
            previous = flattened.get(item["dataset"])
            if previous is None or (
                previous["state"] == "ready" and item["state"] != "ready"
            ):
                flattened[item["dataset"]] = item
    counts = {
        status: sum(item["status"] == status for item in capabilities)
        for status in ("ready", "degraded", "unavailable")
    }
    dataset_counts = {
        state: sum(item["state"] == state for item in flattened.values())
        for state in ("ready", "unverified", "stale", "missing", "unknown")
    }
    overall = (
        "unavailable"
        if counts["unavailable"]
        else "degraded"
        if counts["degraded"]
        else "ready"
    )
    return {
        "status": overall,
        "as_of": as_of,
        "summary": {
            "capabilities": len(capabilities),
            **{f"{key}_capabilities": value for key, value in counts.items()},
            "datasets": len(flattened),
            **{f"{key}_datasets": value for key, value in dataset_counts.items()},
        },
        "capabilities": capabilities,
        "datasets": sorted(flattened.values(), key=lambda item: item["dataset"]),
        "semantics": {
            "task_state": "transport execution, retry and scheduling state",
            "data_state": "freshness plus strict expected-partition coverage for the declared research scope",
            "ready": "all required datasets are present, fresh and strictly verified for the declared scope",
            "degraded": "data exists but at least one required historical scope is not strictly proven",
            "unavailable": "a required dataset is absent or stale",
        },
    }


def lineage_catalog() -> list[dict[str, Any]]:
    """Return a JSON-safe research-to-dataset relationship table."""

    from service.data_service.source_policy import (
        dataset_fallback_routes,
        dataset_fallback_status,
    )

    def public_dependency(item: dict[str, Any]) -> dict[str, Any]:
        dataset = item["dataset"]
        return {
            **item,
            "source_ids": (
                ["chinamoney", "tushare"]
                if dataset == "cn_lpr"
                else ["tushare"]
            ),
            "read_strategy": "local_db_first",
            "fallback_routes": list(dataset_fallback_routes(dataset)),
            "fallback_status": dataset_fallback_status(dataset),
            "runtime_external_query": False,
        }

    return [
        {
            **{key: value for key, value in contract.items() if key != "dependencies"},
            "dependencies": [
                public_dependency(item) for item in contract["dependencies"]
            ],
        }
        for contract in RESEARCH_DATA_CONTRACTS
    ]


def research_history_requirements(as_of: date) -> dict[str, date]:
    """Return the broadest declared historical scope for every dataset.

    Initialization and ad-hoc assurance use the same source of truth as the
    runtime readiness evaluator.  This prevents a new research dependency
    from being documented without also entering the verification plan.
    """
    requirements: dict[str, date] = {}
    for contract in RESEARCH_DATA_CONTRACTS:
        for dependency in contract["dependencies"]:
            required_start = _required_start(dependency, as_of)
            if required_start is None:
                continue
            dataset = dependency["dataset"]
            requirements[dataset] = min(
                required_start,
                requirements.get(dataset, required_start),
            )
    return requirements
