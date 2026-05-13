"""
=============================================================================
股票特色数据查询接口（13个）

包括：卖方盈利预测、筹码分布、技术面因子、中央结算、港股通、集合竞价、
      神奇九转、AH比价、机构调研、券商荐股
=============================================================================

每个函数命名约定：get_<表名>
返回 list[dict]
"""

from typing import Optional
from service.db import query


# ── 1. report_rc: 卖方盈利预测 ──
def get_report_rc(
    ts_code: Optional[str] = None,
    report_date: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    quarter: Optional[str] = None,
    limit: int = 100,
) -> list[dict]:
    """查询卖方盈利预测数据"""
    conds, vals = [], []
    if ts_code: conds.append("ts_code = %s"); vals.append(ts_code)
    if report_date: conds.append("report_date = %s"); vals.append(report_date)
    if start_date: conds.append("report_date >= %s"); vals.append(start_date)
    if end_date: conds.append("report_date <= %s"); vals.append(end_date)
    if quarter: conds.append("quarter = %s"); vals.append(quarter)
    where = " AND ".join(conds) if conds else "1=1"
    rows = query(f"SELECT * FROM report_rc WHERE {where} ORDER BY report_date DESC LIMIT %s", (*vals, limit))
    return [dict(r) for r in rows]


# ── 2. cyq_perf: 每日筹码及胜率 ──
def get_cyq_perf(
    ts_code: Optional[str] = None,
    trade_date: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 100,
) -> list[dict]:
    """查询每日筹码及胜率"""
    conds, vals = [], []
    if ts_code: conds.append("ts_code = %s"); vals.append(ts_code)
    if trade_date: conds.append("trade_date = %s"); vals.append(trade_date)
    if start_date: conds.append("trade_date >= %s"); vals.append(start_date)
    if end_date: conds.append("trade_date <= %s"); vals.append(end_date)
    where = " AND ".join(conds) if conds else "1=1"
    rows = query(f"SELECT * FROM cyq_perf WHERE {where} ORDER BY trade_date DESC LIMIT %s", (*vals, limit))
    return [dict(r) for r in rows]


# ── 3. cyq_chips: 每日筹码分布 ──
def get_cyq_chips(
    ts_code: Optional[str] = None,
    trade_date: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 100,
) -> list[dict]:
    """查询每日筹码分布"""
    conds, vals = [], []
    if ts_code: conds.append("ts_code = %s"); vals.append(ts_code)
    if trade_date: conds.append("trade_date = %s"); vals.append(trade_date)
    if start_date: conds.append("trade_date >= %s"); vals.append(start_date)
    if end_date: conds.append("trade_date <= %s"); vals.append(end_date)
    where = " AND ".join(conds) if conds else "1=1"
    rows = query(f"SELECT * FROM cyq_chips WHERE {where} ORDER BY trade_date DESC, price ASC LIMIT %s", (*vals, limit))
    return [dict(r) for r in rows]


# ── 4. stk_factor_pro: 股票技术面因子 ──
def get_stk_factor_pro(
    ts_code: Optional[str] = None,
    trade_date: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 100,
) -> list[dict]:
    """查询股票技术面因子"""
    conds, vals = [], []
    if ts_code: conds.append("ts_code = %s"); vals.append(ts_code)
    if trade_date: conds.append("trade_date = %s"); vals.append(trade_date)
    if start_date: conds.append("trade_date >= %s"); vals.append(start_date)
    if end_date: conds.append("trade_date <= %s"); vals.append(end_date)
    where = " AND ".join(conds) if conds else "1=1"
    rows = query(f"SELECT * FROM stk_factor_pro WHERE {where} ORDER BY trade_date DESC LIMIT %s", (*vals, limit))
    return [dict(r) for r in rows]


# ── 5. ccass_hold: 中央结算持股汇总 ──
def get_ccass_hold(
    ts_code: Optional[str] = None,
    trade_date: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 100,
) -> list[dict]:
    """查询中央结算系统持股汇总"""
    conds, vals = [], []
    if ts_code: conds.append("ts_code = %s"); vals.append(ts_code)
    if trade_date: conds.append("trade_date = %s"); vals.append(trade_date)
    if start_date: conds.append("trade_date >= %s"); vals.append(start_date)
    if end_date: conds.append("trade_date <= %s"); vals.append(end_date)
    where = " AND ".join(conds) if conds else "1=1"
    rows = query(f"SELECT * FROM ccass_hold WHERE {where} ORDER BY trade_date DESC LIMIT %s", (*vals, limit))
    return [dict(r) for r in rows]


# ── 6. ccass_hold_detail: 中央结算持股明细 ──
def get_ccass_hold_detail(
    ts_code: Optional[str] = None,
    trade_date: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    participant_id: Optional[str] = None,
    limit: int = 100,
) -> list[dict]:
    """查询中央结算系统持股明细"""
    conds, vals = [], []
    if ts_code: conds.append("ts_code = %s"); vals.append(ts_code)
    if trade_date: conds.append("trade_date = %s"); vals.append(trade_date)
    if start_date: conds.append("trade_date >= %s"); vals.append(start_date)
    if end_date: conds.append("trade_date <= %s"); vals.append(end_date)
    if participant_id: conds.append("col_participant_id = %s"); vals.append(participant_id)
    where = " AND ".join(conds) if conds else "1=1"
    rows = query(f"SELECT * FROM ccass_hold_detail WHERE {where} ORDER BY trade_date DESC LIMIT %s", (*vals, limit))
    return [dict(r) for r in rows]


