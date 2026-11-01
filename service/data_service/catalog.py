"""Machine-readable catalog for the public API namespaces and data layers."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from service.data_service.lineage import (
    CANONICAL_ENDPOINT_LINEAGE,
    endpoint_with_sources,
    research_endpoint_lineage,
)
from service.research.catalog import DERIVED_ENDPOINTS


# The ``domain`` labels on research endpoints grew organically (个股/基本面/估值/
# 技术面/资金… all describe stock research; 板块/行业 overlap).  Normalise them
# into a small, stable category vocabulary so the console can group and filter
# without leaking internal taxonomy noise.
_DOMAIN_TO_CATEGORY: dict[str, str] = {
    "个股研究": "个股研究",
    "基本面": "个股研究",
    "估值": "个股研究",
    "技术面": "个股研究",
    "资金": "个股研究",
    "股东回报": "个股研究",
    "微观结构": "个股研究",
    "市场": "个股研究",
    "市场研究": "个股研究",
    "风险": "个股研究",
    "板块": "板块·行业研究",
    "板块研究": "板块·行业研究",
    "行业": "板块·行业研究",
    "行业研究": "板块·行业研究",
    "ETF": "ETF研究",
    "ETF研究": "ETF研究",
    "指数": "指数研究",
    "指数研究": "指数研究",
    "宏观": "宏观研究",
    "宏观研究": "宏观研究",
    "事件": "事件研究",
    "事件研究": "事件研究",
    "关系发现": "关系发现",
    "量化研究": "量化与能力",
    "能力发现": "量化与能力",
    "质量与可用性": "量化与能力",
    "跨资产研究": "跨资产研究",
}

_LAYER_CATEGORY = {
    "raw": "原始审计",
    "standard": "标准数据",
}


def _normalize_category(layer: str, domain: str | None) -> str:
    if layer in _LAYER_CATEGORY:
        return _LAYER_CATEGORY[layer]
    return _DOMAIN_TO_CATEGORY.get(domain or "", domain or "其他")



RAW_ENDPOINTS = (
    {
        "method": "GET",
        "path": "/api/v1/audit/raw/interfaces",
        "name": "原始审计覆盖",
        "description": "查看可采接口的请求、失败和原始记录覆盖。",
    },
    {
        "method": "GET",
        "path": "/api/v1/audit/raw/{api_name}/requests",
        "name": "上游请求账本",
        "description": "分页查看真实 Tushare 请求参数与传输结果。",
    },
    {
        "method": "GET",
        "path": "/api/v1/audit/raw/{api_name}/records",
        "name": "原始记录",
        "description": "查询无损 JSONB 原文及其请求身份。",
    },
    {
        "method": "GET",
        "path": "/api/v1/audit/raw/{api_name}/coverage",
        "name": "接口审计摘要",
        "description": "查看单个接口的请求和记录覆盖摘要。",
    },
    {
        "method": "GET",
        "path": "/api/v1/audit/raw/{api_name}/lineage/{record_hash}",
        "name": "原始血缘",
        "description": "从一条原始记录追溯产生它的逻辑请求。",
    },
)

CANONICAL_ENDPOINTS = (
    {
        "method": "GET",
        "path": "/api/v1/data/canonical/market-bars",
        "name": "规范 A 股日线",
        "description": "本地优先并按缺失开市日有限回退的统一日线模型。",
    },
    {
        "method": "GET",
        "path": "/api/v1/data/canonical/trading-sessions",
        "name": "规范 A 股交易日历",
        "description": "统一 A 股开市日模型，本地日历为空时才允许回退。",
    },
    {
        "method": "GET",
        "path": "/api/v1/data/canonical/equity-profiles",
        "name": "规范 A 股身份",
        "description": "统一证券身份并保留行业分类来源。",
    },
    {
        "method": "GET",
        "path": "/api/v1/data/canonical/equity-valuations",
        "name": "规范 A 股估值",
        "description": "统一估值指标、股息率、股本和市值单位。",
    },
    {
        "method": "GET",
        "path": "/api/v1/data/canonical/equity-financial-periods",
        "name": "规范 A 股财务期间",
        "description": "按明确季度末组合三张累计报表并记录分段来源和披露日。",
    },
    {
        "method": "GET",
        "path": "/api/v1/data/canonical/equity-performance-updates",
        "name": "规范 A 股业绩预告与快报",
        "description": "按明确报告期统一业绩预告和累计业绩快报。",
    },
    {
        "method": "GET",
        "path": "/api/v1/data/canonical/equity-financial-metrics",
        "name": "规范 A 股财务指标",
        "description": "按明确报告期统一盈利、成长、偿债和营运核心指标。",
    },
    {
        "method": "GET",
        "path": "/api/v1/data/canonical/equity-ttm-financials",
        "name": "规范 A 股滚动财务",
        "description": "优先由本地累计报表派生滚动十二月核心财务事实。",
    },
    {
        "method": "GET",
        "path": "/api/v1/data/canonical/equity-dividends",
        "name": "规范 A 股分红",
        "description": "按明确报告期统一分红方案、关键日期和每股金额。",
    },
    {
        "method": "GET",
        "path": "/api/v1/data/canonical/equity-repurchases",
        "name": "规范 A 股回购",
        "description": "统一回购计划、执行进展、金额、数量和价格范围。",
    },
    {
        "method": "GET",
        "path": "/api/v1/data/canonical/equity-holder-counts",
        "name": "规范 A 股股东户数",
        "description": "统一股东户数观察日期、披露日期和变化指标。",
    },
    {
        "method": "GET",
        "path": "/api/v1/data/canonical/equity-business-segments",
        "name": "规范 A 股主营构成",
        "description": "按明确报告期统一业务、行业、产品和地区主营构成。",
    },
    {
        "method": "GET",
        "path": "/api/v1/data/canonical/equity-shareholders",
        "name": "规范 A 股主要股东",
        "description": "按季度末统一前十大股东、流通股东及持股变化。",
    },
    {
        "method": "GET",
        "path": "/api/v1/data/canonical/equity-restricted-releases",
        "name": "规范 A 股限售解禁",
        "description": "统一解禁日期、数量、占比与股东信息。",
    },
    {
        "method": "GET",
        "path": "/api/v1/data/canonical/equity-pledges",
        "name": "规范 A 股股权质押",
        "description": "统一股权质押冻结事件、规模、比例和解除状态。",
    },
    {
        "method": "GET",
        "path": "/api/v1/data/canonical/equity-risk-alerts",
        "name": "规范 A 股风险警示",
        "description": "统一 ST、退市等风险警示状态、原因及生效撤销日期。",
    },
    {
        "method": "GET",
        "path": "/api/v1/data/canonical/equity-suspensions",
        "name": "规范 A 股停复牌",
        "description": "统一停牌日期、时段、原因与复牌信息。",
    },
    {
        "method": "GET",
        "path": "/api/v1/data/canonical/fund-profiles",
        "name": "规范基金档案",
        "description": "统一基金身份、费用率和最低申购金额单位。",
    },
    {
        "method": "GET",
        "path": "/api/v1/data/canonical/fund-nav",
        "name": "规范基金净值",
        "description": "统一基金净值与收益率口径，不套用股票交易日历。",
    },
    {
        "method": "GET",
        "path": "/api/v1/data/canonical/fund-stock-holdings",
        "name": "规范基金股票持仓",
        "description": "按基金和季度末提供带范围声明的统一持仓模型。",
    },
    {
        "method": "GET",
        "path": "/api/v1/data/canonical/fund-dividends",
        "name": "规范基金分红",
        "description": "统一基金除息、登记、派息日期和每份现金分红。",
    },
    {
        "method": "GET",
        "path": "/api/v1/data/canonical/fund-managers",
        "name": "规范基金经理",
        "description": "统一基金经理任职区间、任期回报与履历。",
    },
    {
        "method": "GET",
        "path": "/api/v1/data/canonical/index-profiles",
        "name": "规范指数档案",
        "description": "统一指数名称、发布机构、基日、基点和币种。",
    },
    {
        "method": "GET",
        "path": "/api/v1/data/canonical/index-constituents",
        "name": "规范指数成分权重",
        "description": "按明确更新日期统一指数成分证券和权重。",
    },
)


STANDARD_ENDPOINTS = (
    {
        "method": "GET",
        "path": "/api/v1/data/datasets",
        "name": "数据集目录",
        "description": "发现已登记的标准化数据资产。",
    },
    {
        "method": "GET",
        "path": "/api/v1/data/datasets/{dataset_name}",
        "name": "数据集契约",
        "description": "查看字段、业务主键、日期和过滤能力。",
    },
    {
        "method": "GET",
        "path": "/api/v1/data/datasets/{dataset_name}/records",
        "name": "标准记录查询",
        "description": "按字段、日期范围和历史时点查询强类型记录。",
    },
    {
        "method": "GET",
        "path": "/api/v1/data/interfaces",
        "name": "上游映射",
        "description": "查看 Tushare 接口到标准数据集的实现映射。",
    },
    {
        "method": "GET",
        "path": "/api/v1/data/interfaces/{api_name}/records",
        "name": "通用接口标准查询",
        "description": "查询契约通用采集器产生的强类型标准记录。",
    },
    {
        "method": "GET",
        "path": "/api/v1/data/freshness",
        "name": "时效状态",
        "description": "查看数据集最新日期与时效判定。",
    },
    *CANONICAL_ENDPOINTS,
)

RESEARCH_ENDPOINTS = (
    *DERIVED_ENDPOINTS,
    {
        "method": "GET", "path": "/api/v1/research/factors/catalog",
        "name": "统一研究特征目录", "domain": "量化研究",
        "description": "正式特征身份、11类用途、唯一来源、别名和可用性；不供给内部对照值。",
    },
    {
        "method": "GET", "path": "/api/v1/research/factors/{ts_code}",
        "name": "日频研究特征", "domain": "量化研究",
        "description": "按名称选择已存储的因子及技术指标；共用值仅一个位置，缺失不回退供应商。",
    },
    {
        "method": "GET",
        "path": "/api/v1/research/stocks/{ts_code}/snapshot",
        "name": "个股快照",
        "description": "组合基础信息、行情、估值、资金流和财务指标。",
        "domain": "个股研究",
    },
    {
        "method": "GET",
        "path": "/api/v1/research/stocks/{ts_code}/research-pack",
        "name": "个股研究包",
        "description": "返回时点安全的历史行情、财务和基准比较研究上下文。",
        "domain": "个股研究",
    },
    {
        "method": "GET",
        "path": "/api/v1/research/stocks/{ts_code}/sectors",
        "name": "股票所属板块",
        "description": "发现股票在 THS、DC、TDX 体系中的板块归属。",
        "domain": "关系发现",
    },
    {
        "method": "GET",
        "path": "/api/v1/research/stocks/{ts_code}/peers",
        "name": "同行发现",
        "description": "通过共同板块发现可比较股票，并保留来源证据。",
        "domain": "关系发现",
    },
    {
        "method": "GET",
        "path": "/api/v1/research/sectors",
        "name": "板块搜索",
        "description": "跨供应商发现和筛选行业、概念及主题板块。",
        "domain": "板块研究",
    },
    {
        "method": "GET",
        "path": "/api/v1/research/sectors/{provider}/{sector_code}/snapshot",
        "name": "板块快照",
        "description": "组合板块资料、行情、成分和资金流状态。",
        "domain": "板块研究",
    },
    {
        "method": "GET",
        "path": "/api/v1/research/sectors/{provider}/{sector_code}/members",
        "name": "板块成分",
        "description": "按历史时点读取板块成分股。",
        "domain": "板块研究",
    },
    {
        "method": "GET",
        "path": "/api/v1/research/sectors/{provider}/{sector_code}/research-pack",
        "name": "板块研究包",
        "description": "返回板块趋势、资金流、成分与研究上下文。",
        "domain": "板块研究",
    },
    {
        "method": "GET",
        "path": "/api/v1/research/investment-calendar",
        "name": "投资日历范围",
        "description": "查询宏观数据、政策事件和衍生品交割安排。",
        "domain": "事件研究",
    },
    {
        "method": "GET",
        "path": "/api/v1/research/investment-calendar/{event_date}",
        "name": "单日投资事件",
        "description": "查看指定日期的重要投资事件和发布结果。",
        "domain": "事件研究",
    },
)

OPERATIONS_ENDPOINTS = (
    {
        "method": "GET",
        "path": "/api/v1/ops/orchestration-v2/summary",
        "name": "V2 编排总览",
        "description": "查看 V2 任务定义、执行实例与数据状态。",
    },
    {
        "method": "GET",
        "path": "/api/v1/ops/orchestration-v2/executions",
        "name": "执行实例",
        "description": "分页筛选 V2 执行实例、节点、重试和失败原因。",
    },
    {
        "method": "GET",
        "path": "/api/v1/ops/orchestration-v2/data-calendar",
        "name": "数据日历",
        "description": "按数据日期查看预期数据集的业务完整性，而不是任务创建日期。",
    },
    {
        "method": "GET",
        "path": "/api/v1/ops/data-health",
        "name": "数据健康",
        "description": "查看时效、完整性和待修复数据资产。",
    },
    {
        "method": "GET",
        "path": "/api/v1/ops/initialization",
        "name": "初始化与历史补采",
        "description": "查看安装后的历史初始化阶段和进度。",
    },
    {
        "method": "GET",
        "path": "/api/v1/ops/coverage",
        "name": "日期覆盖",
        "description": "查看日期或报告期完整性证据。",
    },
    {
        "method": "GET",
        "path": "/api/v1/ops/health/ready",
        "name": "服务就绪状态",
        "description": "检查 API 与 PostgreSQL 是否可以正常提供服务。",
    },
)


def _audiences() -> list[dict[str, Any]]:
    return [
        {
            "id": "research",
            "title": "研究接口",
            "audience": "研究者与 Agent",
            "description": "Agent 唯一公开入口；返回可直接用于基本面、技术面、板块和事件研究的语义对象。",
            "entrypoint": "/api/v1/research/capabilities",
            "path_prefixes": ["/api/v1/research"],
            "priority": 1,
        },
        {
            "id": "data",
            "title": "数据接口",
            "audience": "数据工程与公式维护",
            "description": "稳定数据集契约、上游映射、过滤、分页和历史时点查询。",
            "entrypoint": "/api/v1/data/datasets",
            "path_prefixes": ["/api/v1/data"],
            "priority": 2,
        },
        {
            "id": "operations",
            "title": "运营接口",
            "audience": "控制台与管理员",
            "description": "任务编排、执行实例、异常、数据日历、覆盖审计和初始化。",
            "entrypoint": "/api/v1/ops/orchestration-v2/summary",
            "path_prefixes": ["/api/v1/ops"],
            "priority": 3,
        },
        {
            "id": "audit",
            "title": "审计接口",
            "audience": "排障和数据治理",
            "description": "无损原始响应、请求账本、血缘与标准化漂移；不作为研究默认入口。",
            "entrypoint": "/api/v1/audit/raw/interfaces",
            "path_prefixes": ["/api/v1/audit"],
            "priority": 4,
        },
    ]


def build_data_service_catalog(
    *,
    raw_interfaces: list[dict[str, Any]],
    datasets: list[dict[str, Any]],
    interfaces: list[dict[str, Any]],
    dataset_columns: dict[str, list[dict]] | None = None,
) -> dict[str, Any]:
    """Build one truthful view without coupling the dashboard to registries."""

    dataset_sources = {
        item["name"]: list(item.get("source_ids") or ["tushare"])
        for item in datasets
    }
    columns_by_table = dataset_columns or {}

    raw_endpoints = [
        {
            **item,
            "data_origin": "tushare_raw",
            "local_datasets": [],
            "upstream_sources": ["tushare"],
            "fallback_routes": [],
            "derivation": None,
            "read_strategy": "audit_only",
            "dependency_scope": "request_selected_interface",
            "runtime_external_query": False,
            "lineage_status": "complete",
            "category": _normalize_category("raw", None),
        }
        for item in RAW_ENDPOINTS
    ]
    standard_endpoints: list[dict[str, Any]] = []
    for item in STANDARD_ENDPOINTS:
        lineage = CANONICAL_ENDPOINT_LINEAGE.get(item["path"])
        if lineage is not None:
            standard_endpoints.append(
                {
                    **endpoint_with_sources(item, lineage, dataset_sources),
                    "category": _normalize_category("standard", None),
                }
            )
            continue
        if item["path"] == "/api/v1/data/interfaces":
            scope = "all_registered_upstream_interfaces"
        elif "{api_name}" in item["path"]:
            scope = "request_selected_interface"
        elif item["path"] == "/api/v1/data/freshness":
            scope = "all_or_request_selected_dataset"
        else:
            scope = "request_selected_dataset"
        standard_endpoints.append(
            {
                **item,
                "data_origin": "canonical_db",
                "local_datasets": [],
                "upstream_sources": sorted(
                    {source for values in dataset_sources.values() for source in values}
                ),
                "fallback_routes": [],
                "derivation": None,
                "read_strategy": "local_db_first",
                "dependency_scope": scope,
                "runtime_external_query": False,
                "lineage_status": "complete",
                "category": _normalize_category("standard", None),
            }
        )

    observed = sum(bool(item.get("request_count")) for item in raw_interfaces)
    with_records = sum(bool(item.get("has_records")) for item in raw_interfaces)
    with_failures = sum(bool(item.get("failed_requests")) for item in raw_interfaces)
    dated = sum(bool(item.get("date_column")) for item in datasets)
    mapped = sum(bool(item.get("datasets")) for item in interfaces)
    directly_queryable = sum(bool(item.get("records_url")) for item in interfaces)

    research_items = [
        {
            **endpoint_with_sources(
                {**item, "status": "available"},
                research_endpoint_lineage(item["path"]),
                dataset_sources,
            ),
            "category": _normalize_category("research", item.get("domain")),
        }
        for item in RESEARCH_ENDPOINTS
    ]
    name_to_columns = {
        item["name"]: columns_by_table.get(item.get("table"), [])
        for item in datasets
    }
    for endpoint in research_items:
        local = endpoint.get("local_datasets") or []
        fields: list[dict] = []
        seen: set[str] = set()
        for name in local:
            for column in name_to_columns.get(name, []):
                if column["name"] not in seen:
                    seen.add(column["name"])
                    fields.append(column)
        endpoint["fields"] = fields
    layers = [
        {
            "id": "raw",
            "order": 1,
            "title": "原始审计层",
            "short_title": "可追责事实",
            "description": "保存每一次上游请求和无损响应，用于排障、回放、血缘与契约升级。",
            "usage_guidance": "仅在审计和排障时使用；研究代码不要直接解析原始 JSON。",
            "status": "operational",
            "coverage_note": "历史专项采集的原文无法倒推，部署统一审计后覆盖会随采集持续增长。",
            "metrics": {
                "interfaces": len(raw_interfaces),
                "observed_interfaces": observed,
                "interfaces_with_records": with_records,
                "interfaces_with_failed_requests": with_failures,
            },
            "endpoints": raw_endpoints,
            "items": raw_interfaces,
        },
        {
            "id": "standard",
            "order": 2,
            "title": "标准数据层",
            "short_title": "稳定数据契约",
            "description": "将上游数据标准化为强类型数据集，提供字段、主键、日期、过滤和分页契约。",
            "usage_guidance": "供数据工程和公式维护复核输入；不属于公开 Agent 契约。",
            "status": "operational",
            "coverage_note": "数据集是否完整由时效与日期覆盖审计判定，登记成功不等于历史数据完整。",
            "metrics": {
                "datasets": len(datasets),
                "dated_datasets": dated,
                "mapped_interfaces": mapped,
                "direct_interface_queries": directly_queryable,
                "canonical_endpoints": len(CANONICAL_ENDPOINTS),
            },
            "endpoints": standard_endpoints,
            "items": [
                {**item, "columns": columns_by_table.get(item.get("table"), [])}
                for item in datasets
            ],
        },
        {
            "id": "research",
            "order": 3,
            "title": "研究就绪层",
            "short_title": "可直接研究",
            "description": "组合多个标准数据集，向个人研究和 Agent 提供个股、板块与事件语义对象。",
            "usage_guidance": "研究者与 Agent 的唯一公开业务入口；底层复核由维护者完成。",
            "status": "operational",
            "coverage_note": "当前覆盖个股、板块和投资事件，因子、回测与组合研究属于后续独立系统。",
            "metrics": {
                "endpoints": len(research_items),
                "available_endpoints": len(research_items),
                "domains": len({item["domain"] for item in research_items}),
            },
            "endpoints": research_items,
            "items": research_items,
        },
    ]
    return {
        "generated_at": datetime.now(timezone.utc),
        "recommended_entrypoint": "/api/v1/research/capabilities",
        "audiences": _audiences(),
        "control_plane": {
            "id": "operations",
            "title": "运营控制面",
            "description": "运营接口管理数据生产过程，不属于原始→标准→研究的数据加工层。",
            "endpoints": list(OPERATIONS_ENDPOINTS),
        },
        "summary": {
            "layers": len(layers),
            "raw_interfaces": len(raw_interfaces),
            "standard_datasets": len(datasets),
            "research_endpoints": len(research_items),
        },
        "layers": layers,
    }
