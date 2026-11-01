"""Semantic feature directory: canonical identity, source and honest readiness."""

from datetime import datetime, timezone

from service.cache import TTLCache
from service.db import query
from service.research.local_factors.catalog import FACTOR_SCHEMA_VERSION, FACTOR_SPECS
from service.research.local_factors.ownership import (
    SHARED_TECHNICAL_FIELDS, TECHNICAL_ALIASES, TECHNICAL_FEATURES,
)

CATEGORIES = {
    "trend": "趋势与均线", "momentum": "动量与反转", "volatility": "波动与通道",
    "volume_price": "量价与流动性", "structure": "价格结构与突破",
    "value": "估值", "growth": "成长", "quality": "质量与财务",
    "size": "规模", "risk": "风险与基准暴露", "chip": "筹码与成本结构",
}
_FAMILY_CATEGORY = {
    "Alpha101": "volume_price", "Growth": "growth", "Liquidity": "volume_price",
    "Momentum": "momentum", "Quality": "quality", "Reversal": "momentum",
    "Risk": "risk", "Size": "size", "Value": "value",
}
_CACHE = TTLCache(ttl_seconds=120, max_entries=1)


def _technical_category(name: str) -> str:
    if name.startswith(("ema", "sma", "signal_ma", "bbi", "regression")):
        return "trend"
    if name.startswith(("atr", "natr", "keltner", "bollinger", "ttm")):
        return "volatility"
    if name.startswith(("rsi", "roc", "cci", "tsi", "bias", "ppo", "trix")):
        return "momentum"
    if name.startswith(("cost", "pvt", "vroc", "force")):
        return "volume_price"
    return "structure"


def local_feature_definitions() -> list[dict]:
    aliases: dict[str, list[str]] = {}
    for alias, canonical in SHARED_TECHNICAL_FIELDS.items():
        if alias != canonical:
            aliases.setdefault(canonical, []).append(alias)
    for alias, (canonical, _) in TECHNICAL_ALIASES.items():
        aliases.setdefault(canonical, []).append(alias)
    result = []
    for spec in FACTOR_SPECS:
        result.append({
            "name": spec.name, "position": spec.position,
            "category": _FAMILY_CATEGORY[spec.family], "family": spec.family,
            "package": "Alpha101" if spec.family == "Alpha101" else "Style171",
            "role": "quantitative_feature", "formula": spec.formula if spec.formula != spec.name else None,
            "implementation": "service/research/local_factors/" +
                ("alpha101.py" if spec.computation_group == "alpha101" else spec.computation_group + ".py"),
            "unit": {"amount_ma_20d": "CNY (actual unadjusted turnover)",
                     "sum_abs_rtn_amount_20d": "fractional return / CNY; no inferred provider multiplier"}.get(spec.name),
        })
    for name in TECHNICAL_FEATURES:
        result.append({
            "name": name, "position": None, "category": _technical_category(name),
            "family": "Technical", "package": "Technical", "role": "technical_indicator",
            "formula": None, "implementation": "service/orchestration_v2/transformations.py",
        })
    for item in result:
        item.update({
            "id": f"equity.daily.{item['name']}@{FACTOR_SCHEMA_VERSION}",
            "category_label": CATEGORIES[item["category"]],
            "aliases": aliases.get(item["name"], []),
            "origin": "local", "official_source": "claw_local",
            "input_provider": "Tushare (本地业务数据)", "frequency": "daily",
            "storage": "local_factor_snapshot", "asset_class": "equity",
            "query_path": "/api/v1/research/factors/{ts_code}", "fallback_allowed": False,
        })
    return result


def factor_catalog() -> dict:
    return _CACHE.get_or_compute("unified", _build_catalog)


