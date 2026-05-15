"""
申万行业日线行情查询接口

表: ths_daily (Tushare ths_daily 接口)
含 ts_code/trade_date/open/high/low/close/vol 等行情字段

函数:
  get_ths_daily(ts_code, start_date, end_date)     → 某申万行业历史日线
  get_ths_daily_by_date(trade_date)                 → 某天所有申万行业价量
"""

from typing import Optional
from service.db import query


def get_ths_daily(ts_code: str, start_date: str = None, end_date: str = None) -> list[dict]:
    """查询某申万行业历史日线"""
    conditions = ["ts_code = %s"]
    params = [ts_code]

    if start_date:
        conditions.append("trade_date >= %s")
        params.append(start_date)
    if end_date:
        conditions.append("trade_date <= %s")
        params.append(end_date)

    sql = (f"SELECT * FROM ths_daily WHERE {' AND '.join(conditions)} "
           "ORDER BY trade_date")
    return query(sql, tuple(params))


def get_ths_daily_by_date(trade_date: str) -> list[dict]:
    """查询某天所有申万行业日线"""
    sql = "SELECT * FROM ths_daily WHERE trade_date = %s ORDER BY ts_code"
    return query(sql, (trade_date,))


def get_ths_daily_top_gainer(trade_date: str, top_n: int = 10) -> list[dict]:
    """查询某天涨幅最大的申万行业"""
    sql = ("SELECT * FROM ths_daily WHERE trade_date = %s "
           "ORDER BY pct_change DESC LIMIT %s")
    return query(sql, (trade_date, top_n))
