"""Interface-centric dependency inventory for the dashboard 数据依赖 page.

This module deliberately answers a presentation question: *which upstream
interfaces exist, are they used, how often, by which task, into which table,
and with which fields*.  It is a pure code-level compilation of governed
catalog assets (Tushare contracts, the source registry, V2 task blueprints,
collector contracts and the dataset registry) plus the reviewed
蚂蚁数据源 semantic mapping and source policy.  It performs **no database
access**: runtime execution states are merged by the router from an
:class:`~service.orchestration_v2.repository.OrchestrationV2Repository`
snapshot, so the inventory itself stays testable without PostgreSQL.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from service.collector_catalog import CollectorContract, discover_collectors
from service.data_service.provider_equivalence import (
    financial_tushare_catalog,
    financial_tushare_mapping,
    tushare_financial_reverse_catalog,
)
from service.data_service.registry import DATASETS
from service.data_service.source_policy import route_source_policy
from service.orchestration_v2.catalog import (
    acquisition_task_blueprints,
)
from service.source_connectors.financial_data_catalog import FINANCIAL_DATA_ROUTES
from service.source_connectors.public_catalog import PUBLIC_ENDPOINTS, PUBLIC_SOURCES
from service.source_connectors.registry import SOURCE_REGISTRY


ROOT = Path(__file__).resolve().parents[2]

# Recorded operational pauses.  ``us_daily`` stays registered for stock
# queries but scheduled collection is stopped (hourly rate limit; no active
# US research).  See README「当前组成」.
PAUSED_TUSHARE_APIS = frozenset({"us_daily"})

# Tushare permission statuses that mean "token cannot call this today".
_NO_PERMISSION_TOKEN = "无权限"

ACQUISITION_REALTIME = "realtime"
ACQUISITION_ON_DEMAND = "on_demand"
ACQUISITION_SCHEDULED = "scheduled"

# Asset-class taxonomy shared by the 数据依赖 page filter.  Keys are stable
# API values; the dashboard maps them to Chinese labels.
ASSET_CLASS_STOCK = "stock"
ASSET_CLASS_HK = "hk_stock"
ASSET_CLASS_US = "us_stock"
ASSET_CLASS_FUND = "fund"
ASSET_CLASS_INDEX = "index_etf"
ASSET_CLASS_BOND = "bond"
ASSET_CLASS_DERIV = "derivatives"
ASSET_CLASS_FOREX = "forex"
ASSET_CLASS_MACRO = "macro"
ASSET_CLASS_ALT = "altdata"
ASSET_CLASS_INFO = "info"
ASSET_CLASS_CHAIN = "chain"
ASSET_CLASS_FACTOR = "factor"
ASSET_CLASS_QUOTE = "quote"
ASSET_CLASS_OTHER = "other"

_TUSHARE_CATEGORY_ASSET_CLASS: list[tuple[str, str]] = [
    ("股票数据", ASSET_CLASS_STOCK),
    ("港股数据", ASSET_CLASS_HK),
    ("美股数据", ASSET_CLASS_US),
    ("公募基金", ASSET_CLASS_FUND),
    ("ETF专题", ASSET_CLASS_INDEX),
    ("指数专题", ASSET_CLASS_INDEX),
    ("债券专题", ASSET_CLASS_BOND),
    ("期权数据", ASSET_CLASS_DERIV),
    ("期货数据", ASSET_CLASS_DERIV),
    ("现货数据", ASSET_CLASS_DERIV),
    ("外汇数据", ASSET_CLASS_FOREX),
    ("宏观经济", ASSET_CLASS_MACRO),
    ("量化因子库", ASSET_CLASS_FACTOR),
    ("大模型语料", ASSET_CLASS_INFO),
    ("自选组合", ASSET_CLASS_OTHER),
    ("项目扩展接口", ASSET_CLASS_OTHER),
]

# 个别接口按名称覆盖分类：语料类里货币政策执行报告属于宏观文档。
_TUSHARE_API_ASSET_CLASS: dict[str, str] = {
    "monetary_policy": ASSET_CLASS_MACRO,
}

_ANT_SEGMENT_ASSET_CLASS = {
    "stock": ASSET_CLASS_STOCK,
    "stock_fnd": ASSET_CLASS_STOCK,
    "stock_sh_equity": ASSET_CLASS_STOCK,
    "hk_stock": ASSET_CLASS_HK,
    "us_stock": ASSET_CLASS_US,
    "fund": ASSET_CLASS_FUND,
    "fund_derived": ASSET_CLASS_FUND,
    "index_fnd": ASSET_CLASS_INDEX,
    "sector": ASSET_CLASS_INDEX,
    "quote": ASSET_CLASS_QUOTE,
    "macro": ASSET_CLASS_MACRO,
    "altdata": ASSET_CLASS_ALT,
    "info": ASSET_CLASS_INFO,
    "common": ASSET_CLASS_CHAIN,
    "onecode": ASSET_CLASS_OTHER,
}

_PUBLIC_SOURCE_ASSET_CLASS = {
    "chinabond": ASSET_CLASS_BOND,
    "chinamoney": ASSET_CLASS_BOND,
    "pboc": ASSET_CLASS_MACRO,
    "cninfo": ASSET_CLASS_INFO,
    "sse": ASSET_CLASS_INFO,
    "sina": ASSET_CLASS_QUOTE,
}


def _tushare_asset_class(category: str, api_name: str = "") -> str:
    if api_name in _TUSHARE_API_ASSET_CLASS:
        return _TUSHARE_API_ASSET_CLASS[api_name]
    for prefix, asset_class in _TUSHARE_CATEGORY_ASSET_CLASS:
        if category.startswith(prefix):
            return asset_class
    return ASSET_CLASS_OTHER


def _ant_asset_class(route: str) -> str:
    segment = route.split("/")[3] if route.count("/") >= 3 else "other"
    return _ANT_SEGMENT_ASSET_CLASS.get(segment, ASSET_CLASS_OTHER)


def _read_tushare_contracts() -> dict[str, dict[str, Any]]:
    path = ROOT / "docs" / "tushare" / "contracts.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {item["api_name"]: item for item in payload.get("interfaces", [])}


def _ant_contract_for(route: str) -> dict[str, Any]:
    path = ROOT / "docs" / "ant_data" / "route-contracts.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    for item in payload.get("routes", []):
        if item.get("url") == route:
            return item
    return {}


def _tushare_status(api_name: str, registered: bool, contract: dict[str, Any]) -> str:
    if api_name in PAUSED_TUSHARE_APIS:
        return "paused"
    if registered:
        return "active"
    permission = (contract.get("permission") or {}).get("status", "")
    if permission == _NO_PERMISSION_TOKEN:
        return "no_permission"
    if not contract.get("collectable", False):
        return "not_scheduled"
    return "not_scheduled"


@lru_cache(maxsize=1)
def _tushare_compilation() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Compile Tushare inventory rows and table-level field lineage."""
    contracts = _read_tushare_contracts()
    registered = {
        endpoint.endpoint_key: endpoint
        for endpoint in SOURCE_REGISTRY.list_endpoints("tushare")
    }
    collectors: dict[str, list[CollectorContract]] = {}
    for collector in discover_collectors():
        collectors.setdefault(collector.api_name, []).append(collector)

    name_to_dataset = {dataset.name: dataset for dataset in DATASETS.list()}
    endpoint_to_tasks: dict[str, list[dict[str, Any]]] = {}
    for task in acquisition_task_blueprints():
        for reference in task.endpoints:
            endpoint_to_tasks.setdefault(reference.endpoint_key, []).append({
                "task_key": task.task_key,
                "cadence": task.cadence,
                "output_datasets": list(task.output_datasets),
                "group_endpoints": [ref.endpoint_key for ref in task.endpoints],
            })

    reverse = {
        item["api_name"]: item for item in tushare_financial_reverse_catalog()
    }

    # VIP twin endpoints: some finance collectors actually call the `_vip`
    # interface (per-period full-market extraction) while the plain interface
    # only exists as the official documented contract.  The actually-called
    # endpoint becomes the scheduled row (inheriting the official field
    # contract); the plain one is recorded as not scheduled.
    def _vip_base(api: str) -> str | None:
        if not api.endswith("_vip"):
            return None
        base = api[: -len("_vip")]
        base_contract = contracts.get(base)
        if base_contract is None:
            return None
        status_text = str((base_contract.get("implementation") or {}).get("status", ""))
        return base if api in status_text else None

    vip_to_base = {api: base for api in contracts if (base := _vip_base(api))}
    replaced_by_vip = {base: vip for vip, base in vip_to_base.items()}

    rows: list[dict[str, Any]] = []
    lineage: dict[str, dict[str, Any]] = {}

    for api_name in sorted(contracts):
        contract = contracts[api_name]
        endpoint = registered.get(api_name)
        shadowed_by = replaced_by_vip.get(api_name)
        if shadowed_by:
            tasks = []
        else:
            tasks = endpoint_to_tasks.get(api_name, [])
        base_api = vip_to_base.get(api_name)
        display_contract = contracts[base_api] if base_api else contract
        display_title = contract.get("title", "")
        if base_api and (not display_title or "未列出" in display_title):
            display_title = contracts[base_api].get("title", "") or display_title

        tables: set[str] = set()
        for collector in collectors.get(api_name, []):
            tables.add(collector.table_name)
        datasets = []
        seen_datasets: set[str] = set()
        for task in tasks:
            for name in task["output_datasets"]:
                if name in seen_datasets or name not in name_to_dataset:
                    continue
                seen_datasets.add(name)
                dataset = name_to_dataset[name]
                datasets.append({
                    "name": dataset.name,
                    "category": dataset.category,
                    "table": dataset.table,
                })
                tables.add(dataset.table)

        output_fields = [
            {
                "name": field.get("name", ""),
                "type": field.get("type", ""),
                "description": field.get("description", ""),
            }
            for field in display_contract.get("output_parameters", [])
        ]
        status = _tushare_status(api_name, endpoint is not None, contract)
        if shadowed_by:
            status = "not_scheduled"
        permission = contract.get("permission") or {}
        implementation = contract.get("implementation") or {}
        relation = reverse.get(api_name) or {
            "full_equivalence_routes": [],
            "partial_overlap_routes": [],
        }

        rows.append({
            "source": "tushare",
            "key": api_name,
            "title": display_title,
            "category": (display_contract.get("category_path")
                         or display_contract.get("category", "")),
            "asset_class": _tushare_asset_class(
                (display_contract.get("category_path")
                 or display_contract.get("category", "")),
                api_name,
            ),
            "status": status,
            "permission": permission.get("status", "未知"),
            "collectable": bool(contract.get("collectable")),
            "acquisition_kind": ACQUISITION_SCHEDULED if status in {"active", "paused"} else "none",
            "cadence": endpoint.cadence if endpoint else None,
            "resource_class": endpoint.resource_class if endpoint else None,
            "contract_source": base_api if base_api else None,
            "superseded_by": shadowed_by,
            "tasks": [
                {
                    "task_key": task["task_key"],
                    "cadence": task["cadence"],
                    "output_datasets": task["output_datasets"],
                }
                for task in tasks
            ],
            "datasets": [item["name"] for item in datasets],
            "tables": sorted(tables),
            "field_count": len(output_fields),
            "implementation": {
                "status": implementation.get("status", "未登记"),
                "mode": implementation.get("mode"),
                "references": list(implementation.get("references", [])),
            },
            "ant_full_equivalence_routes": list(relation.get("full_equivalence_routes", [])),
            "ant_partial_overlap_routes": list(relation.get("partial_overlap_routes", [])),
        })

        for table in sorted(tables):
            entry = lineage.setdefault(table, {
                "table": table,
                "source": "tushare",
                "interfaces": [],
                "fields": [],
            })
            if api_name not in entry["interfaces"]:
                entry["interfaces"].append(api_name)
            existing = {field["name"]: field for field in entry["fields"]}
            for field in output_fields:
                target = existing.get(field["name"])
                if target is None:
                    target = {
                        "name": field["name"],
                        "type": field["type"],
                        "description": field["description"],
                        "from_interfaces": [],
                    }
                    existing[field["name"]] = target
                    entry["fields"].append(target)
                if api_name not in target["from_interfaces"]:
                    target["from_interfaces"].append(api_name)

    inventory = sorted(rows, key=lambda row: (row["source"], row["key"]))
    lineage_rows = sorted(lineage.values(), key=lambda item: item["table"])
    return inventory, lineage_rows


