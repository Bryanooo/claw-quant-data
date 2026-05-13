"""
外汇数据查询接口

从本地 fx_obasic / fx_daily 表查询外汇数据。

函数：
  get_fx_obasic(classify)                       → 外汇基础信息列表
  get_fx_classify_stats()                       → 外汇品种分类统计
  get_fx_daily(ts_code, start_date, end_date)   → 单只外汇历史日线
  get_fx_daily_by_classify(classify, trade_date) → 某分类外汇行情
  get_fx_daily_latest(limit)                    → 所有品种最新行情
"""

from typing import Optional
from service.db import query


def get_fx_obasic(classify: Optional[str] = None) -> list[dict]:
    """获取外汇基础信息列表

    Args:
        classify: 分类（FX/INDEX/COMMODITY/METAL/BUND/CRYPTO/FX_BASKET），留空返回全部
    Returns:
        外汇基础信息列表
    """
    if classify:
        rows = query("SELECT * FROM fx_obasic WHERE classify = %s ORDER BY ts_code", (classify,))
    else:
        rows = query("SELECT * FROM fx_obasic ORDER BY classify, ts_code")
    return [dict(r) for r in rows]


def get_fx_classify_stats() -> list[dict]:
    """获取外汇品种分类统计"""
    rows = query("SELECT classify, count(*) AS cnt FROM fx_obasic GROUP BY classify ORDER BY classify")
    return [dict(r) for r in rows]


def get_fx_daily(
    ts_code: str,
    start_date: str = "20240101",
    end_date: str = "20250513",
    limit: int = 1000,
) -> list[dict]:
    """获取单只外汇历史日线行情

    Args:
        ts_code: 外汇代码，如 USDCNH.FXCM
        start_date: 开始日期 YYYYMMDD
        end_date: 结束日期 YYYYMMDD
        limit: 最大返回条数
    Returns:
        日线行情列表（按日期递减）
    """
    rows = query(
        """SELECT ts_code, trade_date, bid_open, bid_close, bid_high, bid_low,
                  ask_open, ask_close, ask_high, ask_low, tick_qty
           FROM fx_daily
           WHERE ts_code = %s AND trade_date BETWEEN %s AND %s
           ORDER BY trade_date DESC
           LIMIT %s""",
        (ts_code, start_date, end_date, limit),
    )
    return [dict(r) for r in rows]


def get_fx_daily_by_classify(
    classify: str,
    trade_date: Optional[str] = None,
    limit: int = 200,
) -> list[dict]:
    """获取某分类外汇某天行情

    Args:
        classify: 分类（FX/INDEX/COMMODITY 等）
        trade_date: 交易日期 YYYYMMDD，默认取最新
        limit: 最大返回条数
    Returns:
        行情列表
    """
    if trade_date:
        rows = query(
            """SELECT d.* FROM fx_daily d
               JOIN fx_obasic o ON d.ts_code = o.ts_code
               WHERE o.classify = %s AND d.trade_date = %s
               ORDER BY d.ts_code
               LIMIT %s""",
            (classify, trade_date, limit),
        )
    else:
        rows = query(
            """SELECT d.* FROM fx_daily d
               JOIN fx_obasic o ON d.ts_code = o.ts_code
               WHERE o.classify = %s
               AND d.trade_date = (SELECT max(trade_date) FROM fx_daily)
               ORDER BY d.ts_code
               LIMIT %s""",
            (classify, limit),
        )
    return [dict(r) for r in rows]


def get_fx_daily_latest(limit: int = 10) -> list[dict]:
    """获取所有外汇品种最新日行情"""
    rows = query(
        """SELECT d.* FROM fx_daily d
           INNER JOIN (
               SELECT ts_code, max(trade_date) AS max_date
               FROM fx_daily GROUP BY ts_code
           ) latest ON d.ts_code = latest.ts_code AND d.trade_date = latest.max_date
           ORDER BY d.ts_code
           LIMIT %s""",
        (limit,),
    )
    return [dict(r) for r in rows]
