"""
沪深港通十大成交股查询接口

从本地 hsgt_top10 表查询。

函数：
  get_hsgt_top10(trade_date)           → 某天沪深股通十大成交
  get_hsgt_top10_by_stock(ts_code)     → 某只股票历史沪深股通上榜记录
"""

from typing import Optional
from service.db import query


def get_hsgt_top10(trade_date: str) -> list[dict]:
    """查询某天沪深股通十大成交股（含沪市+深市）"""
    sql = "SELECT * FROM hsgt_top10 WHERE trade_date = %s ORDER BY market_type, rank"
    return query(sql, (trade_date,))


def get_hsgt_top10_by_stock(ts_code: str, limit: int = 50) -> list[dict]:
    """查询某只股票历史沪深股通十大成交上榜记录"""
    sql = (
        "SELECT * FROM hsgt_top10 WHERE ts_code = %s "
        "ORDER BY trade_date DESC LIMIT %s"
    )
    return query(sql, (ts_code, limit))