@lru_cache(maxsize=1)
def _financial_data_compilation() -> list[dict[str, Any]]:
    contracts = {route: _ant_contract_for(route) for route in FINANCIAL_DATA_ROUTES}
    policies = {route: route_source_policy(route) for route in sorted(FINANCIAL_DATA_ROUTES)}
    scheduled = _financial_data_scheduled_tasks()

    rows: list[dict[str, Any]] = []
    for route in sorted(FINANCIAL_DATA_ROUTES):
        info = contracts.get(route) or {}
        policy = policies[route]
        mapping = financial_tushare_mapping(route)
        realtime = policy.dependency_class == "financial_data_realtime_required"
        tasks = scheduled.get(route, [])
        if tasks:
            # Reviewed scheduled-pull routes are now actively collected.
            status = "active"
            acquisition_kind = ACQUISITION_SCHEDULED
            cadence = tasks[0]["cadence"]
            datasets = sorted({
                name
                for task in tasks
                for name in task["output_datasets"]
            })
            tables = sorted({task["table"] for task in tasks})
        else:
            status = {
                "financial_data_realtime_required": "realtime_required",
                "financial_data_primary_no_local_canonical": "ant_primary",
                "local_canonical_fallback_disabled": "not_scheduled",
                "local_overlap_adapter_pending": "adapter_pending",
            }[policy.dependency_class]
            acquisition_kind = ACQUISITION_REALTIME if realtime else ACQUISITION_ON_DEMAND
            cadence = "realtime" if realtime else "on_demand"
            datasets = list(policy.local_datasets)
            tables = []
        response_fields = [
            {"name": name, "type": description}
            for name, description in (info.get("response") or {}).items()
        ]
        rows.append({
            "source": "financial_data",
            "key": route,
            "title": info.get("name", route.rsplit("/", 1)[-1]),
            "category": route.split("/")[3] if route.count("/") >= 3 else "other",
            "asset_class": _ant_asset_class(route),
            "status": status,
            "acquisition_kind": acquisition_kind,
            "cadence": cadence,
            "tasks": tasks,
            "datasets": datasets,
            "tables": tables,
            "field_count": len(response_fields),
            "preferred_read": policy.preferred_read,
            "adapter_status": policy.adapter_status,
            "public_access": policy.public_access,
            "equivalence_class": mapping.equivalence_class,
            "coverage": mapping.coverage,
            "rationale": mapping.rationale,
            "tushare_interfaces": list(mapping.tushare_interfaces),
            "related_tushare_interfaces": list(mapping.related_tushare_interfaces),
            "policy_reason": policy.reason,
        })
    return rows


