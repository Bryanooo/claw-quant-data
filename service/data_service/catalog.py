"""Machine-readable catalog for the public API namespaces and data layers."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from service.research.catalog import DERIVED_ENDPOINTS


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
)

RESEARCH_ENDPOINTS = (
    *DERIVED_ENDPOINTS,
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
        "path": "/api/v1/ops/collection-overview",
        "name": "采集运营总览",
        "description": "查看活动任务、真实未恢复异常和当前采集吞吐。",
    },
    {
        "method": "GET",
        "path": "/api/v1/ops/collection-jobs",
        "name": "执行实例",
        "description": "分页筛选持久化任务实例及其尝试、重试和恢复关系。",
    },
    {
        "method": "GET",
        "path": "/api/v1/ops/delivery/data-calendar",
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
            "entrypoint": "/api/v1/ops/collection-overview",
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
) -> dict[str, Any]:
    """Build one truthful view without coupling the dashboard to registries."""

    observed = sum(bool(item.get("request_count")) for item in raw_interfaces)
    with_records = sum(bool(item.get("has_records")) for item in raw_interfaces)
    with_failures = sum(bool(item.get("failed_requests")) for item in raw_interfaces)
    dated = sum(bool(item.get("date_column")) for item in datasets)
    mapped = sum(bool(item.get("datasets")) for item in interfaces)
    directly_queryable = sum(bool(item.get("records_url")) for item in interfaces)

    research_items = [
        {**item, "status": "available"}
        for item in RESEARCH_ENDPOINTS
    ]
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
            "endpoints": list(RAW_ENDPOINTS),
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
            },
            "endpoints": list(STANDARD_ENDPOINTS),
            "items": datasets,
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
