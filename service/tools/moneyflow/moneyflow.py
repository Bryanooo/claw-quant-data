"""
=============================================================================
资金流向数据服务接口（8张表）
=============================================================================

纯查询函数（无 @mcp.tool），供 service/tools/__init__.py 统一导出。

Tushare 接口对照：
  moneyflow        — https://tushare.pro/document/2?doc_id=340
  moneyflow_ths    — https://tushare.pro/document/2?doc_id=347
  moneyflow_dc     — https://tushare.pro/document/2?doc_id=349
  moneyflow_cnt_ths— https://tushare.pro/document/2?doc_id=348
  moneyflow_ind_ths— https://tushare.pro/document/2?doc_id=264
  moneyflow_ind_dc — https://tushare.pro/document/2?doc_id=350
  moneyflow_mkt_dc — https://tushare.pro/document/2?doc_id=351
  moneyflow_hsgt   — https://tushare.pro/document/2?doc_id=47
"""

from typing import Optional
from service.db import query

# ──────────────────────────────────────────────
# 1. moneyflow — 个股资金流向
# ──────────────────────────────────────────────


def get_moneyflow(trade_date: str, ts_code: str = None) -> list[dict]:
    """查询个股资金流向，指定日期 + 可选股票"""
    if ts_code:
        sql = "SELECT * FROM moneyflow WHERE trade_date = %s AND ts_code = %s"
        return query(sql, (trade_date, ts_code))
    sql = "SELECT * FROM moneyflow WHERE trade_date = %s ORDER BY ts_code"
    return query(sql, (trade_date,))


def get_moneyflow_by_date(trade_date: str, limit: int = 100, offset: int = 0) -> list[dict]:
    """查询某日全市场个股资金流向"""
    sql = "SELECT * FROM moneyflow WHERE trade_date = %s ORDER BY ts_code LIMIT %s OFFSET %s"
    return query(sql, (trade_date, limit, offset))


def get_moneyflow_by_stock(ts_code: str, start: str = None, end: str = None) -> list[dict]:
    """查询某只股票历史资金流向"""
    if start and end:
        sql = "SELECT * FROM moneyflow WHERE ts_code = %s AND trade_date >= %s AND trade_date <= %s ORDER BY trade_date"
        return query(sql, (ts_code, start, end))
    sql = "SELECT * FROM moneyflow WHERE ts_code = %s ORDER BY trade_date"
    return query(sql, (ts_code,))


# ──────────────────────────────────────────────
# 2. moneyflow_ths — 个股资金流向(THS)
# ──────────────────────────────────────────────


def get_moneyflow_ths(trade_date: str, ts_code: str = None) -> list[dict]:
    """查询同花顺个股资金流向"""
    if ts_code:
        sql = "SELECT * FROM moneyflow_ths WHERE trade_date = %s AND ts_code = %s"
        return query(sql, (trade_date, ts_code))
    sql = "SELECT * FROM moneyflow_ths WHERE trade_date = %s ORDER BY ts_code"
    return query(sql, (trade_date,))


def get_moneyflow_ths_by_date(trade_date: str, limit: int = 100, offset: int = 0) -> list[dict]:
    """查询某日全市场同花顺个股资金流向"""
    sql = "SELECT * FROM moneyflow_ths WHERE trade_date = %s ORDER BY ts_code LIMIT %s OFFSET %s"
    return query(sql, (trade_date, limit, offset))


def get_moneyflow_ths_by_stock(ts_code: str, start: str = None, end: str = None) -> list[dict]:
    """查询某只股票同花顺资金流向历史"""
    if start and end:
        sql = "SELECT * FROM moneyflow_ths WHERE ts_code = %s AND trade_date >= %s AND trade_date <= %s ORDER BY trade_date"
        return query(sql, (ts_code, start, end))
    sql = "SELECT * FROM moneyflow_ths WHERE ts_code = %s ORDER BY trade_date"
    return query(sql, (ts_code,))


# ──────────────────────────────────────────────
# 3. moneyflow_dc — 个股资金流向(DC)
# ──────────────────────────────────────────────