@lru_cache(maxsize=1)
def _financial_data_scheduled_tasks() -> dict[str, list[dict[str, Any]]]:
    """Route → acquisition blueprints for the ant scheduled-pull allow-list."""
    from service.source_connectors.ant_scheduled import SCHEDULED_ROUTES

    tasks: dict[str, list[dict[str, Any]]] = {}
    for task in acquisition_task_blueprints():
        for reference in task.endpoints:
            if reference.source_id != "financial_data":
                continue
            spec = SCHEDULED_ROUTES[reference.endpoint_key]
            tasks.setdefault(spec.route, []).append({
                "task_key": task.task_key,
                "cadence": task.cadence,
                "output_datasets": list(task.output_datasets),
                "table": spec.table,
            })
    return tasks


@lru_cache(maxsize=1)
def _public_compilation() -> list[dict[str, Any]]:
    display = {source.source_id: source.display_name for source in PUBLIC_SOURCES}
    rows: list[dict[str, Any]] = []
    for endpoint in PUBLIC_ENDPOINTS:
        fields = list(endpoint.capabilities.get("fields", []))
        rows.append({
            "source": endpoint.source_id,
            "key": f"{endpoint.source_id}/{endpoint.endpoint_key}",
            "title": f"{display.get(endpoint.source_id, endpoint.source_id)} · {endpoint.title}",
            "category": "public_evidence",
            "asset_class": _PUBLIC_SOURCE_ASSET_CLASS.get(
                endpoint.source_id, ASSET_CLASS_OTHER
            ),
            "status": "public_registered",
            "acquisition_kind": ACQUISITION_ON_DEMAND,
            "cadence": "on_demand",
            "tasks": [],
            "datasets": [],
            "tables": [],
            "field_count": len(fields),
            "fields": [{"name": name, "type": "", "description": ""} for name in fields],
            "cache_ttl_seconds": endpoint.cache_ttl_seconds,
            "completeness": dict(endpoint.completeness_policy),
        })
    return rows


