"""
ggt_daily 采集器：港股通每日成交统计
Tushare 接口: ggt_daily
"""

import logging
from datetime import date

from collectors.base import BaseCollector, get_db_conn

logger = logging.getLogger("collector.ggt_daily")


class GgtDailyCollector(BaseCollector):
    INTERFACE_NAME = "ggt_daily"
    TABLE_NAME = "ggt_daily"
    PK_COLUMNS = ["trade_date"]

    def __init__(self):
        super().__init__()
        self.db = get_db_conn()

    def fetch(self, start_date: str, end_date: str):
        df = self.pro.ggt_daily(start_date=start_date, end_date=end_date)
        if df is not None and len(df) > 0:
            logger.info(f"[ggt_daily] {start_date}~{end_date}: {len(df)} 条")
        return df

    def save(self, df):
        if df is None or len(df) == 0:
            return
        with self.db.cursor() as cur:
            for _, r in df.iterrows():
                cur.execute("""
                    INSERT INTO ggt_daily (trade_date, buy_amount, buy_volume, sell_amount, sell_volume)
                    VALUES (%s,%s,%s,%s,%s)
                    ON CONFLICT (trade_date) DO UPDATE SET
                        buy_amount=EXCLUDED.buy_amount, buy_volume=EXCLUDED.buy_volume,
                        sell_amount=EXCLUDED.sell_amount, sell_volume=EXCLUDED.sell_volume
                """, (r["trade_date"], _f(r, "buy_amount"), _f(r, "buy_volume"),
                      _f(r, "sell_amount"), _f(r, "sell_volume")))
        self.db.commit()
        logger.info(f"[ggt_daily] 完成 upsert {len(df)} 条")


def _f(r, k): return float(r[k]) if k in r and r[k] is not None else None
