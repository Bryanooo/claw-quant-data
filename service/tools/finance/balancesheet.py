"""
资产负债表查询接口
"""

from service.db import query


def get_balancesheet(ts_code: str, start_date: str, end_date: str) -> list[dict]:
    """查询某只股票历史资产负债表"""
    sql = (
        "SELECT * FROM balancesheet "
        "WHERE ts_code = %s AND end_date >= %s AND end_date <= %s "
        "ORDER BY end_date DESC"
    )
    return query(sql, (ts_code, start_date, end_date))


def get_balancesheet_by_period(period: str) -> list[dict]:
    """查询某报告期全市场资产负债表"""
    sql = "SELECT * FROM balancesheet WHERE end_date = %s AND report_type = 1 ORDER BY total_assets DESC"
    return query(sql, (period,))


def get_balancesheet_summary(ts_code: str, period_count: int = 4) -> list[dict]:
    """最近N期资产负债表概要"""
    sql = (
        "SELECT ts_code, end_date, total_assets, total_liab, "
        "  total_hldr_eqy_inc_min_int, accounts_receiv, inventories, "
        "  money_cap, fix_assets, goodwill, st_borr, lt_borr "
        "FROM balancesheet WHERE ts_code = %s AND report_type = 1 "
        "ORDER BY end_date DESC LIMIT %s"
    )
    return query(sql, (ts_code, period_count))
