"""
现金流量表查询接口
"""

from service.db import query


def get_cashflow(ts_code: str, start_date: str, end_date: str) -> list[dict]:
    """查询某只股票历史现金流量表"""
    sql = (
        "SELECT * FROM cashflow "
        "WHERE ts_code = %s AND end_date >= %s AND end_date <= %s "
        "ORDER BY end_date DESC"
    )
    return query(sql, (ts_code, start_date, end_date))


def get_cashflow_summary(ts_code: str, period_count: int = 4) -> list[dict]:
    """最近N期现金流概要"""
    sql = (
        "SELECT ts_code, end_date, "
        "  n_cashflow_act, n_cashflow_inv_act, n_cash_flows_fnc_act, "
        "  free_cashflow, n_incr_cash_cash_equ, c_cash_equ_end_period "
        "FROM cashflow WHERE ts_code = %s AND report_type = 1 "
        "ORDER BY end_date DESC LIMIT %s"
    )
    return query(sql, (ts_code, period_count))
