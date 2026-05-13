"""
stk_weekly_monthly 采集器：周线/月线行情
Tushare 接口:
  - stk_weekly_monthly（每日更新，非周五周线 + 月线）
  - weekly（每周五收盘后）
  - monthly（月最后一个交易日收盘后）
统一单位: vol=万手, amount=万元
"""

import logging
import time
from datetime import date, datetime

import pandas as pd

from collectors.base import BaseCollector, get_db_conn

logger = logging.getLogger("collector.stk_weekly_monthly")


class StkWeeklyMonthlyCollector(BaseCollector):
    INTERFACE_NAME = "stk_weekly_monthly"
    TABLE_NAME = "stk_weekly_monthly"
    PK_COLUMNS = ["ts_code", "trade_date", "freq"]

    def __init__(self):
        super().__init__()
        self.db = get_db_conn()

    def fetch(self, **params):
        """兼容 BaseCollector 抽象方法"""
        return pd.DataFrame()

    def fetch_daily(self, trade_date: str, freq: str):
        """从 stk_weekly_monthly 接口取（每日更新，非周五周线 + 月线）"""
        df = self.pro.stk_weekly_monthly(trade_date=trade_date, freq=freq)
        if df is not None and len(df) > 0:
            logger.info(f"[stk_weekly_monthly] {freq} {trade_date}: {len(df)} 行")
        return df

    def fetch_weekly(self, trade_date: str):
        """从 weekly 接口取（每周五收盘后）"""
        df = self.pro.weekly(trade_date=trade_date)
        if df is not None and len(df) > 0:
            logger.info(f"[weekly] {trade_date}: {len(df)} 行")
        return df

    def fetch_monthly(self, trade_date: str):
        """从 monthly 接口取（每月最后一个交易日收盘后）"""
        df = self.pro.monthly(trade_date=trade_date)
        if df is not None and len(df) > 0:
            logger.info(f"[monthly] {trade_date}: {len(df)} 行")
        return df

    def save_daily(self, df, trade_date: str, freq: str):
        """保存 stk_weekly_monthly 接口数据（vol/amount 已是万手/万元）"""
        if df is None or len(df) == 0:
            return
        with self.db.cursor() as cur:
            for _, r in df.iterrows():
                cur.execute("""
                    INSERT INTO stk_weekly_monthly
                        (ts_code, trade_date, freq, open, high, low, close, pre_close, "change", pct_chg, vol, amount, source)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT (ts_code, trade_date, freq) DO UPDATE SET
                        open=EXCLUDED.open, high=EXCLUDED.high, low=EXCLUDED.low, close=EXCLUDED.close,
                        pre_close=EXCLUDED.pre_close, "change"=EXCLUDED."change", pct_chg=EXCLUDED.pct_chg,
                        vol=EXCLUDED.vol, amount=EXCLUDED.amount, source=EXCLUDED.source, updated_at=NOW()
                """, (
                    r["ts_code"], trade_date, freq,
                    _f(r, "open"), _f(r, "high"), _f(r, "low"), _f(r, "close"), _f(r, "pre_close"),
                    _f(r, "change"), _f(r, "pct_chg"), _f(r, "vol"), _f(r, "amount"),
                    "stk_weekly_monthly"
                ))
        self.db.commit()
        logger.info(f"[stk_weekly_monthly] {freq} {trade_date}: upsert {len(df)} 行")

    def save_weekly(self, df, trade_date: str):
        """保存 weekly 接口数据（vol 从股→万手, amount 从元→万元）"""
        if df is None or len(df) == 0:
            return
        with self.db.cursor() as cur:
            for _, r in df.iterrows():
                vol_wan = round(float(r["vol"]) / 10000, 2) if r.get("vol") else None
                amt_wan = round(float(r["amount"]) / 10000, 2) if r.get("amount") else None
                cur.execute("""
                    INSERT INTO stk_weekly_monthly
                        (ts_code, trade_date, freq, open, high, low, close, pre_close, "change", pct_chg, vol, amount, source)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT (ts_code, trade_date, freq) DO UPDATE SET
                        open=EXCLUDED.open, high=EXCLUDED.high, low=EXCLUDED.low, close=EXCLUDED.close,
                        pre_close=EXCLUDED.pre_close, "change"=EXCLUDED."change", pct_chg=EXCLUDED.pct_chg,
                        vol=EXCLUDED.vol, amount=EXCLUDED.amount, source=EXCLUDED.source, updated_at=NOW()
                """, (
                    r["ts_code"], trade_date, "week",
                    _f(r, "open"), _f(r, "high"), _f(r, "low"), _f(r, "close"), _f(r, "pre_close"),
                    _f(r, "change"), _f(r, "pct_chg"), vol_wan, amt_wan,
                    "weekly"
                ))
        self.db.commit()
        logger.info(f"[weekly] {trade_date}: upsert {len(df)} 行")

    def save_monthly(self, df, trade_date: str):
        """保存 monthly 接口数据（vol 从股→万手, amount 从元→万元）"""
        if df is None or len(df) == 0:
            return
        with self.db.cursor() as cur:
            for _, r in df.iterrows():
                vol_wan = round(float(r["vol"]) / 10000, 2) if r.get("vol") else None
                amt_wan = round(float(r["amount"]) / 10000, 2) if r.get("amount") else None
                cur.execute("""
                    INSERT INTO stk_weekly_monthly
                        (ts_code, trade_date, freq, open, high, low, close, pre_close, "change", pct_chg, vol, amount, source)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT (ts_code, trade_date, freq) DO UPDATE SET
                        open=EXCLUDED.open, high=EXCLUDED.high, low=EXCLUDED.low, close=EXCLUDED.close,
                        pre_close=EXCLUDED.pre_close, "change"=EXCLUDED."change", pct_chg=EXCLUDED.pct_chg,
                        vol=EXCLUDED.vol, amount=EXCLUDED.amount, source=EXCLUDED.source, updated_at=NOW()
                """, (
                    r["ts_code"], trade_date, "month",
                    _f(r, "open"), _f(r, "high"), _f(r, "low"), _f(r, "close"), _f(r, "pre_close"),
                    _f(r, "change"), _f(r, "pct_chg"), vol_wan, amt_wan,
                    "monthly"
                ))
        self.db.commit()
        logger.info(f"[monthly] {trade_date}: upsert {len(df)} 行")


def _f(r, k):
    """安全取 float 值"""
    v = r.get(k)
    if v is None:
        return None
    try:
        return float(v)
    except (ValueError, TypeError):
        return None
