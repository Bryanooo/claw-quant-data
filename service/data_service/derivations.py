"""Derived-indicator inventory for the dashboard 数据派生 page.

Compiles the code-owned V2 transformation registry (see
:mod:`service.orchestration_v2.catalog`) into dashboard rows: which derived
indicators exist, which governed datasets feed them, how they are computed,
when they run, and which dates have actually been materialized.  Static
metadata is compiled once per process; date coverage is queried lazily by the
router so this module itself never opens a database connection.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from service.data_service.registry import DATASETS
from service.db import get_conn
from service.orchestration_v2.catalog import transformation_task_blueprints
from service.orchestration_v2.transformations import (
    SUPPORTED_TRANSFORMATION_TASK_KEYS,
)

# Data-plane names used by orchestration blueprints that differ from the
# public dataset registry identity.
_INPUT_DATASET_ALIASES = {
    "daily": "stock_daily",
    "daily_basic": "stock_daily_basic",
}

_ALGORITHM_NOTES = {
    "technical_factor_snapshot": (
        "以前复权日线为基础，计算牛门线/确认线/突破线（同花顺口径）、通用技术指标包"
        "与参数化指标，并叠加严格的 20/60 交易日成交成本线；当日证券主数据与行情、"
        "复权因子同批冻结，避免新上市/退市证券因竞态被遗漏。"
    ),
    "fama_french_daily": (
        "A 股 Fama-French 三因子（MKT/SMB/HML）：剔除 ST 与上市不足 60 个交易日的"
        "新股，按市值中位数×账面市值比 2×3 分组，市值加权构建组合收益，"
        "逐交易日合成日频因子序列。"
    ),
    "ggt_monthly": (
        "按月聚合港股通（沪/深）逐日成交统计，生成每月累计成交量与成交金额。"
    ),
}

_FREQUENCY_NOTES = {
    "technical_factor_snapshot": "每个交易日 · 输入日频数据就绪后自动派发",
    "fama_french_daily": "每个交易日 · 输入日频数据就绪后自动派发",
    "ggt_monthly": "每月（聚合日频港股通成交）",
}

# ggt_monthly is materialized through the collector runtime (monthly
# aggregation of local ggt_daily) rather than the V2 dispatch whitelist.
_IMPLEMENTED_OVERRIDES = frozenset({"ggt_monthly"})

_PLANNED_TITLES = {
    "adjusted_price_return": "后复权价格与收益率序列",
    "canonical_period_bars": "规范周期K线（周/月）",
    "valuation_percentile_snapshot": "估值分位快照",
    "market_breadth": "市场宽度（涨跌/涨停分布）",
    "sector_breadth": "行业宽度",
    "etf_flow": "ETF 资金流",
    "sector_rotation": "行业轮动信号",
    "industry_fundamental_snapshot": "行业基本面快照",
    "repurchase_progress_snapshot": "回购进度快照",
    "investment_event_calendar": "投资事件日历",
    "macro_regime": "宏观状态刻画",
    "etf_state_team_signal": "ETF 国家队信号",
}

_ALGORITHM_PLANNED = "算法待固化：任务蓝图已登记（planned-v1），尚未纳入派发白名单。"


@lru_cache(maxsize=1)
def _dataset_by_name() -> dict[str, Any]:
    return {item.name: item for item in DATASETS.list()}


@lru_cache(maxsize=1)
def _derived_outputs() -> dict[str, str]:
    """Map derived dataset name -> producing task key (for chained inputs)."""
    mapping: dict[str, str] = {}
    for blueprint in transformation_task_blueprints():
        for name in blueprint.output_datasets:
            mapping.setdefault(name, blueprint.task_key)
    return mapping


def _input_ref(name: str) -> dict[str, Any]:
    resolved = _INPUT_DATASET_ALIASES.get(name, name)
    dataset = _dataset_by_name().get(resolved)
    if dataset is not None:
        return {
            "kind": "dataset",
            "name": resolved,
            "title": dataset.description.split("：")[0] if dataset.description else resolved,
            "table": dataset.table,
        }
    producer = _derived_outputs().get(name)
    if producer:
        return {
            "kind": "derived",
            "name": name,
            "title": f"上游派生数据（{producer} 产出）",
            "table": None,
        }
    return {"kind": "unknown", "name": name, "title": name, "table": None}


@lru_cache(maxsize=1)
def derivation_inventory() -> list[dict[str, Any]]:
    """Compile all V2 derived-indicator tasks into dashboard rows."""
    datasets = _dataset_by_name()
    rows: list[dict[str, Any]] = []
    for blueprint in transformation_task_blueprints():
        implemented = (
            blueprint.task_key in SUPPORTED_TRANSFORMATION_TASK_KEYS
            or blueprint.task_key in _IMPLEMENTED_OVERRIDES
        )
        output_specs = [datasets.get(name) for name in blueprint.output_datasets]
        primary = next((spec for spec in output_specs if spec), None)
        description = primary.description if primary else None
        title = description.split("：")[0] if description else None
        if title is None:
            title = _PLANNED_TITLES.get(blueprint.task_key, blueprint.task_key)
        rows.append({
            "source": "transformation",
            "key": blueprint.task_key,
            "title": title,
            "description": description,
            "category": primary.category if primary else "derived",
            "status": "implemented" if implemented else "planned",
            "algorithm": _ALGORITHM_NOTES.get(blueprint.task_key)
            or (_ALGORITHM_PLANNED if not implemented else None),
            "implementation_version": blueprint.implementation_version,
            "priority": blueprint.priority,
            "inputs": [_input_ref(name) for name in blueprint.input_datasets],
            "output_datasets": list(blueprint.output_datasets),
            "tables": [spec.table for spec in output_specs if spec],
            "date_column": primary.date_column if primary else None,
            "dependency_task_keys": list(blueprint.dependency_task_keys),
            "frequency": _FREQUENCY_NOTES.get(blueprint.task_key)
            or ("未纳入派发（蓝图登记）" if not implemented else "依赖就绪自动派发"),
        })
    rows.sort(key=lambda row: (row["status"] != "implemented", row["key"]))
    return rows


@lru_cache(maxsize=1)
def derivation_summary() -> dict[str, Any]:
    items = derivation_inventory()
    by_status: dict[str, int] = {}
    for item in items:
        by_status[item["status"]] = by_status.get(item["status"], 0) + 1
    return {
        "tasks": len(items),
        "by_status": by_status,
        "on_demand_endpoints": len(on_demand_catalog()),
    }


@lru_cache(maxsize=1)
def on_demand_catalog() -> list[dict[str, Any]]:
    """Research-layer indicators computed on demand (never materialized).

    Capability-discovery and quality endpoints are excluded: they describe
    the research service itself rather than a computed indicator.
    """
    from service.research.catalog import DERIVED_ENDPOINTS

    excluded_domains = {"能力发现", "质量与可用性"}
    rows = []
    for entry in DERIVED_ENDPOINTS:
        if entry.get("domain") in excluded_domains:
            continue
        rows.append({
            "key": entry.get("path", ""),
            "title": entry.get("name", ""),
            "domain": entry.get("domain", ""),
            "method": entry.get("method", "GET"),
            "description": entry.get("description", ""),
        })
    return rows


def date_coverage(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any] | None]:
    """Query materialized date coverage per implemented output table.

    Returns a mapping keyed by task key.  Missing tables or database errors
    degrade to ``None`` so the inventory always renders.
    """
    import psycopg2

    coverage: dict[str, dict[str, Any] | None] = {}
    connection = None
    try:
        connection = get_conn()
        with connection.cursor() as cursor:
            for row in rows:
                coverage[row["key"]] = _table_coverage(cursor, connection, row)
    except Exception:  # pragma: no cover - database unavailable
        return {row["key"]: None for row in rows}
    finally:
        if connection is not None:
            connection.close()
    return coverage


def _table_coverage(cursor, connection, row: dict[str, Any]) -> dict[str, Any] | None:
    if row["status"] != "implemented":
        return None
    column = row["date_column"] or "trade_date"
    for table in row["tables"]:
        try:
            cursor.execute(
                f"SELECT count(DISTINCT {column}), min({column}), max({column}) "
                f"FROM {table}"
            )
            days, first, last = cursor.fetchone()
            return {
                "table": table,
                "days": int(days) if days is not None else 0,
                "first_date": str(first) if first else None,
                "latest_date": str(last) if last else None,
            }
        except Exception:
            connection.rollback()
    return None
