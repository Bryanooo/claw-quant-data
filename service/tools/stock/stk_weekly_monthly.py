"""
周线/月线行情查询接口

从本地 stk_weekly_monthly 表查询，freq 参数区分 week / month。

函数：
  get_weekly_line(ts_code, start, end)       → 周线行情
  get_monthly_line(ts_code, start, end)      → 月线行情
  get_weekly_line_by_date(trade_date)        → 某周全市场
  get_monthly_line_by_date(trade_date)       → 某月全市场
"""

from typing import Optional
from service.db import query


def get_weekly_line(ts_code: str, start_date: str, end_date: str) -> list[dict]:
    """查询某只股票历史周线"""
    sql = (
        "SELECT * FROM stk_weekly_monthly "
        "WHERE ts_code = %s AND freq = 'week' "
        "AND trade_date >= %s AND trade_date <= %s "
        "ORDER BY trade_date"
    )
    return query(sql, (ts_code, start_date, end_date))


def get_monthly_line(ts_code: str, start_date: str, end_date: str) -> list[dict]:
    """查询某只股票历史月线"""
    sql = (
        "SELECT * FROM stk_weekly_monthly "
        "WHERE ts_code = %s AND freq = 'month' "
        "AND trade_date >= %s AND trade_date <= %s "
        "ORDER BY trade_date"
    )
    return query(sql, (ts_code, start_date, end_date))


def get_weekly_line_by_date(trade_date: str, limit: int = 100, offset: int = 0) -> list[dict]:
    """查询某周全市场周线"""
    sql = (
        "SELECT * FROM stk_weekly_monthly "
        "WHERE freq = 'week' AND trade_date = %s "
        "ORDER BY ts_code LIMIT %s OFFSET %s"
    )
    return query(sql, (trade_date, limit, offset))


def get_monthly_line_by_date(trade_date: str, limit: int = 100, offset: int = 0) -> list[dict]:
    """查询某月全市场月线"""
    sql = (
        "SELECT * FROM stk_weekly_monthly "
        "WHERE freq = 'month' AND trade_date = %s "
        "ORDER BY ts_code LIMIT %s OFFSET %s"
    )
    return query(sql, (trade_date, limit, offset))
