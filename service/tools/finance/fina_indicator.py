"""
财务指标查询接口
"""

from service.db import query


def get_fina_indicator(ts_code: str, start_date: str, end_date: str) -> list[dict]:
    """查询某只股票历史财务指标"""
    sql = (
        "SELECT * FROM fina_indicator "
        "WHERE ts_code = %s AND end_date >= %s AND end_date <= %s "
        "ORDER BY end_date DESC"
    )
    return query(sql, (ts_code, start_date, end_date))


def get_fina_indicator_by_period(period: str) -> list[dict]:
    """查询某报告期全市场财务指标"""
    sql = "SELECT * FROM fina_indicator WHERE end_date = %s ORDER BY roe DESC LIMIT 5000"
    return query(sql, (period,))


def get_fina_indicator_ratings(period: str, top_n: int = 10) -> list[dict]:
    """某报告期排名前N的股票（按ROE）"""
    sql = (
        "SELECT ts_code, eps, roe, roa, roic, bps, debt_to_assets, "
        "  grossprofit_margin, netprofit_margin "
        "FROM fina_indicator WHERE end_date = %s "
        "ORDER BY roe DESC LIMIT %s"
    )
    return query(sql, (period, top_n))
