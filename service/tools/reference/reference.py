"""
股票参考数据查询接口（12个）

函数：
  get_stk_shock, get_stk_high_shock, get_stk_alert              → 异常波动类
  get_top10_holders, get_top10_floatholders                       → 十大股东类
  get_pledge_stat, get_pledge_detail                               → 股权质押类
  get_repurchase                                                    → 股票回购
  get_share_float                                                   → 限售股解禁
  get_block_trade                                                   → 大宗交易
  get_stk_holdernumber                                              → 股东人数
  get_stk_holdertrade                                               → 股东增减持
"""

from typing import Optional
from service.db import query


# ── 异常波动类 ──

def get_stk_shock(
    ts_code: Optional[str] = None,
    trade_date: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 100,
) -> list[dict]:
    """查询个股异常波动"""
    conds, vals = [], []
    if ts_code: conds.append("ts_code = %s"); vals.append(ts_code)
    if trade_date: conds.append("trade_date = %s"); vals.append(trade_date)
    if start_date: conds.append("trade_date >= %s"); vals.append(start_date)
    if end_date: conds.append("trade_date <= %s"); vals.append(end_date)
    where = " AND ".join(conds) if conds else "1=1"
    rows = query(f"SELECT * FROM stk_shock WHERE {where} ORDER BY trade_date DESC LIMIT %s", (*vals, limit))
    return [dict(r) for r in rows]


def get_stk_high_shock(
    ts_code: Optional[str] = None,
    trade_date: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 100,
) -> list[dict]:
    """查询个股严重异常波动"""
    conds, vals = [], []
    if ts_code: conds.append("ts_code = %s"); vals.append(ts_code)
    if trade_date: conds.append("trade_date = %s"); vals.append(trade_date)
    if start_date: conds.append("trade_date >= %s"); vals.append(start_date)
    if end_date: conds.append("trade_date <= %s"); vals.append(end_date)
    where = " AND ".join(conds) if conds else "1=1"
    rows = query(f"SELECT * FROM stk_high_shock WHERE {where} ORDER BY trade_date DESC LIMIT %s", (*vals, limit))
    return [dict(r) for r in rows]


def get_stk_alert(
    ts_code: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 100,
) -> list[dict]:
    """查询交易所重点提示证券"""
    conds, vals = [], []
    if ts_code: conds.append("ts_code = %s"); vals.append(ts_code)
    if start_date: conds.append("start_date >= %s"); vals.append(start_date)
    if end_date: conds.append("end_date <= %s"); vals.append(end_date)
    where = " AND ".join(conds) if conds else "1=1"
    rows = query(f"SELECT * FROM stk_alert WHERE {where} ORDER BY start_date DESC LIMIT %s", (*vals, limit))
    return [dict(r) for r in rows]


# ── 十大股东类 ──

def get_top10_holders(
    ts_code: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 50,
) -> list[dict]:
    """查询前十大股东"""
    conds, vals = ["ts_code = %s"], [ts_code]
    if start_date: conds.append("end_date >= %s"); vals.append(start_date)
    if end_date: conds.append("end_date <= %s"); vals.append(end_date)
    where = " AND ".join(conds)
    rows = query(f"SELECT * FROM top10_holders WHERE {where} ORDER BY end_date DESC, hold_amount DESC LIMIT %s", (*vals, limit))
    return [dict(r) for r in rows]


def get_top10_floatholders(
    ts_code: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 50,
) -> list[dict]:
    """查询前十大流通股东"""
    conds, vals = ["ts_code = %s"], [ts_code]
    if start_date: conds.append("end_date >= %s"); vals.append(start_date)
    if end_date: conds.append("end_date <= %s"); vals.append(end_date)
    where = " AND ".join(conds)
    rows = query(f"SELECT * FROM top10_floatholders WHERE {where} ORDER BY end_date DESC, hold_amount DESC LIMIT %s", (*vals, limit))
    return [dict(r) for r in rows]


# ── 股权质押类 ──

def get_pledge_stat(
    ts_code: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 100,
) -> list[dict]:
    """查询股权质押统计"""
    conds, vals = [], []
    if ts_code: conds.append("ts_code = %s"); vals.append(ts_code)
    if end_date: conds.append("end_date = %s"); vals.append(end_date)
    where = " AND ".join(conds) if conds else "1=1"
    rows = query(f"SELECT * FROM pledge_stat WHERE {where} ORDER BY end_date DESC LIMIT %s", (*vals, limit))
    return [dict(r) for r in rows]


