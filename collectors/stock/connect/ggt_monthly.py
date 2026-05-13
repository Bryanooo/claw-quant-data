"""
ggt_monthly 采集器：港股通每月成交统计
Tushare 接口: ggt_monthly
"""

import logging
import time
from datetime import date, datetime

import pandas as pd

from collectors.base import BaseCollector, get_db_conn

logger = logging.getLogger("collector.ggt_monthly")


class GgtMonthlyCollector(BaseCollector):
    INTERFACE_NAME = "ggt_monthly"
    TABLE_NAME = "ggt_monthly"
    PK_COLUMNS = ["month"]

    def __init__(self):
        super().__init__()
        self.db = get_db_conn()

    def fetch(self, start_month: str, end_month: str):
        """取月度范围数据（按月逐个取）"""
        all_dfs = []
        sy, sm = int(start_month[:4]), int(start_month[4:])
        ey, em = int(end_month[:4]), int(end_month[4:])
        y, m = sy, sm
        while (y < ey) or (y == ey and m <= em):
            m_str = f"{y}{m:02d}"
            df = self.pro.ggt_monthly(trade_date=m_str)
            if df is not None and len(df) > 0:
                all_dfs.append(df)
            m += 1
            if m > 12:
                m = 1
                y += 1
            time.sleep(3)

        if all_dfs:
            result = pd.concat(all_dfs).drop_duplicates(subset=["month"])
            logger.info(f"[ggt_monthly] {start_month}~{end_month}: {len(result)} 条")
            return result
        return None

    def save(self, df):
        if df is None or len(df) == 0:
            return
        with self.db.cursor() as cur:
            for _, r in df.iterrows():
                cur.execute("""
                    INSERT INTO ggt_monthly (month, day_buy_amt, day_buy_vol, day_sell_amt, day_sell_vol,
                        total_buy_amt, total_buy_vol, total_sell_amt, total_sell_vol)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT (month) DO UPDATE SET
                        day_buy_amt=EXCLUDED.day_buy_amt, day_buy_vol=EXCLUDED.day_buy_vol,
                        day_sell_amt=EXCLUDED.day_sell_amt, day_sell_vol=EXCLUDED.day_sell_vol,
                        total_buy_amt=EXCLUDED.total_buy_amt, total_buy_vol=EXCLUDED.total_buy_vol,
                        total_sell_amt=EXCLUDED.total_sell_amt, total_sell_vol=EXCLUDED.total_sell_vol
                """, (r["month"], _f(r, "day_buy_amt"), _f(r, "day_buy_vol"),
                      _f(r, "day_sell_amt"), _f(r, "day_sell_vol"),
                      _f(r, "total_buy_amt"), _f(r, "total_buy_vol"),
                      _f(r, "total_sell_amt"), _f(r, "total_sell_vol")))
        self.db.commit()
        logger.info(f"[ggt_monthly] 完成 upsert {len(df)} 条")


def _f(r, k): return float(r[k]) if k in r and r[k] is not None else None
