"""Machine-readable catalog for the three public data-service layers."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


RAW_ENDPOINTS = (
    {
        "method": "GET",
        "path": "/api/v1/raw/interfaces",
        "name": "原始审计覆盖",
        "description": "查看可采接口的请求、失败和原始记录覆盖。",
    },
    {
        "method": "GET",
        "path": "/api/v1/raw/{api_name}/requests",
        "name": "上游请求账本",
        "description": "分页查看真实 Tushare 请求参数与传输结果。",
    },
    {
        "method": "GET",
        "path": "/api/v1/raw/{api_name}/records",
        "name": "原始记录",
        "description": "查询无损 JSONB 原文及其请求身份。",
    },
    {
        "method": "GET",
        "path": "/api/v1/raw/{api_name}/coverage",
        "name": "接口审计摘要",
        "description": "查看单个接口的请求和记录覆盖摘要。",
    },
    {
        "method": "GET",
        "path": "/api/v1/raw/{api_name}/lineage/{record_hash}",
        "name": "原始血缘",
        "description": "从一条原始记录追溯产生它的逻辑请求。",
    },
)

STANDARD_ENDPOINTS = (
    {
        "method": "GET",
        "path": "/api/v1/datasets",
        "name": "数据集目录",
        "description": "发现已登记的标准化数据资产。",
    },
    {
        "method": "GET",
        "path": "/api/v1/datasets/{dataset_name}",
        "name": "数据集契约",
        "description": "查看字段、业务主键、日期和过滤能力。",
    },
    {
        "method": "GET",
        "path": "/api/v1/datasets/{dataset_name}/records",
        "name": "标准记录查询",
        "description": "按字段、日期范围和历史时点查询强类型记录。",
    },
    {
        "method": "GET",
        "path": "/api/v1/interfaces",
        "name": "上游映射",
        "description": "查看 Tushare 接口到标准数据集的实现映射。",
    },
    {
        "method": "GET",
        "path": "/api/v1/interfaces/{api_name}/records",
        "name": "通用接口标准查询",
        "description": "查询契约通用采集器产生的强类型标准记录。",
    },
    {
        "method": "GET",
        "path": "/api/v1/freshness",
        "name": "时效状态",
        "description": "查看数据集最新日期与时效判定。",
    },
    {
        "method": "GET",
        "path": "/api/v1/coverage",
        "name": "日期覆盖",
        "description": "查看日期或报告期完整性证据。",
    },
)

RESEARCH_ENDPOINTS = (
    {
        "method": "GET",
        "path": "/api/v1/stocks/{ts_code}/snapshot",
        "name": "个股快照",
        "description": "组合基础信息、行情、估值、资金流和财务指标。",
        "domain": "个股研究",
    },
    {
        "method": "GET",
        "path": "/api/v1/stocks/{ts_code}/research-pack",
        "name": "个股研究包",
        "description": "返回时点安全的历史行情、财务和基准比较研究上下文。",
        "domain": "个股研究",
    },
    {
        "method": "GET",
        "path": "/api/v1/stocks/{ts_code}/sectors",
        "name": "股票所属板块",
        "description": "发现股票在 THS、DC、TDX 体系中的板块归属。",
        "domain": "关系发现",
    },
    {
        "method": "GET",
        "path": "/api/v1/stocks/{ts_code}/peers",
        "name": "同行发现",
        "description": "通过共同板块发现可比较股票，并保留来源证据。",
        "domain": "关系发现",
    },
    {
        "method": "GET",
        "path": "/api/v1/sectors",
        "name": "板块搜索",
        "description": "跨供应商发现和筛选行业、概念及主题板块。",
        "domain": "板块研究",
    },
    {
        "method": "GET",
        "path": "/api/v1/sectors/{provider}/{sector_code}/snapshot",
        "name": "板块快照",
        "description": "组合板块资料、行情、成分和资金流状态。",
        "domain": "板块研究",
    },
    {
        "method": "GET",
        "path": "/api/v1/sectors/{provider}/{sector_code}/members",
        "name": "板块成分",
        "description": "按历史时点读取板块成分股。",
        "domain": "板块研究",
    },
    {
        "method": "GET",
        "path": "/api/v1/sectors/{provider}/{sector_code}/research-pack",
        "name": "板块研究包",
        "description": "返回板块趋势、资金流、成分与研究上下文。",
        "domain": "板块研究",
    },
    {
        "method": "GET",
        "path": "/api/v1/investment-calendar",
        "name": "投资日历范围",
        "description": "查询宏观数据、政策事件和衍生品交割安排。",
        "domain": "事件研究",
    },
    {
        "method": "GET",
        "path": "/api/v1/investment-calendar/{event_date}",
        "name": "单日投资事件",
        "description": "查看指定日期的重要投资事件和发布结果。",
        "domain": "事件研究",
    },
)


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
            "usage_guidance": "Agent 和研究代码的默认查询入口。",
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
            "usage_guidance": "优先用于股票/板块研究；需要底层字段时再下钻标准层。",
            "status": "operational",
            "coverage_note": "当前覆盖个股、板块和投资事件，因子、回测与组合研究属于后续独立系统。",
            "metrics": {
                "capabilities": len(research_items),
                "available_capabilities": len(research_items),
                "domains": len({item["domain"] for item in research_items}),
            },
            "endpoints": research_items,
            "items": research_items,
        },
    ]
    return {
        "generated_at": datetime.now(timezone.utc),
        "summary": {
            "layers": len(layers),
            "raw_interfaces": len(raw_interfaces),
            "standard_datasets": len(datasets),
            "research_capabilities": len(research_items),
        },
        "layers": layers,
    }
