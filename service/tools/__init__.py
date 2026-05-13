"""
=============================================================================
service/tools — 统一数据查询接口
=============================================================================

所有 service tool 都在这里统一导出，Agent 只需记住：

    from service.tools import search_stock, is_trade_day, ...

按数据域分文件：
  trade_cal.py   — 交易日历相关
  stock.py       — 股票基础信息
  kline.py       — K 线数据（后续）
  finance.py     — 财务数据（后续）
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
