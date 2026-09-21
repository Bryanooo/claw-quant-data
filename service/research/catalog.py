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
        "path": "/api/v1/research/readiness",
        "name": "研究数据就绪状态",
        "domain": "质量与可用性",
        "description": "提供 Agent 可直接判断的时效、覆盖、失败和历史初始化摘要。",
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
        "description": "K线与形态、趋势、动量、量价、关键价位、波浪候选、相对强弱和图表序列。",
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
        "path": "/api/v1/research/stocks/{ts_code}/repurchase-progress",
        "name": "回购进展",
        "domain": "股东回报",
        "description": "对齐回购方案、最新累计实施进度、执行均价与公告后市场表现。",
    },
    {
        "method": "GET",
        "path": "/api/v1/research/instruments/{asset_type}/{code}/technicals",
        "name": "多资产技术面",
        "domain": "跨资产研究",
        "description": "股票、指数、ETF、同花顺板块与上金所现货的日/周/月技术面及长期趋势。",
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


# This is a deliberately bounded v1 research baseline, not a claim that eight
# HTTP routes exhaust every possible investment-research method.  One route is
# a cohesive resource that exposes several stable calculations.  Keeping the
# individual techniques explicit prevents a route count from being mistaken
# for capability coverage and makes every remaining gap auditable.
SERVED_TECHNIQUES: tuple[dict[str, Any], ...] = (
    # Fundamentals (8)
    {"id": "financial-trend", "name": "多期财务趋势", "domain": "基本面", "endpoint": "fundamentals"},
    {"id": "profitability", "name": "盈利能力", "domain": "基本面", "endpoint": "fundamentals"},
    {"id": "growth", "name": "成长能力", "domain": "基本面", "endpoint": "fundamentals"},
    {"id": "dupont", "name": "杜邦分解", "domain": "基本面", "endpoint": "fundamentals"},
    {"id": "cash-quality", "name": "现金流与利润质量", "domain": "基本面", "endpoint": "fundamentals"},
    {"id": "solvency", "name": "偿债能力", "domain": "基本面", "endpoint": "fundamentals"},
    {"id": "operating-efficiency", "name": "营运效率", "domain": "基本面", "endpoint": "fundamentals"},
    {"id": "business-segments", "name": "主营构成", "domain": "基本面", "endpoint": "fundamentals"},
    # Valuation (3)
    {"id": "valuation-history", "name": "历史估值分位", "domain": "估值", "endpoint": "valuation"},
    {"id": "peer-valuation", "name": "同行估值对比", "domain": "估值", "endpoint": "valuation"},
    {"id": "valuation-inputs", "name": "DCF/DDM 输入事实", "domain": "估值", "endpoint": "valuation"},
    # Technical and risk (28)
    {"id": "candlestick-chart", "name": "K线与图表序列", "domain": "技术面", "endpoint": "technicals"},
    {"id": "candlestick-patterns", "name": "K线形态识别", "domain": "技术面", "endpoint": "technicals"},
    {"id": "trend", "name": "趋势与均线", "domain": "技术面", "endpoint": "technicals"},
    {"id": "momentum", "name": "MACD/RSI 动量", "domain": "技术面", "endpoint": "technicals"},
    {"id": "oscillators", "name": "KDJ/CCI/Williams/MFI", "domain": "技术面", "endpoint": "technicals"},
    {"id": "trend-strength", "name": "ADX/DMI 趋势强度", "domain": "技术面", "endpoint": "technicals"},
    {"id": "volatility", "name": "ATR/布林波动", "domain": "技术面", "endpoint": "technicals"},
    {"id": "volume-price", "name": "量价关系", "domain": "技术面", "endpoint": "technicals"},
    {"id": "breakout-levels", "name": "可解释支撑压力", "domain": "技术面", "endpoint": "technicals"},
    {"id": "wave-candidates", "name": "波浪候选与失效条件", "domain": "技术面", "endpoint": "technicals"},
    {"id": "bull-bear-lines", "name": "牛熊线与加权趋势线", "domain": "技术面", "endpoint": "technicals"},
    {"id": "relative-strength", "name": "相对强弱", "domain": "技术面", "endpoint": "technicals"},
    {"id": "adjusted-return", "name": "复权收益", "domain": "技术面", "endpoint": "technicals"},
    {"id": "drawdown-risk", "name": "回撤风险", "domain": "技术面", "endpoint": "technicals"},
    {"id": "multi-timeframe", "name": "日周月多周期与年度长期趋势", "domain": "技术面", "endpoint": "technicals"},
    {"id": "pivot-systems", "name": "Classic/Fibonacci/Woodie/Camarilla/DeMark/CPR枢轴", "domain": "技术面", "endpoint": "technicals"},
    {"id": "fibonacci-retracement", "name": "确认波段斐波那契回撤与扩展", "domain": "技术面", "endpoint": "technicals"},
    {"id": "chan-structure", "name": "缠论分型、笔、线段候选与中枢", "domain": "技术面", "endpoint": "technicals"},
    {"id": "chan-divergence", "name": "缠论背驰与一二三类买卖点候选", "domain": "技术面", "endpoint": "technicals"},
    {"id": "ichimoku", "name": "一目均衡表", "domain": "技术面", "endpoint": "technicals"},
    {"id": "donchian", "name": "唐奇安通道与突破", "domain": "技术面", "endpoint": "technicals"},
    {"id": "supertrend", "name": "Supertrend趋势系统", "domain": "技术面", "endpoint": "technicals"},
    {"id": "stochastic-rsi", "name": "StochRSI动量", "domain": "技术面", "endpoint": "technicals"},
    {"id": "chaikin-money-flow", "name": "Chaikin资金流", "domain": "技术面", "endpoint": "technicals"},
    {"id": "aroon-psar", "name": "Aroon与Parabolic SAR趋势系统", "domain": "技术面", "endpoint": "technicals"},
    {"id": "price-gaps", "name": "价格缺口与回补状态", "domain": "技术面", "endpoint": "technicals"},
    {"id": "downside-risk", "name": "下行波动、历史VaR与Expected Shortfall", "domain": "风险", "endpoint": "technicals"},
    {"id": "benchmark-risk", "name": "Beta、相关性、Alpha、跟踪误差与信息比率", "domain": "风险", "endpoint": "technicals"},
    # Capital, event and market (8)
    {"id": "main-money-flow", "name": "主力资金流", "domain": "资金", "endpoint": "capital-flow"},
    {"id": "margin-financing", "name": "两融行为", "domain": "资金", "endpoint": "capital-flow"},
    {"id": "northbound-holdings", "name": "北向持仓", "domain": "资金", "endpoint": "capital-flow"},
    {"id": "block-trade", "name": "大宗交易", "domain": "资金", "endpoint": "capital-flow"},
    {"id": "chip-distribution", "name": "筹码分布", "domain": "资金", "endpoint": "capital-flow"},
    {"id": "event-study", "name": "事件窗口异常收益", "domain": "事件", "endpoint": "event-study"},
    {"id": "market-breadth", "name": "市场宽度", "domain": "市场", "endpoint": "market-breadth"},
    {"id": "sector-rotation", "name": "板块轮动", "domain": "板块", "endpoint": "sector-rotation"},
    {"id": "repurchase-progress", "name": "回购累计进展与市场反应", "domain": "股东回报", "endpoint": "repurchase-progress"},
)


GAP_TECHNIQUES: tuple[dict[str, Any], ...] = (
    {"id": "analyst-revisions", "name": "一致预期与盈利修正", "domain": "基本面", "status": "planned", "action": "backfill", "workstream": "analyst"},
    {"id": "ownership-behavior", "name": "股东与机构行为", "domain": "基本面", "status": "planned", "action": "backfill", "workstream": "ownership"},
    {"id": "shareholder-return", "name": "总股东回报", "domain": "基本面", "status": "planned", "action": "backfill", "workstream": "shareholder-return"},
    {"id": "announcement-evidence", "name": "公告原文证据", "domain": "事件", "status": "missing", "action": "new_source", "source_todo": "official-announcements"},
    {"id": "governance-risk", "name": "治理、诉讼与监管风险", "domain": "基本面", "status": "missing", "action": "new_source", "source_todo": "official-announcements"},
    {"id": "news-events", "name": "新闻事件检测", "domain": "事件", "status": "partial", "action": "derive_and_source", "source_todo": "news-and-sentiment"},
    {"id": "news-sentiment", "name": "情绪与新闻冲击", "domain": "事件", "status": "partial", "action": "derive_and_source", "source_todo": "news-and-sentiment"},
    {"id": "market-microstructure", "name": "订单失衡与冲击成本", "domain": "微观结构", "status": "constrained", "action": "new_source", "source_todo": "level2-microstructure"},
)


BACKFILL_WORKSTREAMS: tuple[dict[str, Any], ...] = (
    {
        "id": "news-history",
        "group": "news",
        "name": "多来源新闻历史",
        "interfaces": ["major_news"],
        "status": "planned",
        "reason": "旧策略没有按新闻来源扇出，历史记录仅覆盖新浪财经的少量日期。",
    },
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
        "status": "partial",
        "required_for": ["事件检测", "情绪分析", "新闻冲击"],
        "acceptance": "major_news 多来源历史完成后仍需证券实体绑定、事件去重和情绪派生；快讯需另行取得合法数据源。",
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
            "baseline_techniques": len(SERVED_TECHNIQUES) + len(GAP_TECHNIQUES),
            "currently_served": len(SERVED_TECHNIQUES),
            "planned_from_existing_sources": sum(
                item["action"] == "backfill" for item in GAP_TECHNIQUES
            ),
            "external_or_constrained": sum(
                item["action"] != "backfill" for item in GAP_TECHNIQUES
            ),
            # Kept for clients that consumed the original fields. They now
            # mean the explicit v1 baseline and techniques served today.
            "core_techniques": len(SERVED_TECHNIQUES) + len(GAP_TECHNIQUES),
            "available_or_derivable": len(SERVED_TECHNIQUES),
            "backfill_workstreams": len(BACKFILL_WORKSTREAMS),
            "new_source_todos": len(NEW_SOURCE_TODOS),
            "agent_endpoints": len(DERIVED_ENDPOINTS),
            "derived_endpoints": sum(
                item["path"]
                not in {
                    "/api/v1/research/capabilities",
                    "/api/v1/research/readiness",
                }
                for item in DERIVED_ENDPOINTS
            ),
        },
        "api_namespace": {
            "path": "/api/v1/research",
            "reason": (
                "derived research contracts have calculation semantics and quality "
                "evidence, unlike raw and standard dataset queries"
            ),
        },
        "derived_services": list(DERIVED_ENDPOINTS),
        "techniques": {
            "scope": "claw-quant-data v1 baseline; not all possible research methods",
            "served": [dict(item, status="served") for item in SERVED_TECHNIQUES],
            "gaps": list(GAP_TECHNIQUES),
        },
        "backfills": backfills,
        "new_source_todos": list(NEW_SOURCE_TODOS),
    }
