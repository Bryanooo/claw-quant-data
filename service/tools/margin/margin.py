"""
两融数据查询接口
"""

from typing import Optional
from service.db import query


def get_margin(
    trade_date: Optional[str] = None,
    exchange_id: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 100,
) -> list[dict]:
    """融资融券交易汇总"""
    conds, vals = [], []
    if trade_date: conds.append("trade_date = %s"); vals.append(trade_date)
    if exchange_id: conds.append("exchange_id = %s"); vals.append(exchange_id)
    if start_date: conds.append("trade_date >= %s"); vals.append(start_date)
    if end_date: conds.append("trade_date <= %s"); vals.append(end_date)
    where = " AND ".join(conds) if conds else "1=1"
    return [dict(r) for r in query(f"SELECT * FROM margin WHERE {where} ORDER BY trade_date DESC LIMIT %s", (*vals, limit))]


def get_margin_detail(
    ts_code: Optional[str] = None,
    trade_date: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 100,
) -> list[dict]:
    """融资融券交易明细"""
    conds, vals = [], []
    if ts_code: conds.append("ts_code = %s"); vals.append(ts_code)
    if trade_date: conds.append("trade_date = %s"); vals.append(trade_date)
    if start_date: conds.append("trade_date >= %s"); vals.append(start_date)
    if end_date: conds.append("trade_date <= %s"); vals.append(end_date)
    where = " AND ".join(conds) if conds else "1=1"
    return [dict(r) for r in query(f"SELECT * FROM margin_detail WHERE {where} ORDER BY trade_date DESC LIMIT %s", (*vals, limit))]


def get_margin_secs(
    trade_date: Optional[str] = None,
    exchange: Optional[str] = None,
    limit: int = 100,
) -> list[dict]:
    """融资融券标的"""
    conds, vals = [], []
    if trade_date: conds.append("trade_date = %s"); vals.append(trade_date)
    if exchange: conds.append("exchange = %s"); vals.append(exchange)
    where = " AND ".join(conds) if conds else "1=1"
    return [dict(r) for r in query(f"SELECT * FROM margin_secs WHERE {where} ORDER BY ts_code LIMIT %s", (*vals, limit))]


def get_slb_len(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 100,
) -> list[dict]:
    """转融资交易汇总"""
    conds, vals = [], []
    if start_date: conds.append("trade_date >= %s"); vals.append(start_date)
    if end_date: conds.append("trade_date <= %s"); vals.append(end_date)
    where = " AND ".join(conds) if conds else "1=1"
    return [dict(r) for r in query(f"SELECT * FROM slb_len WHERE {where} ORDER BY trade_date DESC LIMIT %s", (*vals, limit))]
