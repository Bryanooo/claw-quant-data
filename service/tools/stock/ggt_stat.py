"""
港股通每日/每月成交统计查询接口

从本地 ggt_daily, ggt_monthly 表查询。

函数：
  get_ggt_daily(start_date, end_date)      → 港股通每日成交统计（区间）
  get_ggt_monthly(start_month, end_month)  → 港股通每月成交统计（区间）
"""

from service.db import query


def get_ggt_daily(start_date: str, end_date: str) -> list[dict]:
    """查询港股通每日成交统计（区间）"""
    sql = (
        "SELECT * FROM ggt_daily "
        "WHERE trade_date >= %s AND trade_date <= %s "
        "ORDER BY trade_date"
    )
    return query(sql, (start_date, end_date))


def get_ggt_monthly(start_month: str, end_month: str) -> list[dict]:
    """查询港股通每月成交统计（区间）"""
    sql = (
        "SELECT * FROM ggt_monthly "
        "WHERE month >= %s AND month <= %s "
        "ORDER BY month"
    )
    return query(sql, (start_month, end_month))