def _build_catalog() -> dict:
    factors = local_feature_definitions()
    bounds = query("""
        SELECT min(trade_date) AS min_date,max(trade_date) AS max_date,
               count(DISTINCT trade_date) AS days,count(*) AS rows
        FROM local_factor_snapshot WHERE schema_version=%s
    """, (FACTOR_SCHEMA_VERSION,))[0]
    latest = bounds["max_date"]
    availability = {}
    validation = {}
    if latest:
        rows = query("""
            WITH latest AS MATERIALIZED (
                SELECT factor_values,technical_values FROM local_factor_snapshot
                WHERE schema_version=%s AND trade_date=%s
            )
            SELECT i::text AS key,count(*) FILTER (WHERE factor_values[i] IS NOT NULL) AS available,
                   count(*) AS total FROM latest CROSS JOIN generate_series(1,272) i GROUP BY i
            UNION ALL
            SELECT key,count(*) FILTER (WHERE value <> 'null'::jsonb),count(*)
            FROM latest CROSS JOIN LATERAL jsonb_each(technical_values) GROUP BY key
        """, (FACTOR_SCHEMA_VERSION, latest))
        availability = {str(row["key"]): row for row in rows}
        validation = {str(row["factor_position"]): dict(row) for row in query("""
            SELECT factor_position,validation_status,validation_reason,sample_size,pearson_correlation,value_match_ratio
            FROM local_factor_validation WHERE schema_version=%s AND trade_date=%s
        """, (FACTOR_SCHEMA_VERSION, latest))}
    for factor in factors:
        key = str(factor["position"] or factor["name"])
        evidence = availability.get(key, {})
        factor.update({
            "observation_date": str(latest) if latest else None,
            "available_securities": int(evidence.get("available") or 0),
            "observed_securities": int(evidence.get("total") or 0),
            "availability": "has_values" if evidence.get("available") else "missing",
            "validation": validation.get(key, {"validation_status": "not_compared"}),
        })
    # Provider chip estimates are not equivalent to transaction-cost VWAP.
    for dataset, fields in {
        "cyq_perf": ("winner_rate", "cost_5pct", "cost_15pct", "cost_50pct", "cost_85pct", "cost_95pct", "weight_avg"),
        "cyq_chips": ("percent",),
    }.items():
        for field in fields:
            factors.append({
                "id": f"equity.daily.{dataset}.{field}@provider-v1",
                "name": f"{dataset}.{field}", "category": "chip", "category_label": CATEGORIES["chip"],
                "family": "Chip", "package": "Chip", "role": "provider_indicator",
                "origin": "provider", "official_source": "tushare", "input_provider": "Tushare",
                "frequency": "daily", "asset_class": "equity", "aliases": [], "storage": dataset,
                "formula": None, "availability": "not_audited",
                "validation": {"validation_status": "provider_contract"},
                "query_path": f"/api/v1/data/datasets/{dataset}/records", "fallback_allowed": False,
            })
    return {
        "contract": "claw-factor-catalog@v2", "generated_at": datetime.now(timezone.utc).isoformat(),
        "categories": [{"name": key, "label": label} for key, label in CATEGORIES.items()],
        "factors": factors, "factor_count": len(factors), "local_count": len(factors)-8, "provider_count": 8,
        "local_storage_range": {key: str(value) if hasattr(value, "isoformat") else value for key,value in bounds.items()},
        "schema_version": FACTOR_SCHEMA_VERSION,
        "quality": query("""SELECT audit_status,count(*) AS securities FROM local_factor_snapshot
            WHERE schema_version=%s AND trade_date=%s GROUP BY audit_status""", (FACTOR_SCHEMA_VERSION, latest)) if latest else [],
        "notes": [
            "同一日频特征仅一个正式来源；别名不新增因子、不存第二份值。",
            "日期边界只描述存储范围，不证明中间连续或全市场完整。就绪数量仅对应最新数据日。",
            "有值不等于验证通过；相关性抽检不能证明公式等价或逐值一致。",
            "当前目录仅展示修正版本；旧版本保留作审计证据，不自动回退。就绪须逐特征检查，缺失原因不明不会标绿。",
            "factor_value 仅内部抽检，保留采集，不出现在正式供给、不作缺失回退。",
            "周/月及临时参数计算属于独立口径，不计入已落库日频目录。",
        ],
        "audit": {"dataset": "factor_value", "purpose": "internal_comparison_only",
                  "collection_retained": True, "external_values": False},
        "unregistered_provider_datasets": [
            {"dataset": dataset, "source": "Tushare", "reason": reason}
            for dataset, reason in (
                ("stk_factor", "股票供应商技术指标；保留基础数据查询，尚未逐项证明与本地公式等价，不混计正式特征"),
                ("stk_factor_pro", "股票专业技术指标；复权、暖机及公式映射待逐项核验，不自动替代本地特征"),
                ("fund_factor_pro", "ETF/基金供应商指标；尚未注册为统一特征身份，仍可通过基础数据查询"),
                ("idx_factor_pro", "指数供应商指标；尚未注册为统一特征身份，仍可通过基础数据查询"),
                ("cb_factor_pro", "可转债供应商指标；尚未注册为统一特征身份，仍可通过基础数据查询"),
            )
        ],
    }
