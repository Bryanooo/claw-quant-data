"""Public catalog for agent-oriented research capabilities."""

from __future__ import annotations

from typing import Any


DERIVED_ENDPOINTS: tuple[dict[str, Any], ...] = (
    {
        "method": "GET",
        "path": "/api/v1/research/capabilities",
        "name": "研究能力目录",
        "domain": "能力发现",
        "description": "列出研究能力、数据动作、服务状态和待办缺口。",
    },
    {
        "method": "GET",
        "path": "/api/v1/research/stocks/{ts_code}/fundamentals",
        "name": "基本面分析",
        "domain": "个股研究",
        "description": "多期财务趋势、盈利、成长、杜邦、现金质量、偿债和营运效率。",
    },
    {
        "method": "GET",
        "path": "/api/v1/research/stocks/{ts_code}/valuation",
        "name": "估值分析",
        "domain": "个股研究",
        "description": "历史估值分位、同行对比及 DCF/DDM 输入数据。",
    },
    {
        "method": "GET",
        "path": "/api/v1/research/stocks/{ts_code}/technicals",
        "name": "技术面分析",
        "domain": "个股研究",
        "description": "趋势、动量、波动、量价、突破、相对强弱和复权收益。",
    },
    {
        "method": "GET",
        "path": "/api/v1/research/stocks/{ts_code}/capital-flow",
        "name": "资金与筹码",
        "domain": "个股研究",
        "description": "主力资金、两融、北向、大宗交易和筹码状态。",
    },
    {
        "method": "GET",
        "path": "/api/v1/research/stocks/{ts_code}/event-study",
        "name": "事件研究",
        "domain": "事件研究",
        "description": "计算事件窗口内个股、基准和累计异常收益。",
    },
    {
        "method": "GET",
        "path": "/api/v1/research/market/breadth",
        "name": "市场宽度",
        "domain": "市场研究",
        "description": "涨跌分布、成交、均线扩散和涨跌停情绪。",
    },
    {
        "method": "GET",
        "path": "/api/v1/research/sectors/{provider}/rotation",
        "name": "板块轮动",
        "domain": "板块研究",
        "description": "按多窗口收益和成交活跃度识别板块强弱。",
    },
)


BACKFILL_WORKSTREAMS: tuple[dict[str, Any], ...] = (
    {
        "id": "analyst-consensus-history",
        "group": "analyst",
        "name": "卖方一致预期历史",
        "interfaces": ["report_rc"],
        "status": "planned",
        "reason": "当前记录仅覆盖 2026-08-28 以后，不能形成可靠修正序列。",
    },
    {
        "id": "ownership-history",
        "group": "ownership",
        "name": "股东与机构持仓历史",
        "interfaces": [
            "top10_holders", "top10_floatholders", "fund_portfolio",
            "hk_hold", "stk_holdertrade", "stk_holdernumber",
        ],
        "status": "planned",
        "reason": "多项数据只有最近一期或最近数周。",
    },
    {
        "id": "shareholder-return-history",
        "group": "shareholder-return",
        "name": "分红回购与解禁历史",
        "interfaces": ["dividend", "repurchase", "share_float"],
        "status": "planned",
        "reason": "当前分红和回购历史不足以计算长期总股东回报。",
    },
    {
        "id": "chip-distribution-history",
        "group": "chips",
        "name": "筹码分布历史",
        "interfaces": ["cyq_chips", "cyq_perf"],
        "status": "planned",
        "reason": "当前只覆盖 2026-08-06 至 2026-09-04。",
    },
    {
        "id": "intraday-history",
        "group": "intraday",
        "name": "分钟行情历史",
        "interfaces": ["stk_mins"],
        "status": "constrained",
        "reason": "接口已实现且有权限，但当前 Token 仅允许每天 2 次请求。",
    },
)


NEW_SOURCE_TODOS: tuple[dict[str, Any], ...] = (
    {
        "id": "official-announcements",
        "name": "交易所与公司公告全文",
        "status": "todo",
        "required_for": ["公告证据", "治理风险", "诉讼与监管事件"],
        "acceptance": "支持原文、发布日期、证券实体、文档类型、去重哈希和可引用段落。",
    },
    {
        "id": "news-and-sentiment",
        "name": "持续新闻与舆情数据源",
        "status": "todo",
        "required_for": ["事件检测", "情绪分析", "新闻冲击"],
        "acceptance": "覆盖稳定、来源可追踪、正文可检索，并能按证券和事件去重绑定。",
    },
    {
        "id": "level2-microstructure",
        "name": "逐笔成交与 Level-2 盘口",
        "status": "todo",
        "required_for": ["微观结构", "订单失衡", "冲击成本"],
        "acceptance": "明确授权、交易时序、盘口档位、逐笔身份和可恢复的高频存储。",
    },
)


def capability_catalog(
    backfill_statuses: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    backfills = []
    for configured in BACKFILL_WORKSTREAMS:
        item = dict(configured)
        runtime = (backfill_statuses or {}).get(item["group"])
        if runtime:
            item.update(runtime)
        backfills.append(item)
    return {
        "summary": {
            "core_techniques": 35,
            "available_or_derivable": 27,
            "backfill_workstreams": len(BACKFILL_WORKSTREAMS),
            "new_source_todos": len(NEW_SOURCE_TODOS),
            "derived_endpoints": len(DERIVED_ENDPOINTS) - 1,
        },
        "api_namespace": {
            "path": "/api/v1/research",
            "reason": (
                "derived research contracts have calculation semantics and quality "
                "evidence, unlike raw and standard dataset queries"
            ),
            "compatibility": "existing /api/v1/stocks and /api/v1/sectors routes remain unchanged",
        },
        "derived_services": list(DERIVED_ENDPOINTS),
        "backfills": backfills,
        "new_source_todos": list(NEW_SOURCE_TODOS),
    }
