"""
每日停复牌信息查询接口

从本地 suspend_d 表查询。

函数：
  get_suspend_d(trade_date, ts_code)        → 某天某只股票停复牌情况
  get_suspend_d_by_date(trade_date)          → 某天全市场停复牌
  get_suspend_d_history(ts_code, start, end) → 某只股票历史停复牌
"""

from typing import Optional
from service.db import query


def get_suspend_d(trade_date: str, ts_code: str) -> list[dict]:
    """查询某天某只股票的停复牌信息"""
    sql = "SELECT * FROM suspend_d WHERE trade_date = %s AND ts_code = %s"
    return query(sql, (trade_date, ts_code))


def get_suspend_d_by_date(trade_date: str, limit: int = 100, offset: int = 0) -> list[dict]:
    """查询某天全市场停复牌"""
    sql = "SELECT * FROM suspend_d WHERE trade_date = %s ORDER BY ts_code LIMIT %s OFFSET %s"
    return query(sql, (trade_date, limit, offset))


def get_suspend_d_history(ts_code: str, start_date: str, end_date: str) -> list[dict]:
    """查询某只股票历史停复牌记录"""
    sql = (
        "SELECT * FROM suspend_d "
        "WHERE ts_code = %s AND trade_date >= %s AND trade_date <= %s "
        "ORDER BY trade_date"
    )
    return query(sql, (ts_code, start_date, end_date))
