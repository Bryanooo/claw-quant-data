"""Semantic mapping between Financial Data routes and Tushare contracts.

This module deliberately answers a different question from ``source_policy``.
``source_policy`` describes what claw-quant-data can serve *today* from its
canonical database.  This catalog describes whether the upstream Tushare
product can provide the same business fact, even when the current token has no
permission or claw-quant-data has not implemented the adapter yet.

The four classes are exhaustive and mutually exclusive.  A route is only
classified as direct/derived/announcement when Tushare can satisfy the whole
published Financial Data contract.  Partial market or field overlap remains
``financial_data_only`` and is recorded in ``related_tushare_interfaces``.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import json
from pathlib import Path

from service.source_connectors.financial_data_catalog import FINANCIAL_DATA_ROUTES


TUSHARE_DIRECT = "tushare_direct"
TUSHARE_DERIVED = "tushare_derived"
TUSHARE_ANNOUNCEMENT_PARSE = "tushare_announcement_parse"
FINANCIAL_DATA_ONLY = "financial_data_only"

EQUIVALENCE_CLASSES = (
    TUSHARE_DIRECT,
    TUSHARE_DERIVED,
    TUSHARE_ANNOUNCEMENT_PARSE,
    FINANCIAL_DATA_ONLY,
)


# Whole-contract direct equivalents.  Multiple interfaces mean that all listed
# markets or business slices are needed to cover the Financial Data contract.
DIRECT_EQUIVALENTS: dict[str, tuple[str, ...]] = {
    "/api/v1/common/symbol-by-cond": (
        "stock_basic", "hk_basic", "us_basic", "fund_basic", "index_basic",
        "sge_basic",
    ),
    "/api/v1/fund/dividend": ("fund_div",),
    "/api/v1/fund/fund-manager": ("fund_manager",),
    "/api/v1/fund/stock-portfolio": ("fund_portfolio",),
    "/api/v1/index_fnd/index-profile-basic-info": ("index_basic",),
    "/api/v1/sector/plate-component": (
        "ths_member", "dc_member", "tdx_member", "index_member_all",
    ),
    "/api/v1/sector/plate-list": (
        "ths_index", "dc_index", "tdx_index", "index_classify",
    ),
    "/api/v1/stock/block-trading-details": ("block_trade",),
    "/api/v1/stock/component-list-belonged": (
        "index_member_all", "ths_member", "dc_member", "tdx_member",
    ),
    "/api/v1/stock/daily-valuation-indicators": ("daily_basic",),
    "/api/v1/stock/risk-alerts": ("stk_alert", "stock_st", "st"),
    "/api/v1/stock/sc-activitie": ("hsgt_top10", "ggt_top10"),
    "/api/v1/stock/sh-hold-stat": ("hk_hold", "stock_hsgt"),
    "/api/v1/stock/suspend-resumption": ("suspend_d",),
    "/api/v1/stock/tra-variant": (
        "top_list", "top_inst", "stk_shock", "stk_high_shock",
    ),
    "/api/v1/stock_fnd/balance-sheet": (
        "balancesheet", "hk_balancesheet", "us_balancesheet",
    ),
    "/api/v1/stock_fnd/broker-golden-stocks": ("broker_recommend",),
    "/api/v1/stock_fnd/buyback-plans": ("repurchase",),
    "/api/v1/stock_fnd/growth-rates-acc": (
        "fina_indicator", "hk_fina_indicator", "us_fina_indicator",
    ),
    "/api/v1/stock_fnd/hk-intermediary-holdings": (
        "ccass_hold", "ccass_hold_detail",
    ),
    "/api/v1/stock_fnd/income-cashflow-acc": (
        "income", "cashflow", "hk_income", "hk_cashflow", "us_income",
        "us_cashflow",
    ),
    "/api/v1/stock_fnd/investor-relations": ("stk_surv",),
    "/api/v1/stock_fnd/performance-forecast": ("forecast",),
    "/api/v1/stock_fnd/prelim-acc": ("express",),
    "/api/v1/stock_fnd/prelim-balance": ("express",),
    "/api/v1/info/research-reports": ("research_report",),
}


# Whole-contract deterministic transformations over Tushare facts.  These are
# not provider-native equivalents: claw-quant-data must own and version the
# formula, joins, weights and as-of rules.
DERIVED_EQUIVALENTS: dict[str, tuple[str, ...]] = {
    "/api/v1/fund/fund-company-info": (
        "fund_company", "fund_basic", "fund_share",
    ),
    "/api/v1/fund/invest-industry": (
        "fund_portfolio", "stock_basic", "index_member_all",
    ),
    "/api/v1/fund/plate-fund-relevancy": (
        "fund_portfolio", "ths_member", "dc_member", "tdx_member",
    ),
    "/api/v1/fund/yield-rank": ("fund_nav", "fund_daily", "fund_basic"),
    "/api/v1/fund_derived/benchmark-excess": (
        "fund_nav", "fund_daily", "mkt_idx_bmk", "index_daily",
    ),
    "/api/v1/fund_derived/risk-return": (
        "fund_nav", "fund_daily", "index_daily",
    ),
    "/api/v1/index_fnd/index-fnd-estimates-summary": (
        "index_weight", "index_member_all", "report_rc",
    ),
    "/api/v1/index_fnd/index-fnd-financial-ratios": (
        "index_weight", "index_member_all", "fina_indicator", "income",
        "balancesheet",
    ),
    "/api/v1/index_fnd/index-fnd-financial-ratios-single": (
        "index_weight", "index_member_all", "fina_indicator", "income",
        "balancesheet",
    ),
    "/api/v1/index_fnd/index-fnd-financial-statement": (
        "index_weight", "index_member_all", "income", "balancesheet",
        "cashflow",
    ),
    "/api/v1/quote/kline-batch": (
        "daily", "weekly", "monthly", "stk_weekly_monthly",
        "hk_daily_adj", "us_daily_adj", "fund_daily", "index_daily",
        "index_weekly", "index_monthly", "tdx_daily", "sge_daily",
    ),
    "/api/v1/quote/capital-flow-range": (
        "moneyflow", "moneyflow_dc", "moneyflow_ths", "moneyflow_ind_dc",
        "moneyflow_ind_ths", "moneyflow_mkt_dc",
    ),
    "/api/v1/sector/plate-fund-relevancy": (
        "fund_portfolio", "ths_member", "dc_member", "tdx_member",
    ),
    "/api/v1/sector/sector-capital-flow": (
        "margin_detail", "index_member_all", "ths_member", "dc_member",
    ),
    "/api/v1/sector/sector-financial-cumulative": (
        "index_member_all", "ths_member", "dc_member", "income",
        "balancesheet", "cashflow", "fina_indicator",
    ),
    "/api/v1/sector/sector-financial-point": (
        "index_member_all", "ths_member", "dc_member", "balancesheet",
        "fina_indicator",
    ),
    "/api/v1/sector/sector-financial-quarterly": (
        "index_member_all", "ths_member", "dc_member", "income",
        "cashflow", "fina_indicator",
    ),
    "/api/v1/sector/sector-valuation": (
        "index_member_all", "ths_member", "dc_member", "daily_basic",
        "index_dailybasic",
    ),
    "/api/v1/stock/tech-patterns": (
        "daily", "adj_factor", "stk_factor_pro", "stk_nineturn",
    ),
    "/api/v1/stock/tech-indicators": (
        "daily", "adj_factor", "hk_daily_adj", "us_daily_adj",
        "stk_factor", "stk_factor_pro",
    ),
    "/api/v1/stock/sc-trade": ("moneyflow_hsgt", "ggt_daily"),
    "/api/v1/stock_fnd/growth-rates-quarter": (
        "income", "cashflow", "fina_indicator", "hk_income", "hk_cashflow",
        "hk_fina_indicator", "us_income", "us_cashflow", "us_fina_indicator",
    ),
    "/api/v1/stock_fnd/holding-stats": (
        "top10_holders", "top10_floatholders", "fund_portfolio",
    ),
    "/api/v1/stock_fnd/income-cashflow-single": (
        "income", "cashflow", "hk_income", "hk_cashflow", "us_income",
        "us_cashflow",
    ),
    "/api/v1/stock_fnd/main-business-industry": ("fina_mainbz",),
    "/api/v1/stock_fnd/metrics-ttm": (
        "income", "cashflow", "daily_basic", "us_income", "us_cashflow",
        "us_daily_adj",
    ),
    "/api/v1/stock_fnd/prelim-quarter": ("express",),
    "/api/v1/stock_fnd/risk-factor-csi300": ("daily", "index_daily"),
    "/api/v1/stock_fnd/risk-factor-csi500": ("daily", "index_daily"),
    "/api/v1/stock_fnd/risk-factor-sh000001": ("daily", "index_daily"),
    "/api/v1/stock_fnd/risk-factor-sw": (
        "daily", "sw_daily", "index_member_all",
    ),
    "/api/v1/stock_fnd/stock-rel-fund-holdings-top": ("fund_portfolio",),
    "/api/v1/stock_fnd/style-classification": (
        "daily", "daily_basic", "fina_indicator",
    ),
    "/api/v1/stock_fnd/yield-factor": ("daily", "adj_factor"),
}


# Structured facts absent from Tushare's tabular catalog but recoverable from
# the official A-share announcement PDFs exposed by ``anns_d``.  Parsing must
# retain document URL/hash, parser version and evidence spans.
ANNOUNCEMENT_PARSE_ROUTES = frozenset({
    "/api/v1/stock/change-plan",
    "/api/v1/stock_fnd/actual-controller",
    "/api/v1/stock_fnd/asset-restructuring",
    "/api/v1/stock_fnd/concert-parties",
    "/api/v1/stock_fnd/controlling-shareholder",
    "/api/v1/stock_fnd/delisting-info",
    "/api/v1/stock_fnd/employee-ownership-plan",
    "/api/v1/stock_fnd/fund-raising-usage",
    "/api/v1/stock_fnd/guarantee-events",
    "/api/v1/stock_fnd/guarantee-stats",
    "/api/v1/stock_fnd/holding-subsidiaries",
    "/api/v1/stock_fnd/ipo-quote-details",
    "/api/v1/stock_fnd/ipo-winning-numbers",
    "/api/v1/stock_fnd/litigation-arbitration",
    "/api/v1/stock_fnd/regulatory-penalties",
    "/api/v1/stock_fnd/related-party-transactions",
    "/api/v1/stock_fnd/review-process",
    "/api/v1/stock_fnd/seo-placement-details",
    "/api/v1/stock_fnd/shareholder-commitment",
    "/api/v1/stock_fnd/shareholder-meeting",
    "/api/v1/stock_fnd/takeover-offers",
    "/api/v1/stock_fnd/tender-offers",
})


# Partial overlap is explicitly *not* equivalence.  These routes remain
# Financial-Data-only for their published contract, while the listed Tushare
# interfaces can satisfy a smaller market/field slice.
PARTIAL_TUSHARE_OVERLAPS: dict[str, tuple[str, ...]] = {
    "/api/v1/altdata/hot-plate-rank": ("ths_hot", "dc_hot", "limit_cpt_list"),
    "/api/v1/altdata/hot-stock-rank": ("ths_hot", "dc_hot"),
    "/api/v1/common/entity_relationship": (
        "stk_ah_comparison", "bse_mapping", "namechange",
    ),
    "/api/v1/common/trading-day": (
        "trade_cal", "hk_tradecal", "us_tradecal", "fut_trade_cal",
    ),
    "/api/v1/common/trading-state": (
        "trade_cal", "hk_tradecal", "us_tradecal", "rt_hk_k", "rt_idx_k",
    ),
    "/api/v1/fund/asset-allocation": ("fund_portfolio", "fund_nav"),
    "/api/v1/fund/fund-archive": ("fund_basic",),
    "/api/v1/fund/fund-charge-rate": ("fund_basic",),
    "/api/v1/fund/net-value": ("fund_nav", "fund_daily"),
    "/api/v1/fund/share-split": ("fund_adj",),
    "/api/v1/fund/trade-limit": ("fund_basic",),
    "/api/v1/hk_stock/equity-structure": ("hk_daily_adj",),
    "/api/v1/hk_stock/free-float": ("hk_daily_adj",),
    "/api/v1/hk_stock/high-shareholding-concentration": (
        "ccass_hold", "ccass_hold_detail",
    ),
    "/api/v1/info/announcements": ("anns_d",),
    "/api/v1/info/news-global-search": ("news", "major_news"),
    "/api/v1/info/tag/category": ("news", "major_news"),
    "/api/v1/info/tag/query": ("news", "major_news"),
    "/api/v1/macro/data-query": (
        "cn_gdp", "cn_cpi", "cn_ppi", "cn_pmi", "cn_m", "sf_month",
        "shibor", "shibor_lpr", "us_tbr", "us_tltr", "us_trltr",
        "us_trycr", "us_tycr",
    ),
    "/api/v1/macro/meta-search": (
        "cn_schedule", "cn_gdp", "cn_cpi", "cn_ppi", "cn_pmi", "cn_m",
    ),
    "/api/v1/onecode/query": (
        "factor_value", "daily", "daily_basic", "fund_nav", "index_daily",
    ),
    "/api/v1/onecode/recall": ("factor_list",),
    "/api/v1/quote/basic-snapshot": (
        "stk_mins", "hk_mins", "etf_mins", "idx_mins", "rt_hk_k",
        "rt_idx_k", "rt_sw_k", "rt_etf_sz_iopv",
    ),
    "/api/v1/quote/auction-snapshot": (
        "stk_auction", "stk_auction_o", "stk_auction_c",
    ),
    "/api/v1/quote/derived-snapshot": (
        "daily_basic", "hk_daily_adj", "us_daily_adj",
    ),
    "/api/v1/index_fnd/index-constituents-list-weight": (
        "index_weight", "index_member_all",
    ),
    "/api/v1/stock_fnd/consensus-details": ("report_rc",),
    "/api/v1/stock_fnd/consensus-stats": ("report_rc",),
    "/api/v1/stock/market-detail": ("margin_detail",),
    "/api/v1/stock/stock-index-constituents-list": (
        "index_member_all", "index_weight",
    ),
    "/api/v1/stock_fnd/depository-receipt": ("us_basic",),
    "/api/v1/stock_fnd/dividend-details": ("dividend",),
    "/api/v1/stock_fnd/dividend-record": ("dividend",),
    "/api/v1/stock_fnd/equity-structure": ("daily_basic", "hk_daily_adj"),
    "/api/v1/stock_fnd/executive-compensation": ("stk_rewards",),
    "/api/v1/stock_fnd/free-float": ("daily_basic", "hk_daily_adj"),
    "/api/v1/stock_fnd/ipo-primary": ("new_share",),
    "/api/v1/stock_fnd/main-business-product": ("fina_mainbz",),
    "/api/v1/stock_fnd/main-business-region": ("fina_mainbz",),
    "/api/v1/stock_fnd/holder-count": ("stk_holdernumber",),
    "/api/v1/stock_fnd/industry-classification": (
        "stock_basic", "hk_basic", "us_basic", "index_classify",
    ),
    "/api/v1/stock_fnd/rating-summary": ("report_rc",),
    "/api/v1/stock_fnd/restricted-release-calendar": ("share_float",),
    "/api/v1/stock_fnd/shareholder-list": (
        "top10_holders", "top10_floatholders",
    ),
    "/api/v1/stock_fnd/specialty-metrics-period": (
        "fina_indicator", "hk_fina_indicator", "us_fina_indicator",
    ),
    "/api/v1/stock_fnd/stock-basic-info": (
        "stock_basic", "stock_company", "hk_basic", "us_basic",
    ),
    "/api/v1/stock_fnd/target-price": ("report_rc",),
    "/api/v1/us_stock/security-markings": ("us_basic",),
    "/api/v1/us_stock/equity-structure": ("us_daily_adj",),
    "/api/v1/stock_sh_equity/freeze-pledge": (
        "pledge_detail", "pledge_stat",
    ),
    "/api/v2/info/news/article": ("news", "major_news"),
    "/api/v2/info/news/search_evidence": ("news", "major_news", "anns_d"),
}


ROUTE_NOTES: dict[str, str] = {
    "/api/v1/altdata/hot-plate-rank": "Financial Data 是支付宝口径；Tushare 热榜的数据源和排名方法不同。",
    "/api/v1/altdata/hot-stock-rank": "Financial Data 是支付宝散户关注度；Tushare 热榜不能复现该口径。",
    "/api/v1/common/entity_relationship": "Tushare 仅覆盖部分 AH、北交所代码及曾用名关系，缺少完整跨市场实体图谱。",
    "/api/v1/common/trading-day": "Tushare 有 A/H/US/期货日历，但没有覆盖该合同中现货等全部资产的统一交易日历。",
    "/api/v1/common/trading-state": "Tushare 没有覆盖多资产市场的统一实时交易状态接口。",
    "/api/v1/fund/asset-allocation": "Tushare 基金持仓不提供股票、债券、现金等完整大类资产配置表。",
    "/api/v1/fund/bond-portfolio": "Tushare fund_portfolio 是公募股票持仓，不能替代重仓债券明细。",
    "/api/v1/fund/fund-archive": "fund_basic 有基础字段，但缺少完整投资策略、风险评估和申购确认等合同字段。",
    "/api/v1/fund/fund-charge-rate": "fund_basic 的管理/托管费不能替代分档申购、赎回和认购费率。",
    "/api/v1/fund/fund-portfolio": "Tushare 缺少 FOF 持有底层基金的结构化明细。",
    "/api/v1/fund/net-value": "fund_nav/fund_daily 有普通基金净值行情，但缺少货币基金七日年化和万份收益字段。",
    "/api/v1/fund/share-split": "fund_adj 只能观察复权因子变化，不能确定拆分类型和登记变更日。",
    "/api/v1/fund/trade-limit": "Tushare 缺少按业务类型、收费方式展开的场外基金交易限制。",
    "/api/v1/index_fnd/index-constituents-list-weight": "Tushare 可覆盖 A 股主要指数，不能完整覆盖该合同声明的港股指数成分。",
    "/api/v1/info/announcements": "anns_d 提供 A 股公告 PDF，不能完整覆盖 Financial Data 的 A 股与港股合同。",
    "/api/v1/info/news-global-search": "Tushare 新闻源可做局部检索，但不是全网搜索与证据抽取服务。",
    "/api/v1/macro/data-query": "Tushare 有核心宏观序列，但不覆盖地区、长尾国家和细分产业指标全集。",
    "/api/v1/macro/meta-search": "Tushare 没有与 Financial Data 长尾宏观指标库等价的语义检索目录。",
    "/api/v1/onecode/query": "部分指标可由 Tushare 计算，但 OneCode 动态指标全集及其口径不是公开等价物。",
    "/api/v1/onecode/recall": "factor_list 仅覆盖 Tushare 量化因子，不能替代 OneCode 全指标语义召回。",
    "/api/v1/quote/basic-snapshot": "Tushare 只有若干品种实时接口，缺少统一 A/H/US/基金/板块/指数/现货快照。",
    "/api/v1/quote/auction-snapshot": "stk_auction 系列只给最终开/收盘竞价结果，不能提供指定时段内未撮合买卖量的快照序列。",
    "/api/v1/quote/derived-snapshot": "历史/日频估值不能替代跨市场实时衍生快照。",
    "/api/v1/stock/ashare-cdr-conversion-ratio": "Tushare 没有 A 股 CDR 与基础证券转换比例历史。",
    "/api/v1/stock/after-daily-quote": "Tushare 日行情不包含盘后固定价格成交及盘后买卖申报数量。",
    "/api/v1/stock/market-detail": "margin_detail 覆盖核心两融数据，但缺少担保券数量、市值及交易所占比等合同字段。",
    "/api/v1/stock/stock-index-constituents-list": "Tushare 可反查部分 A 股指数归属，缺少该合同声明的港股指数归属全集。",
    "/api/v1/stock_fnd/consensus-details": "report_rc 覆盖 A 股卖方盈利预测，不覆盖该合同的港股、美股全集。",
    "/api/v1/stock_fnd/consensus-stats": "可聚合 A 股 report_rc，但无法完整覆盖港股、美股一致预期统计。",
    "/api/v1/stock_fnd/depository-receipt": "Tushare 基础证券表没有完整存托凭证转换关系与比例历史。",
    "/api/v1/stock_fnd/dividend-details": "dividend 仅覆盖 A 股，缺少港股和美股合同范围。",
    "/api/v1/stock_fnd/dividend-record": "dividend 仅覆盖 A 股，缺少港股和美股除权除息事件。",
    "/api/v1/stock_fnd/executive-compensation": "stk_rewards 仅覆盖 A 股，缺少港股高管薪酬与持股。",
    "/api/v1/stock_fnd/holder-count": "stk_holdernumber 只有股东总户数，缺少 A/B/H/CDR 分类型户数。",
    "/api/v1/stock_fnd/industry-classification": "Tushare 可给基础行业和 A 股申万层级，缺少 A/H/US 多标准一至四级分类全集。",
    "/api/v1/stock_fnd/ipo-primary": "new_share 仅覆盖 A 股，缺少港股和美股 IPO 合同字段。",
    "/api/v1/stock_fnd/listing-rules": "Tushare 没有港股收市竞价、卖空、市调机制等规则快照。",
    "/api/v1/stock_fnd/restricted-release-calendar": "share_float 仅覆盖 A 股，缺少港股限售解禁。",
    "/api/v1/stock_fnd/shareholder-list": "Tushare 十大股东表仅覆盖 A 股，缺少港股和美股。",
    "/api/v1/stock_fnd/specialty-metrics-period": "Tushare 财务指标不能完整覆盖 A/H/US 银行、保险、券商特色口径。",
    "/api/v1/stock_fnd/specialty-metrics-point": "Tushare 缺少内含价值、风险贴现率等跨市场保险特色时点指标。",
    "/api/v1/stock_fnd/target-price": "report_rc 可提供部分 A 股研报价格信息，缺少统一 A/H/US 目标价统计。",
    "/api/v1/stock_fnd/stock-basic-info": "Tushare 的港股/美股列表缺少成立日期、注册资本、法人等完整公司档案字段。",
    "/api/v1/stock_sh_equity/freeze-pledge": "pledge_detail/pledge_stat 覆盖质押，但没有完整股权冻结事件。",
    "/api/v1/us_stock/equity-structure": "us_daily_adj 有总股本和流通股本，但缺少内部人持股及公司/证券双层股本。",
    "/api/v1/us_stock/security-markings": "us_basic 缺少完整 ADR 比例、首次发行和双重上市标识。",
    "/api/v2/info/news/article": "Tushare 有正文，但不能用 Financial Data 的 feed_id 读取同一篇内容。",
    "/api/v2/info/news/search_evidence": "Tushare 有新闻/公告子集，缺少相同去重、标签和 feed_id 证据合同。",
}


@dataclass(frozen=True, slots=True)
class FinancialTushareMapping:
    route: str
    equivalence_class: str
    tushare_interfaces: tuple[str, ...]
    related_tushare_interfaces: tuple[str, ...]
    coverage: str
    rationale: str

    def as_dict(self) -> dict:
        permissions = tushare_contract_index()
        interface_status = [
            {
                "api_name": name,
                "title": permissions.get(name, {}).get("title"),
                "permission": permissions.get(name, {}).get("permission", "未收录"),
                "collectable": permissions.get(name, {}).get("collectable", False),
            }
            for name in self.tushare_interfaces
        ]
        related_status = [
            {
                "api_name": name,
                "title": permissions.get(name, {}).get("title"),
                "permission": permissions.get(name, {}).get("permission", "未收录"),
                "collectable": permissions.get(name, {}).get("collectable", False),
            }
            for name in self.related_tushare_interfaces
        ]
        accessible = {"有权限", "有权限（当前限频）"}
        token_ready = bool(interface_status) and all(
            item["permission"] in accessible and item["collectable"] is True
            for item in interface_status
        )
        return {
            "route": self.route,
            "equivalence_class": self.equivalence_class,
            "coverage": self.coverage,
            "tushare_interfaces": interface_status,
            "related_tushare_interfaces": related_status,
            "current_token_ready": token_ready,
            "rationale": self.rationale,
        }


@lru_cache(maxsize=1)
def tushare_contract_index() -> dict[str, dict[str, object]]:
    path = Path(__file__).resolve().parents[2] / "docs" / "tushare" / "contracts.json"
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {
        item["api_name"]: {
            "title": item.get("title", ""),
            "permission": item.get("permission", {}).get("status", "未知"),
            "collectable": bool(item.get("collectable")),
        }
        for item in payload.get("interfaces", [])
    }


def _rationale(route: str, equivalence_class: str) -> str:
    if route in ROUTE_NOTES:
        return ROUTE_NOTES[route]
    if equivalence_class == TUSHARE_DIRECT:
        return "Tushare 有覆盖该完整业务事实的结构化接口；仍需统一字段、代码、日期和单位。"
    if equivalence_class == TUSHARE_DERIVED:
        return "可由所列 Tushare 结构化数据确定性计算；公式、权重与 as-of 规则必须版本化。"
    if equivalence_class == TUSHARE_ANNOUNCEMENT_PARSE:
        return "Tushare 没有等价结构化表，但可从 anns_d 官方公告 PDF 提取并保留证据链。"
    return "在已审计的 Tushare 契约中没有覆盖完整合同的结构化、可确定性派生或公告来源。"


def financial_tushare_mapping(route: str) -> FinancialTushareMapping:
    if route not in FINANCIAL_DATA_ROUTES:
        raise KeyError(f"uncatalogued Financial Data route: {route}")
    if route in DIRECT_EQUIVALENTS:
        category = TUSHARE_DIRECT
        interfaces = DIRECT_EQUIVALENTS[route]
        related = ()
        coverage = "full_direct"
    elif route in DERIVED_EQUIVALENTS:
        category = TUSHARE_DERIVED
        interfaces = DERIVED_EQUIVALENTS[route]
        related = ()
        coverage = "full_after_deterministic_derivation"
    elif route in ANNOUNCEMENT_PARSE_ROUTES:
        category = TUSHARE_ANNOUNCEMENT_PARSE
        interfaces = ("anns_d",)
        related = ()
        coverage = "full_after_evidence_backed_a_share_parsing"
    else:
        category = FINANCIAL_DATA_ONLY
        interfaces = ()
        related = PARTIAL_TUSHARE_OVERLAPS.get(route, ())
        coverage = "partial_overlap_only" if related else "no_equivalent"
    return FinancialTushareMapping(
        route=route,
        equivalence_class=category,
        tushare_interfaces=interfaces,
        related_tushare_interfaces=related,
        coverage=coverage,
        rationale=_rationale(route, category),
    )


def financial_tushare_catalog() -> tuple[FinancialTushareMapping, ...]:
    return tuple(
        financial_tushare_mapping(route)
        for route in sorted(FINANCIAL_DATA_ROUTES)
    )


def financial_tushare_summary(
    items: tuple[FinancialTushareMapping, ...] | None = None,
) -> dict[str, int]:
    items = financial_tushare_catalog() if items is None else items
    counts = {
        category: sum(item.equivalence_class == category for item in items)
        for category in EQUIVALENCE_CLASSES
    }
    serialized = [item.as_dict() for item in items]
    return {
        "financial_data_routes": len(items),
        "tushare_contracts": len(tushare_contract_index()),
        "tushare_collectable_contracts": sum(
            item["collectable"] is True
            for item in tushare_contract_index().values()
        ),
        "current_token_ready_routes": sum(
            item["current_token_ready"] for item in serialized
        ),
        "partial_tushare_overlap_routes": sum(
            item.coverage == "partial_overlap_only" for item in items
        ),
        **counts,
    }


def tushare_financial_reverse_catalog() -> tuple[dict, ...]:
    """Return all Tushare contracts with their full/partial FD relationships."""
    contracts = tushare_contract_index()
    mappings = financial_tushare_catalog()
    result = []
    for api_name in sorted(contracts):
        full_routes = tuple(
            item.route for item in mappings
            if api_name in item.tushare_interfaces
        )
        partial_routes = tuple(
            item.route for item in mappings
            if api_name in item.related_tushare_interfaces
        )
        if full_routes:
            status = "full_equivalence_input"
        elif partial_routes:
            status = "partial_overlap_only"
        else:
            status = "no_financial_data_counterpart"
        result.append({
            "api_name": api_name,
            "title": contracts[api_name]["title"],
            "permission": contracts[api_name]["permission"],
            "collectable": contracts[api_name]["collectable"],
            "mapping_status": status,
            "full_equivalence_routes": list(full_routes),
            "partial_overlap_routes": list(partial_routes),
        })
    return tuple(result)


def tushare_financial_reverse_summary(
    items: tuple[dict, ...] | None = None,
) -> dict[str, int]:
    items = tushare_financial_reverse_catalog() if items is None else items
    return {
        "tushare_contracts": len(items),
        "full_equivalence_input": sum(
            item["mapping_status"] == "full_equivalence_input" for item in items
        ),
        "partial_overlap_only": sum(
            item["mapping_status"] == "partial_overlap_only" for item in items
        ),
        "no_financial_data_counterpart": sum(
            item["mapping_status"] == "no_financial_data_counterpart"
            for item in items
        ),
    }


_classified = (
    set(DIRECT_EQUIVALENTS)
    | set(DERIVED_EQUIVALENTS)
    | set(ANNOUNCEMENT_PARSE_ROUTES)
)
if not _classified <= FINANCIAL_DATA_ROUTES:
    raise RuntimeError("provider mapping contains unknown Financial Data routes")
if len(_classified) != sum(
    len(group)
    for group in (DIRECT_EQUIVALENTS, DERIVED_EQUIVALENTS, ANNOUNCEMENT_PARSE_ROUTES)
):
    raise RuntimeError("provider mapping classes must be disjoint")
if not set(PARTIAL_TUSHARE_OVERLAPS) <= (FINANCIAL_DATA_ROUTES - _classified):
    raise RuntimeError("partial overlaps cannot also claim full equivalence")
