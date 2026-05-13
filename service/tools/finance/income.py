"""
利润表查询接口

从本地 income 表查询上市公司利润表数据。

函数：
  get_income(ts_code, start_date, end_date)            → 某只股票历史利润表
  get_income_by_period(period)                          → 某报告期全市场
  get_income_summary(ts_code, period_count)             → 最近 N 期概要
"""

from typing import Optional
from service.db import query


def get_income(ts_code: str, start_date: str, end_date: str) -> list[dict]:
    """查询某只股票历史利润表区间"""
    sql = (
        "SELECT * FROM income "
        "WHERE ts_code = %s AND end_date >= %s AND end_date <= %s "
        "ORDER BY end_date DESC"
    )
    return query(sql, (ts_code, start_date, end_date))


def get_income_by_period(period: str, report_type: int = 1) -> list[dict]:
    """查询某报告期全市场利润表"""
    sql = (
        "SELECT * FROM income "
        "WHERE end_date = %s AND report_type = %s "
        "ORDER BY n_income_attr_p DESC"
    )
    return query(sql, (period, report_type))


def get_income_summary(ts_code: str, period_count: int = 4) -> list[dict]:
    """查询某只股票最近 N 期关键财务指标"""
    sql = (
        "SELECT ts_code, end_date, report_type, ann_date, "
        "  revenue, total_profit, n_income, n_income_attr_p, "
        "  basic_eps, diluted_eps, operate_profit, rd_exp "
        "FROM income "
        "WHERE ts_code = %s AND report_type = 1 "
        "ORDER BY end_date DESC LIMIT %s"
    )
    return query(sql, (ts_code, period_count))