@lru_cache(maxsize=1)
def interface_inventory() -> list[dict[str, Any]]:
    tushare_rows, _ = _tushare_compilation()
    return [*tushare_rows, *_financial_data_compilation(), *_public_compilation()]


@lru_cache(maxsize=1)
def field_lineage() -> list[dict[str, Any]]:
    """Table-level field lineage: physical table → fields ← source interfaces."""
    _, lineage_rows = _tushare_compilation()
    return lineage_rows


@lru_cache(maxsize=1)
def dependency_summary() -> dict[str, Any]:
    items = interface_inventory()
    by_source: dict[str, int] = {}
    by_status: dict[str, int] = {}
    by_asset_class: dict[str, int] = {}
    for item in items:
        by_source[item["source"]] = by_source.get(item["source"], 0) + 1
        by_status[item["status"]] = by_status.get(item["status"], 0) + 1
        asset_class = item.get("asset_class", "other")
        by_asset_class[asset_class] = by_asset_class.get(asset_class, 0) + 1
    equivalence = financial_tushare_catalog()
    equivalence_counts: dict[str, int] = {}
    for mapping in equivalence:
        equivalence_counts[mapping.equivalence_class] = (
            equivalence_counts.get(mapping.equivalence_class, 0) + 1
        )
    return {
        "interfaces": len(items),
        "by_source": dict(sorted(by_source.items())),
        "by_status": dict(sorted(by_status.items())),
        "by_asset_class": dict(sorted(by_asset_class.items())),
        "equivalence_counts": dict(sorted(equivalence_counts.items())),
        "datasets": len(DATASETS.list()),
        "tasks": len(acquisition_task_blueprints()),
    }