def get_moneyflow_dc(trade_date: str, ts_code: str = None) -> list[dict]:
    """查询东方财富个股资金流向"""
    if ts_code:
        sql = "SELECT * FROM moneyflow_dc WHERE trade_date = %s AND ts_code = %s"
        return query(sql, (trade_date, ts_code))
    sql = "SELECT * FROM moneyflow_dc WHERE trade_date = %s ORDER BY ts_code"
    return query(sql, (trade_date,))


def get_moneyflow_dc_by_date(trade_date: str, limit: int = 100, offset: int = 0) -> list[dict]:
    """查询某日全市场东方财富个股资金流向"""
    sql = "SELECT * FROM moneyflow_dc WHERE trade_date = %s ORDER BY ts_code LIMIT %s OFFSET %s"
    return query(sql, (trade_date, limit, offset))


def get_moneyflow_dc_by_stock(ts_code: str, start: str = None, end: str = None) -> list[dict]:
    """查询某只股票东方财富资金流向历史"""
    if start and end:
        sql = "SELECT * FROM moneyflow_dc WHERE ts_code = %s AND trade_date >= %s AND trade_date <= %s ORDER BY trade_date"
        return query(sql, (ts_code, start, end))
    sql = "SELECT * FROM moneyflow_dc WHERE ts_code = %s ORDER BY trade_date"
    return query(sql, (ts_code,))


# ──────────────────────────────────────────────
# 4. moneyflow_cnt_ths — 同花顺概念板块资金流向
# ──────────────────────────────────────────────


def get_moneyflow_cnt_ths(trade_date: str, ts_code: str = None) -> list[dict]:
    """查询同花顺概念板块资金流向"""
    if ts_code:
        sql = "SELECT * FROM moneyflow_cnt_ths WHERE trade_date = %s AND ts_code = %s"
        return query(sql, (trade_date, ts_code))
    sql = "SELECT * FROM moneyflow_cnt_ths WHERE trade_date = %s ORDER BY ts_code"
    return query(sql, (trade_date,))


def get_moneyflow_cnt_ths_by_date(trade_date: str, limit: int = 100, offset: int = 0) -> list[dict]:
    """查询某日同花顺全部概念板块资金流向"""
    sql = "SELECT * FROM moneyflow_cnt_ths WHERE trade_date = %s ORDER BY ts_code LIMIT %s OFFSET %s"
    return query(sql, (trade_date, limit, offset))


def get_moneyflow_cnt_ths_history(ts_code: str, start: str = None, end: str = None) -> list[dict]:
    """查询某个概念板块历史资金流向"""
    if start and end:
        sql = "SELECT * FROM moneyflow_cnt_ths WHERE ts_code = %s AND trade_date >= %s AND trade_date <= %s ORDER BY trade_date"
        return query(sql, (ts_code, start, end))
    sql = "SELECT * FROM moneyflow_cnt_ths WHERE ts_code = %s ORDER BY trade_date"
    return query(sql, (ts_code,))


# ──────────────────────────────────────────────
# 5. moneyflow_ind_ths — 同花顺行业资金流向
# ──────────────────────────────────────────────


def get_moneyflow_ind_ths(trade_date: str, ts_code: str = None) -> list[dict]:
    """查询同花顺行业资金流向"""
    if ts_code:
        sql = "SELECT * FROM moneyflow_ind_ths WHERE trade_date = %s AND ts_code = %s"
        return query(sql, (trade_date, ts_code))
    sql = "SELECT * FROM moneyflow_ind_ths WHERE trade_date = %s ORDER BY ts_code"
    return query(sql, (trade_date,))


def get_moneyflow_ind_ths_by_date(trade_date: str, limit: int = 100, offset: int = 0) -> list[dict]:
    """查询某日同花顺全部行业资金流向"""
    sql = "SELECT * FROM moneyflow_ind_ths WHERE trade_date = %s ORDER BY ts_code LIMIT %s OFFSET %s"
    return query(sql, (trade_date, limit, offset))


