"""
每日涨跌停价格查询接口

从本地 stk_limit 表查询每日涨跌停数据。

函数：
  get_stk_limit(trade_date, ts_code)        → 某天某只股票
  get_stk_limit_by_date(trade_date)          → 某天全市场涨跌停
  get_stk_limit_history(ts_code, start, end) → 某只股票历史区间
"""

from typing import Optional
from service.db import query


def get_stk_limit(trade_date: str, ts_code: str) -> list[dict]:
    """查询某天某只股票的涨跌停价格"""
    sql = "SELECT * FROM stk_limit WHERE trade_date = %s AND ts_code = %s"
    return query(sql, (trade_date, ts_code))


def get_stk_limit_by_date(trade_date: str, limit: int = 100, offset: int = 0) -> list[dict]:
    """查询某天全市场涨跌停价格"""
    sql = "SELECT * FROM stk_limit WHERE trade_date = %s ORDER BY ts_code LIMIT %s OFFSET %s"
    return query(sql, (trade_date, limit, offset))


def get_stk_limit_history(ts_code: str, start_date: str, end_date: str) -> list[dict]:
    """查询某只股票历史涨跌停区间"""
    sql = (
        "SELECT * FROM stk_limit "
        "WHERE ts_code = %s AND trade_date >= %s AND trade_date <= %s "
        "ORDER BY trade_date"
    )
    return query(sql, (ts_code, start_date, end_date))