def interface_detail(source: str, key: str) -> dict[str, Any] | None:
    items = interface_inventory()
    for item in items:
        if item["source"] == source and item["key"] == key:
            break
    else:
        return None
    detail = dict(item)
    if source == "tushare":
        contracts = _read_tushare_contracts()
        contract_source = detail.get("contract_source")
        superseded_by = detail.get("superseded_by")
        # VIP endpoints inherit the official contract of their plain twin
        # (same fields, same data — verified); shadowed plain interfaces keep
        # their own contract but explain where collection actually goes.
        contract = contracts.get(contract_source or key, {})
        if superseded_by:
            detail["description"] = (
                f"{contract.get('description', '')}（本条目为官方契约登记；"
                f"采集调度实际调用 {superseded_by}，数据内容与官方契约完全一致。）"
            )
        elif contract_source:
            detail["description"] = (
                f"{contract.get('description', '')}（采集调度实际调用本端点；"
                f"字段契约与官方接口 {contract_source} 一致。）"
            )
        else:
            detail["description"] = contract.get("description", "")
        detail["official_urls"] = list(contract.get("official_urls", []))
        detail["input_parameters"] = [
            {
                "name": field.get("name", ""),
                "type": field.get("type", ""),
                "required": field.get("required", ""),
                "description": field.get("description", ""),
            }
            for field in contract.get("input_parameters", [])
        ]
        detail["output_parameters"] = [
            {
                "name": field.get("name", ""),
                "type": field.get("type", ""),
                "description": field.get("description", ""),
            }
            for field in contract.get("output_parameters", [])
        ]
    elif source == "financial_data":
        contract = _ant_contract_for(key)
        detail["description"] = contract.get("description", "")
        detail["request_parameters"] = dict(contract.get("request") or {})
        detail["response_parameters"] = dict(contract.get("response") or {})
    else:
        for endpoint in PUBLIC_ENDPOINTS:
            if f"{endpoint.source_id}/{endpoint.endpoint_key}" == key:
                detail["description"] = endpoint.title
                detail["request_parameters"] = dict(endpoint.request_contract)
                detail["output_parameters"] = [
                    {"name": name, "type": "", "description": ""}
                    for name in endpoint.capabilities.get("fields", [])
                ]
                break
    return detail


def merge_runtime(
    items: list[dict[str, Any]],
    execution_states: dict[str, dict[str, Any]],
    dataset_states: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    """Attach latest execution + dataset readiness onto inventory rows.

    Tushare rows join by task_key and dataset name.  Ant/public rows keep
    ``runtime=None`` because query-through traffic has no V2 task identity.
    """
    merged: list[dict[str, Any]] = []
    for item in items:
        row = dict(item)
        runtime: dict[str, Any] | None = None
        if row["tasks"] and row["source"] in {"tushare", "financial_data"}:
            states = [
                execution_states.get(task["task_key"])
                for task in row["tasks"]
            ]
            states = [state for state in states if state]
            if states:
                latest = max(states, key=lambda state: state.get("updated_at") or "")
                runtime = {"latest_execution": latest}
            ready = 0
            latest_date = None
            for name in row["datasets"]:
                state = dataset_states.get(name)
                if not state:
                    continue
                if state.get("ready"):
                    ready += 1
                candidate = state.get("observation_end")
                if candidate and (latest_date is None or str(candidate) > str(latest_date)):
                    latest_date = str(candidate)
            if row["datasets"]:
                runtime = {
                    **(runtime or {}),
                    "ready_datasets": ready,
                    "datasets": len(row["datasets"]),
                    "latest_data_date": latest_date,
                }
        row["runtime"] = runtime
        merged.append(row)
    return merged
