"""
指数基本信息查询接口

表: index_basic (Tushare index_basic 接口 -> ts_code/name/market/fullname 等)

函数:
  get_index_basic(ts_code=None, market=None)  → 查询指数基本信息
"""

from typing import Optional
from service.db import query


def get_index_basic(ts_code: str = None, market: str = None) -> list[dict]:
    """查询指数基本信息

    Args:
        ts_code: 指数代码，不传则返回全部
        market: 交易所筛选（SH/SZ），不传则不筛

    Returns:
        list[dict]: 指数基本信息列表
    """
    conditions = []
    params = []

    if ts_code:
        conditions.append("ts_code = %s")
        params.append(ts_code)
    if market:
        conditions.append("market = %s")
        params.append(market)

    where = " WHERE " + " AND ".join(conditions) if conditions else ""
    sql = f"SELECT * FROM index_basic{where} ORDER BY ts_code"
    return query(sql, tuple(params)) if params else query(sql)