# ── 7. hk_hold: 沪深港股通持股 ──
def get_hk_hold(
    ts_code: Optional[str] = None,
    trade_date: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    exchange: Optional[str] = None,
    limit: int = 100,
) -> list[dict]:
    """查询沪深港股通持股明细"""
    conds, vals = [], []
    if ts_code: conds.append("ts_code = %s"); vals.append(ts_code)
    if trade_date: conds.append("trade_date = %s"); vals.append(trade_date)
    if start_date: conds.append("trade_date >= %s"); vals.append(start_date)
    if end_date: conds.append("trade_date <= %s"); vals.append(end_date)
    if exchange: conds.append("exchange = %s"); vals.append(exchange)
    where = " AND ".join(conds) if conds else "1=1"
    rows = query(f"SELECT * FROM hk_hold WHERE {where} ORDER BY trade_date DESC LIMIT %s", (*vals, limit))
    return [dict(r) for r in rows]


# ── 8. stk_auction_o: 开盘集合竞价 ──
def get_stk_auction_o(
    ts_code: Optional[str] = None,
    trade_date: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 100,
) -> list[dict]:
    """查询股票开盘集合竞价"""
    conds, vals = [], []
    if ts_code: conds.append("ts_code = %s"); vals.append(ts_code)
    if trade_date: conds.append("trade_date = %s"); vals.append(trade_date)
    if start_date: conds.append("trade_date >= %s"); vals.append(start_date)
    if end_date: conds.append("trade_date <= %s"); vals.append(end_date)
    where = " AND ".join(conds) if conds else "1=1"
    rows = query(f"SELECT * FROM stk_auction_o WHERE {where} ORDER BY trade_date DESC LIMIT %s", (*vals, limit))
    return [dict(r) for r in rows]


# ── 9. stk_auction_c: 收盘集合竞价 ──
def get_stk_auction_c(
    ts_code: Optional[str] = None,
    trade_date: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 100,
) -> list[dict]:
    """查询股票收盘集合竞价"""
    conds, vals = [], []
    if ts_code: conds.append("ts_code = %s"); vals.append(ts_code)
    if trade_date: conds.append("trade_date = %s"); vals.append(trade_date)
    if start_date: conds.append("trade_date >= %s"); vals.append(start_date)
    if end_date: conds.append("trade_date <= %s"); vals.append(end_date)
    where = " AND ".join(conds) if conds else "1=1"
    rows = query(f"SELECT * FROM stk_auction_c WHERE {where} ORDER BY trade_date DESC LIMIT %s", (*vals, limit))
    return [dict(r) for r in rows]


# ── 10. stk_nineturn: 神奇九转 ──
def get_stk_nineturn(
    ts_code: Optional[str] = None,
    trade_date: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    freq: Optional[str] = None,
    limit: int = 100,
) -> list[dict]:
    """查询神奇九转指标"""
    conds, vals = [], []
    if ts_code: conds.append("ts_code = %s"); vals.append(ts_code)
    if trade_date: conds.append("trade_date = %s"); vals.append(trade_date)
    if start_date: conds.append("trade_date >= %s"); vals.append(start_date)
    if end_date: conds.append("trade_date <= %s"); vals.append(end_date)
    if freq: conds.append("freq = %s"); vals.append(freq)
    where = " AND ".join(conds) if conds else "1=1"
    rows = query(f"SELECT * FROM stk_nineturn WHERE {where} ORDER BY trade_date DESC LIMIT %s", (*vals, limit))
    return [dict(r) for r in rows]


# ── 11. stk_ah_comparison: AH股比价 ──
def get_stk_ah_comparison(
    ts_code: Optional[str] = None,
    hk_code: Optional[str] = None,
    trade_date: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 100,
) -> list[dict]:
    """查询AH股比价"""
    conds, vals = [], []
    if ts_code: conds.append("ts_code = %s"); vals.append(ts_code)
    if hk_code: conds.append("hk_code = %s"); vals.append(hk_code)
    if trade_date: conds.append("trade_date = %s"); vals.append(trade_date)
    if start_date: conds.append("trade_date >= %s"); vals.append(start_date)
    if end_date: conds.append("trade_date <= %s"); vals.append(end_date)
    where = " AND ".join(conds) if conds else "1=1"
    rows = query(f"SELECT * FROM stk_ah_comparison WHERE {where} ORDER BY trade_date DESC LIMIT %s", (*vals, limit))
    return [dict(r) for r in rows]


# ── 12. stk_surv: 机构调研 ──
def get_stk_surv(
    ts_code: Optional[str] = None,
    surv_date: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 100,
) -> list[dict]:
    """查询机构调研数据"""
    conds, vals = [], []
    if ts_code: conds.append("ts_code = %s"); vals.append(ts_code)
    if surv_date: conds.append("surv_date = %s"); vals.append(surv_date)
    if start_date: conds.append("surv_date >= %s"); vals.append(start_date)
    if end_date: conds.append("surv_date <= %s"); vals.append(end_date)
    where = " AND ".join(conds) if conds else "1=1"
    rows = query(f"SELECT * FROM stk_surv WHERE {where} ORDER BY surv_date DESC LIMIT %s", (*vals, limit))
    return [dict(r) for r in rows]


# ── 13. broker_recommend: 券商荐股 ──
def get_broker_recommend(
    month: Optional[str] = None,
    broker: Optional[str] = None,
    ts_code: Optional[str] = None,
    limit: int = 100,
) -> list[dict]:
    """查询券商每月荐股"""
    conds, vals = [], []
    if month: conds.append("month = %s"); vals.append(month)
    if broker: conds.append("broker = %s"); vals.append(broker)
    if ts_code: conds.append("ts_code = %s"); vals.append(ts_code)
    where = " AND ".join(conds) if conds else "1=1"
    rows = query(f"SELECT * FROM broker_recommend WHERE {where} ORDER BY month DESC LIMIT %s", (*vals, limit))
    return [dict(r) for r in rows]
