"""
申万行业成分构成查询接口

表: ths_member (Tushare ths_member 接口)
含 ts_code/con_code/con_name 等成分股信息

函数:
  get_ths_member(ts_code)              → 某申万行业的所有成分股
  get_ths_member_by_stock(con_code)    → 某股票所属申万行业
"""

from typing import Optional
from service.db import query


def get_ths_member(ts_code: str) -> list[dict]:
    """查询某申万行业的所有成分股"""
    sql = "SELECT * FROM ths_member WHERE ts_code = %s ORDER BY con_code"
    return query(sql, (ts_code,))


def get_ths_member_by_stock(con_code: str) -> list[dict]:
    """查询某股票所属的申万行业"""
    sql = "SELECT * FROM ths_member WHERE con_code = %s ORDER BY ts_code"
    return query(sql, (con_code,))
