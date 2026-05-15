"""
大盘指数每日指标查询接口

表: index_dailybasic (Tushare index_dailybasic 接口)
含 PE/PB/PETTM/总市值/流通市值 等指标

函数:
  get_index_dailybasic(ts_code, start_date, end_date)     → 某指数历史每日指标
  get_index_dailybasic_by_date(trade_date)                 → 某天所有指数指标
"""

from typing import Optional
from service.db import query


def get_index_dailybasic(ts_code: str, start_date: str = None, end_date: str = None) -> list[dict]:
    """查询某指数历史每日指标"""
    conditions = ["ts_code = %s"]
    params = [ts_code]

    if start_date:
        conditions.append("trade_date >= %s")
        params.append(start_date)
    if end_date:
        conditions.append("trade_date <= %s")
        params.append(end_date)

    sql = (f"SELECT * FROM index_dailybasic WHERE {' AND '.join(conditions)} "
           "ORDER BY trade_date")
    return query(sql, tuple(params))


def get_index_dailybasic_by_date(trade_date: str) -> list[dict]:
    """查询某天所有指数每日指标"""
    sql = "SELECT * FROM index_dailybasic WHERE trade_date = %s ORDER BY ts_code"
    return query(sql, (trade_date,))
