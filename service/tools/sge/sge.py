"""
上海黄金交易所（SGE）现货数据查询接口

函数：
  get_sge_basic()                              → 全量现货合约信息
  get_sge_daily(ts_code, start_date, end_date) → 单合约历史日线
  get_sge_daily_by_date(trade_date)            → 某天全市场日线
  get_sge_daily_by_tscode_all(ts_code)         → 某合约所有日线
  get_sge_daily_latest(limit)                  → 所有合约最新行情
"""

from typing import Optional
from service.db import query


def get_sge_basic() -> list[dict]:
    """获取上海黄金交易所全部现货合约基础信息"""
    rows = query("SELECT * FROM sge_basic ORDER BY ts_code")
    return [dict(r) for r in rows]


def get_sge_daily(
    ts_code: str,
    start_date: str = "20240101",
    end_date: str = "20250513",
    limit: int = 1000,
) -> list[dict]:
    """获取某现货合约历史日线

    Args:
        ts_code: 合约代码，如 Au99.99 / Ag(T+D)
        start_date: YYYYMMDD
        end_date: YYYYMMDD
        limit: 最大条数
    """
    rows = query(
        """SELECT * FROM sge_daily
           WHERE ts_code = %s AND trade_date BETWEEN %s AND %s
           ORDER BY trade_date DESC LIMIT %s""",
        (ts_code, start_date, end_date, limit),
    )
    return [dict(r) for r in rows]


def get_sge_daily_by_date(trade_date: str) -> list[dict]:
    """获取某交易日全市场现货合约行情

    Args:
        trade_date: YYYYMMDD
    """
    rows = query(
        "SELECT * FROM sge_daily WHERE trade_date = %s ORDER BY ts_code",
        (trade_date,),
    )
    return [dict(r) for r in rows]


def get_sge_daily_latest(limit: int = 15) -> list[dict]:
    """获取所有合约最新日行情"""
    rows = query(
        """SELECT d.* FROM sge_daily d
           INNER JOIN (
               SELECT ts_code, max(trade_date) AS max_date
               FROM sge_daily GROUP BY ts_code
           ) latest ON d.ts_code = latest.ts_code AND d.trade_date = latest.max_date
           ORDER BY d.ts_code LIMIT %s""",
        (limit,),
    )
    return [dict(r) for r in rows]


def get_sge_daily_all_tscode(ts_code: str, limit: int = 2000) -> list[dict]:
    """获取某合约全部日线（按日期降序）

    Args:
        ts_code: 合约代码
        limit: 最大条数
    """
    rows = query(
        "SELECT * FROM sge_daily WHERE ts_code = %s ORDER BY trade_date DESC LIMIT %s",
        (ts_code, limit),
    )
    return [dict(r) for r in rows]