def get_pledge_detail(
    ts_code: str,
    limit: int = 100,
) -> list[dict]:
    """查询股权质押明细"""
    rows = query("SELECT * FROM pledge_detail WHERE ts_code = %s ORDER BY ann_date DESC LIMIT %s", (ts_code, limit))
    return [dict(r) for r in rows]


# ── 股票回购 ──

def get_repurchase(
    ts_code: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 100,
) -> list[dict]:
    """查询股票回购"""
    conds, vals = [], []
    if ts_code: conds.append("ts_code = %s"); vals.append(ts_code)
    if start_date: conds.append("ann_date >= %s"); vals.append(start_date)
    if end_date: conds.append("ann_date <= %s"); vals.append(end_date)
    where = " AND ".join(conds) if conds else "1=1"
    rows = query(f"SELECT * FROM repurchase WHERE {where} ORDER BY ann_date DESC LIMIT %s", (*vals, limit))
    return [dict(r) for r in rows]


# ── 限售股解禁 ──

def get_share_float(
    ts_code: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 100,
) -> list[dict]:
    """查询限售股解禁"""
    conds, vals = [], []
    if ts_code: conds.append("ts_code = %s"); vals.append(ts_code)
    if start_date: conds.append("float_date >= %s"); vals.append(start_date)
    if end_date: conds.append("float_date <= %s"); vals.append(end_date)
    where = " AND ".join(conds) if conds else "1=1"
    rows = query(f"SELECT * FROM share_float WHERE {where} ORDER BY float_date DESC LIMIT %s", (*vals, limit))
    return [dict(r) for r in rows]


# ── 大宗交易 ──

def get_block_trade(
    ts_code: Optional[str] = None,
    trade_date: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 100,
) -> list[dict]:
    """查询大宗交易"""
    conds, vals = [], []
    if ts_code: conds.append("ts_code = %s"); vals.append(ts_code)
    if trade_date: conds.append("trade_date = %s"); vals.append(trade_date)
    if start_date: conds.append("trade_date >= %s"); vals.append(start_date)
    if end_date: conds.append("trade_date <= %s"); vals.append(end_date)
    where = " AND ".join(conds) if conds else "1=1"
    rows = query(f"SELECT * FROM block_trade WHERE {where} ORDER BY trade_date DESC, amount DESC LIMIT %s", (*vals, limit))
    return [dict(r) for r in rows]


# ── 股东人数 ──

def get_stk_holdernumber(
    ts_code: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 50,
) -> list[dict]:
    """查询股东人数"""
    conds, vals = [], []
    if ts_code: conds.append("ts_code = %s"); vals.append(ts_code)
    if start_date: conds.append("end_date >= %s"); vals.append(start_date)
    if end_date: conds.append("end_date <= %s"); vals.append(end_date)
    where = " AND ".join(conds) if conds else "1=1"
    rows = query(f"SELECT * FROM stk_holdernumber WHERE {where} ORDER BY end_date DESC LIMIT %s", (*vals, limit))
    return [dict(r) for r in rows]


# ── 股东增减持 ──

def get_stk_holdertrade(
    ts_code: Optional[str] = None,
    trade_type: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 100,
) -> list[dict]:
    """查询股东增减持

    Args:
        ts_code: 股票代码
        trade_type: IN 增持 / DE 减持
        start_date / end_date: 公告日期范围 YYYYMMDD
    """
    conds, vals = [], []
    if ts_code: conds.append("ts_code = %s"); vals.append(ts_code)
    if trade_type: conds.append("in_de = %s"); vals.append(trade_type)
    if start_date: conds.append("ann_date >= %s"); vals.append(start_date)
    if end_date: conds.append("ann_date <= %s"); vals.append(end_date)
    where = " AND ".join(conds) if conds else "1=1"
    rows = query(f"SELECT * FROM stk_holdertrade WHERE {where} ORDER BY ann_date DESC, change_vol DESC LIMIT %s", (*vals, limit))
    return [dict(r) for r in rows]
