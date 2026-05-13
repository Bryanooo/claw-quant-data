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
