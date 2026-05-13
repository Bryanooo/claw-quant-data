"""
业绩预告/快报/分红/主营构成/财报披露查询接口
"""

from service.db import query


# ── 业绩预告 ──

def get_forecast(ts_code: str) -> list[dict]:
    """查询某只股票历史业绩预告"""
    sql = (
        "SELECT * FROM forecast WHERE ts_code = %s "
        "ORDER BY end_date DESC, ann_date DESC"
    )
    return query(sql, (ts_code,))


def get_forecast_by_period(period: str) -> list[dict]:
    """查询某报告期所有业绩预告"""
    sql = (
        "SELECT * FROM forecast WHERE end_date = %s "
        "ORDER BY type, p_change_min"
    )
    return query(sql, (period,))


# ── 业绩快报 ──

def get_express(ts_code: str, limit: int = 4) -> list[dict]:
    """查询某只股票最近N次业绩快报"""
    sql = (
        "SELECT * FROM express WHERE ts_code = %s "
        "ORDER BY end_date DESC LIMIT %s"
    )
    return query(sql, (ts_code, limit))


# ── 分红送股 ──

def get_dividend(ts_code: str, limit: int = 10) -> list[dict]:
    """查询某只股票历史分红记录"""
    sql = (
        "SELECT * FROM dividend WHERE ts_code = %s "
        "ORDER BY end_date DESC LIMIT %s"
    )
    return query(sql, (ts_code, limit))


def get_dividend_upcoming(after_date: str) -> list[dict]:
    """查询在指定日期后的除权除息"""
    sql = (
        "SELECT * FROM dividend "
        "WHERE ex_date >= %s AND div_proc = '实施' "
        "ORDER BY ex_date"
    )
    return query(sql, (after_date,))


# ── 主营业务构成 ──

def get_mainbz(ts_code: str, period: str) -> list[dict]:
    """查询某只股票某报告期主营业务构成"""
    sql = (
        "SELECT * FROM fina_mainbz "
        "WHERE ts_code = %s AND end_date = %s "
        "ORDER BY bz_sales DESC"
    )
    return query(sql, (ts_code, period))


def get_mainbz_by_industry(period: str, industry_code: str, top_n: int = 10) -> list[dict]:
    """查询某行业在某报告期的营收TOP公司"""
    sql = (
        "SELECT ts_code, end_date, bz_item, bz_sales, bz_profit "
        "FROM fina_mainbz "
        "WHERE end_date = %s AND bz_code = 'I' AND bz_item = %s "
        "ORDER BY bz_sales DESC LIMIT %s"
    )
    return query(sql, (period, industry_code, top_n))


# ── 财报披露计划 ──

def get_disclosure_date(ts_code: str) -> list[dict]:
    """查询某只股票历史财报披露计划"""
    sql = (
        "SELECT * FROM disclosure_date WHERE ts_code = %s "
        "ORDER BY end_date DESC"
    )
    return query(sql, (ts_code,))


def get_upcoming_disclosures(end_date: str) -> list[dict]:
    """查询某报告期所有已披露/待披露"""
    sql = "SELECT * FROM disclosure_date WHERE end_date = %s ORDER BY actual_date"
    return query(sql, (end_date,))


def get_next_earnings(days: int = 7) -> list[dict]:
    """查询未来N天内的财报披露"""
    from datetime import date, timedelta
    start = date.today()
    end = start + timedelta(days=days)
    sql = (
        "SELECT * FROM disclosure_date "
        "WHERE pre_date >= %s AND pre_date <= %s "
        "ORDER BY pre_date"
    )
    return query(sql, (start.strftime("%Y%m%d"), end.strftime("%Y%m%d")))
