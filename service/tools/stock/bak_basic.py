"""
股票历史列表（每日备用基础）查询接口

从本地 bak_basic 表查询盘后指标数据。
包含：行业、PE、流通股本、财务比率等每日快照。

函数：
  get_bak_basic(trade_date, ts_code)           → 查某天某只股票
  get_bak_basic_by_date(trade_date)             → 查某天全市场
  get_bak_basic_history(ts_code, start, end)    → 查某只股票历史区间
  get_bak_basic_by_industry(trade_date, industry) → 查某天某个行业
"""

from typing import Optional
from service.db import query


def get_bak_basic(trade_date: str, ts_code: str) -> list[dict]:
    """
    查询某天某只股票的盘后指标

    参数：
        trade_date: 交易日期 YYYYMMDD
        ts_code:    股票代码
    """
    sql = "SELECT * FROM bak_basic WHERE trade_date = %s AND ts_code = %s"
    return query(sql, (trade_date, ts_code))


def get_bak_basic_by_date(trade_date: str,
                          limit: int = 100,
                          offset: int = 0) -> list[dict]:
    """
    查询某天全市场所有股票的盘后快照

    参数：
        trade_date: 交易日期 YYYYMMDD
        limit:      返回条数
        offset:     分页偏移
    """
    sql = "SELECT * FROM bak_basic WHERE trade_date = %s ORDER BY ts_code LIMIT %s OFFSET %s"
    return query(sql, (trade_date, limit, offset))


def get_bak_basic_history(ts_code: str,
                          start_date: str,
                          end_date: str,
                          fields: Optional[list] = None) -> list[dict]:
    """
    查询某只股票一段时间的历史指标变化

    参数：
        ts_code:    股票代码
        start_date: 起始日期 YYYYMMDD
        end_date:   截止日期 YYYYMMDD
        fields:     可选，指定返回字段，如 ["trade_date", "pe", "pb", "eps"]
                    None = 返回所有字段

    返回按 trade_date 升序排列
    """
    if fields:
        cols = ", ".join(fields)
    else:
        cols = "*"

    sql = (
        f"SELECT {cols} FROM bak_basic "
        "WHERE ts_code = %s AND trade_date >= %s AND trade_date <= %s "
        "ORDER BY trade_date"
    )
    return query(sql, (ts_code, start_date, end_date))


def get_bak_basic_by_industry(trade_date: str,
                              industry: str,
                              limit: int = 500) -> list[dict]:
    """
    查询某天某个行业的股票指标

    参数：
        trade_date: 交易日期 YYYYMMDD
        industry:   行业名称（模糊匹配）
        limit:      返回条数
    """
    sql = (
        "SELECT * FROM bak_basic "
        "WHERE trade_date = %s AND industry LIKE %s "
        "ORDER BY ts_code LIMIT %s"
    )
    return query(sql, (trade_date, f"%{industry}%", limit))
