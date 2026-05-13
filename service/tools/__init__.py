"""
=============================================================================
service/tools — 统一数据查询接口
=============================================================================

所有 service tool 都在这里统一导出，Agent 只需记住：

    from service.tools import search_stock, is_trade_day, ...

按数据域分文件：
  trade_cal.py                  — 交易日历相关
  stock/                        — 股票数据
    namechange.py               —   曾用名
    bse_mapping.py              —   北交所对照
    bak_basic.py                —   盘后指标
    stk_limit.py                —   涨跌停价格 ⭐ 新增
    suspend_d.py                —   停复牌信息 ⭐ 新增
    hsgt_top10.py               —   沪深股通十大成交 ⭐ 新增
    ggt_top10.py                —   港股通十大成交 ⭐ 新增
    ggt_stat.py                 —   港股通日/月统计 ⭐ 新增
    stk_weekly_monthly.py       —   周线/月线行情 ⭐ 新增
  finance/                      — 财务数据
    income.py                   —   利润表 ⭐ 新增
    balancesheet.py             —   资产负债表 ⭐ 新增
    cashflow.py                 —   现金流量表 ⭐ 新增
    fina_indicator.py           —   财务指标 ⭐ 新增
    extras.py                   —   业绩预告/快报/分红/主营/披露计划 ⭐ 新增
"""

from service.tools.trade_cal import (
    is_trade_day,
    get_trade_days,
    get_last_trade_day,
    get_next_trade_day,
    get_trade_calendar,
)
from service.tools.stock.namechange import get_namechange
from service.tools.stock.bse_mapping import get_bse_mapping
from service.tools.stock.bak_basic import (
    get_bak_basic,
    get_bak_basic_by_date,
    get_bak_basic_history,
    get_bak_basic_by_industry,
)
from service.tools.stock.stk_limit import (
    get_stk_limit,
    get_stk_limit_by_date,
    get_stk_limit_history,
)
from service.tools.stock.suspend_d import (
    get_suspend_d,
    get_suspend_d_by_date,
    get_suspend_d_history,
)
from service.tools.stock.hsgt_top10 import (
    get_hsgt_top10,
    get_hsgt_top10_by_stock,
)
from service.tools.stock.ggt_top10 import (
    get_ggt_top10,
    get_ggt_top10_by_stock,
)
from service.tools.stock.ggt_stat import (
    get_ggt_daily,
    get_ggt_monthly,
)
from service.tools.stock.stk_weekly_monthly import (
    get_weekly_line,
    get_monthly_line,
    get_weekly_line_by_date,
    get_monthly_line_by_date,
)
from service.tools.finance.income import (
    get_income,
    get_income_by_period,
    get_income_summary,
)
from service.tools.finance.balancesheet import (
    get_balancesheet,
    get_balancesheet_by_period,
    get_balancesheet_summary,
)
from service.tools.finance.cashflow import (
    get_cashflow,
    get_cashflow_summary,
)
from service.tools.finance.fina_indicator import (
    get_fina_indicator,
    get_fina_indicator_by_period,
    get_fina_indicator_ratings,
)
from service.tools.finance.extras import (
    get_forecast,
    get_forecast_by_period,
    get_express,
    get_dividend,
    get_dividend_upcoming,
    get_mainbz,
    get_mainbz_by_industry,
    get_disclosure_date,
    get_upcoming_disclosures,
    get_next_earnings,
)

# ── 外汇数据（5接口） ──
from service.tools.forex.forex import (
    get_fx_obasic,
    get_fx_classify_stats,
    get_fx_daily,
    get_fx_daily_by_classify,
    get_fx_daily_latest,
)
