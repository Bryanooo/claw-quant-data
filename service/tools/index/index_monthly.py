"""
指数月线行情查询接口

表: index_monthly (Tushare index_monthly 接口)

函数:
  get_index_monthly(ts_code, start_date, end_date)   → 某指数历史月线
  get_index_monthly_by_date(trade_date)               → 某月所有指数月线
"""

from typing import Optional
from service.db import query


def get_index_monthly(ts_code: str, start_date: str = None, end_date: str = None) -> list[dict]:
    """查询某指数历史月线"""
    conditions = ["ts_code = %s"]
    params = [ts_code]

    if start_date:
        conditions.append("trade_date >= %s")
        params.append(start_date)
    if end_date:
        conditions.append("trade_date <= %s")
        params.append(end_date)

    sql = (f"SELECT * FROM index_monthly WHERE {' AND '.join(conditions)} "
           "ORDER BY trade_date")
    return query(sql, tuple(params))


def get_index_monthly_by_date(trade_date: str) -> list[dict]:
    """查询某月所有指数月线"""
    sql = "SELECT * FROM index_monthly WHERE trade_date = %s ORDER BY ts_code"
    return query(sql, (trade_date,))
