"""
=============================================================================
交易日历查询接口
=============================================================================

提供交易日相关的纯查询工具函数，供投研 Agent 调用。

函数清单：
  is_trade_day(date)         → bool         判断某天是否为交易日
  get_trade_days(start, end) → list[str]    获取日期范围内的所有交易日
  get_last_trade_day(date)   → str          获取上一个交易日
  get_next_trade_day(date)   → str          获取下一个交易日
  get_trade_calendar(year)   → list[dict]   获取某年全部日历数据

依赖：
  service/db.py  — 数据库连接
  trade_cal 表    — 必须有数据
"""

from datetime import datetime, date, timedelta
from typing import Optional, Union

from service.db import query

# ──────────────────────────────────────────────
# 日期工具
# ──────────────────────────────────────────────
_DATE_FMT = "%Y%m%d"


def _fmt(d: Union[str, date, datetime]) -> str:
    """统一转成 YYYYMMDD 字符串"""
    if isinstance(d, str):
        return d.replace("-", "")
    return d.strftime(_DATE_FMT)


def _parse(d: str) -> date:
    """YYYYMMDD → date"""
    return datetime.strptime(d, _DATE_FMT).date()


# ──────────────────────────────────────────────
# 查询接口
# ──────────────────────────────────────────────
def is_trade_day(d: Union[str, date, datetime] = None,
                 exchange: str = "SSE") -> bool:
    """
    判断某天是否为交易日。

    参数：
      d:        日期，默认今天
      exchange: 交易所，默认 SSE

    返回：
      True=交易日 / False=休市日

    示例：
      is_trade_day()               → True/False（判断今天）
      is_trade_day("20260512")     → True
      is_trade_day("20260501")     → False（劳动节）
      is_trade_day("20250101")     → False（元旦）
    """
    if d is None:
        d = date.today()
    day = _fmt(d)
    rows = query(
        "SELECT is_open FROM trade_cal "
        "WHERE exchange = %s AND cal_date = %s",
        (exchange, day),
    )
    if not rows:
        return False
    return rows[0]["is_open"] == 1


def get_trade_days(
    start: Union[str, date, datetime],
    end: Union[str, date, datetime],
    exchange: str = "SSE",
) -> list[str]:
    """
    获取日期范围内的所有交易日（按日期升序）。

    参数：
      start:    起始日期
      end:      截止日期
      exchange: 交易所，默认 SSE

    返回：
      交易日列表，格式 ["20260512", "20260513", ...]

    示例：
      get_trade_days("20260501", "20260515")
      # → ["20260506", "20260507", "20260510", ...]（排除周末和节假日）

      get_trade_days("2025-01-01", "2025-01-10")
    """
    rows = query(
        "SELECT cal_date FROM trade_cal "
        "WHERE exchange = %s AND cal_date >= %s AND cal_date <= %s AND is_open = 1 "
        "ORDER BY cal_date",
        (exchange, _fmt(start), _fmt(end)),
    )
    return [r["cal_date"].strftime(_DATE_FMT) for r in rows]


def get_last_trade_day(
    d: Union[str, date, datetime] = None,
    exchange: str = "SSE",
) -> Optional[str]:
    """
    获取上一个交易日。

    参数：
      d:        参考日期，默认今天
      exchange: 交易所

    返回：
      YYYYMMDD 格式的上一个交易日，若不存在则返回 None

    示例：
      get_last_trade_day("20260512")  # → "20260511"
      get_last_trade_day("20260510")  # → "20260509"（周一→上周五）
    """
    if d is None:
        d = date.today()
    day = _fmt(d)
    rows = query(
        "SELECT pretrade_date FROM trade_cal "
        "WHERE exchange = %s AND cal_date = %s",
        (exchange, day),
    )
    if not rows or rows[0]["pretrade_date"] is None:
        return None
    return rows[0]["pretrade_date"].strftime(_DATE_FMT)


def get_next_trade_day(
    d: Union[str, date, datetime] = None,
    exchange: str = "SSE",
) -> Optional[str]:
    """
    获取下一个交易日。

    参数：
      d:        参考日期，默认今天
      exchange: 交易所

    返回：
      YYYYMMDD 格式的下一个交易日

    示例：
      get_next_trade_day("20260512")  # → "20260513"
      get_next_trade_day("20260509")  # → "20260510"（周五→下周一）
    """
    if d is None:
        d = date.today()
    day = _fmt(d)
    rows = query(
        "SELECT cal_date FROM trade_cal "
        "WHERE exchange = %s AND cal_date > %s AND is_open = 1 "
        "ORDER BY cal_date LIMIT 1",
        (exchange, day),
    )
    if not rows:
        return None
    return rows[0]["cal_date"].strftime(_DATE_FMT)


def get_trade_calendar(
    year: int = None,
    exchange: str = "SSE",
) -> list[dict]:
    """
    获取某年全部日历数据（含节假日标记）。

    参数：
      year:     年份，默认今年
      exchange: 交易所

    返回：
      [{"cal_date": "20260512", "is_open": 1, ...}, ...]

    示例：
      get_trade_calendar(2026)
    """
    if year is None:
        year = date.today().year
    start = f"{year}-01-01"
    end = f"{year}-12-31"
    rows = query(
        "SELECT cal_date, is_open, pretrade_date FROM trade_cal "
        "WHERE exchange = %s "
        "AND cal_date >= %s AND cal_date <= %s "
        "ORDER BY cal_date",
        (exchange, start, end),
    )
    return [
        {
            "cal_date": r["cal_date"].strftime(_DATE_FMT),
            "is_open": r["is_open"],
            "pretrade_date": (
                r["pretrade_date"].strftime(_DATE_FMT)
                if r["pretrade_date"]
                else None
            ),
        }
        for r in rows
    ]
