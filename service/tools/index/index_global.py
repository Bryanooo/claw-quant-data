"""
国际指数行情查询接口

表: index_global (Tushare index_global 接口)
含 DJI/SPX/IXIC/FTSE/N225 等国际主要指数

函数:
  get_index_global(ts_code, start_date, end_date)     → 某国际指数历史行情
  get_index_global_by_date(trade_date)                 → 某天所有国际指数
"""

from typing import Optional
from service.db import query


def get_index_global(ts_code: str, start_date: str = None, end_date: str = None) -> list[dict]:
    """查询某国际指数历史行情"""
    conditions = ["ts_code = %s"]
    params = [ts_code]

    if start_date:
        conditions.append("trade_date >= %s")
        params.append(start_date)
    if end_date:
        conditions.append("trade_date <= %s")
        params.append(end_date)

    sql = (f"SELECT * FROM index_global WHERE {' AND '.join(conditions)} "
           "ORDER BY trade_date")
    return query(sql, tuple(params))


def get_index_global_by_date(trade_date: str) -> list[dict]:
    """查询某天所有国际指数行情"""
    sql = "SELECT * FROM index_global WHERE trade_date = %s ORDER BY ts_code"
    return query(sql, (trade_date,))