def get_moneyflow_ind_ths_history(ts_code: str, start: str = None, end: str = None) -> list[dict]:
    """查询某个行业历史资金流向"""
    if start and end:
        sql = "SELECT * FROM moneyflow_ind_ths WHERE ts_code = %s AND trade_date >= %s AND trade_date <= %s ORDER BY trade_date"
        return query(sql, (ts_code, start, end))
    sql = "SELECT * FROM moneyflow_ind_ths WHERE ts_code = %s ORDER BY trade_date"
    return query(sql, (ts_code,))


# ──────────────────────────────────────────────
# 6. moneyflow_ind_dc — 东财板块资金流向
# ──────────────────────────────────────────────


def get_moneyflow_ind_dc(trade_date: str, content_type: str = None) -> list[dict]:
    """查询东财板块资金流向，可选 content_type（行业/概念）"""
    if content_type:
        sql = "SELECT * FROM moneyflow_ind_dc WHERE trade_date = %s AND content_type = %s ORDER BY rank"
        return query(sql, (trade_date, content_type))
    sql = "SELECT * FROM moneyflow_ind_dc WHERE trade_date = %s ORDER BY content_type, rank"
    return query(sql, (trade_date,))


def get_moneyflow_ind_dc_by_date(trade_date: str, content_type: str, limit: int = 100, offset: int = 0) -> list[dict]:
    """查询某日东财某类板块资金流向"""
    sql = "SELECT * FROM moneyflow_ind_dc WHERE trade_date = %s AND content_type = %s ORDER BY rank LIMIT %s OFFSET %s"
    return query(sql, (trade_date, content_type, limit, offset))


def get_moneyflow_ind_dc_by_sector(ts_code: str, content_type: str, start: str = None, end: str = None) -> list[dict]:
    """查询某个东财板块历史资金流向"""
    if start and end:
        sql = "SELECT * FROM moneyflow_ind_dc WHERE ts_code = %s AND content_type = %s AND trade_date >= %s AND trade_date <= %s ORDER BY trade_date"
        return query(sql, (ts_code, content_type, start, end))
    sql = "SELECT * FROM moneyflow_ind_dc WHERE ts_code = %s AND content_type = %s ORDER BY trade_date"
    return query(sql, (ts_code, content_type))


# ──────────────────────────────────────────────
# 7. moneyflow_mkt_dc — 大盘资金流向(DC)
# ──────────────────────────────────────────────


def get_moneyflow_mkt_dc(trade_date: str = None) -> list[dict]:
    """查询大盘资金流向，指定日期或最近"""
    if trade_date:
        sql = "SELECT * FROM moneyflow_mkt_dc WHERE trade_date = %s"
        return query(sql, (trade_date,))
    sql = "SELECT * FROM moneyflow_mkt_dc ORDER BY trade_date DESC LIMIT 1"
    return query(sql)


def get_moneyflow_mkt_dc_history(start: str, end: str) -> list[dict]:
    """查询大盘资金流向历史区间"""
    sql = "SELECT * FROM moneyflow_mkt_dc WHERE trade_date >= %s AND trade_date <= %s ORDER BY trade_date"
    return query(sql, (start, end))


# ──────────────────────────────────────────────
# 8. moneyflow_hsgt — 沪深港通资金流向
# ──────────────────────────────────────────────


def get_moneyflow_hsgt(trade_date: str = None) -> list[dict]:
    """查询沪深港通资金流向，指定日期或最近"""
    if trade_date:
        sql = "SELECT * FROM moneyflow_hsgt WHERE trade_date = %s"
        return query(sql, (trade_date,))
    sql = "SELECT * FROM moneyflow_hsgt ORDER BY trade_date DESC LIMIT 1"
    return query(sql)


def get_moneyflow_hsgt_history(start: str, end: str) -> list[dict]:
    """查询沪深港通资金流向历史区间"""
    sql = "SELECT * FROM moneyflow_hsgt WHERE trade_date >= %s AND trade_date <= %s ORDER BY trade_date"
    return query(sql, (start, end))


def get_moneyflow_hsgt_latest(n: int = 5) -> list[dict]:
    """查询最近 N 天沪深港通资金流向"""
    sql = "SELECT * FROM moneyflow_hsgt ORDER BY trade_date DESC LIMIT %s"
    return query(sql, (n,))
