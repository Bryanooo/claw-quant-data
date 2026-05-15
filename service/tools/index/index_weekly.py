"""
指数周线行情查询接口

表: index_weekly (Tushare index_weekly 接口)

函数:
  get_index_weekly(ts_code, start_date, end_date)   → 某指数历史周线
  get_index_weekly_by_date(trade_date)               → 某周所有指数周线
"""

from typing import Optional
from service.db import query


def get_index_weekly(ts_code: str, start_date: str = None, end_date: str = None) -> list[dict]:
    """查询某指数历史周线"""
    conditions = ["ts_code = %s"]
    params = [ts_code]

    if start_date:
        conditions.append("trade_date >= %s")
        params.append(start_date)
    if end_date:
        conditions.append("trade_date <= %s")
        params.append(end_date)

    sql = (f"SELECT * FROM index_weekly WHERE {' AND '.join(conditions)} "
           "ORDER BY trade_date")
    return query(sql, tuple(params))


def get_index_weekly_by_date(trade_date: str) -> list[dict]:
    """查询某周所有指数周线"""
    sql = "SELECT * FROM index_weekly WHERE trade_date = %s ORDER BY ts_code"
    return query(sql, (trade_date,))
