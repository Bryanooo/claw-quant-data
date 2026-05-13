"""
大宗交易采集器（block_trade）
"""

import logging
from collectors.base import BaseCollector
from collectors.base import get_db_conn

logger = logging.getLogger("collector.block_trade")

_FIELDS = ["ts_code","trade_date","price","vol","amount","buyer","seller"]

class BlockTradeCollector(BaseCollector):
    INTERFACE_NAME = "block_trade"
    TABLE_NAME = "block_trade"
    CORE_FIELDS = _FIELDS

    def fetch(self, **params):
        return self.pro.block_trade(**params)

    def collect_all_history(self, start_date="20200101", end_date="20250513"):
        from datetime import datetime, timedelta
        total = 0
        s = datetime.strptime(start_date, "%Y%m%d")
        e = datetime.strptime(end_date, "%Y%m%d")
        d = s
        import time
        while d <= e:
            ds = d.strftime("%Y%m%d")
            df = self.fetch(trade_date=ds, fields=",".join(self.CORE_FIELDS))
            if df is not None and len(df) > 0:
                self.store(df)
                total += len(df)
            d += timedelta(days=1)
            time.sleep(0.5)
        logger.info(f"✅ block_trade: 历史补齐 {total} 行")
        return total

    def store(self, df):
        conn = get_db_conn()
        try:
            cols = ",".join(self.CORE_FIELDS)
            phs = ",".join(["%s"] * len(self.CORE_FIELDS))
            updates = ",".join([f"{c}=EXCLUDED.{c}" for c in self.CORE_FIELDS if c not in ("ts_code","trade_date","price","buyer","seller")])
            vals = [
                tuple(None if (v is None or (isinstance(v, float) and v != v)) else v for v in [r.get(c) for c in self.CORE_FIELDS])
                for _, r in df.iterrows()
            ]
            with conn.cursor() as cur:
                for row in vals:
                    cur.execute(
                        f"INSERT INTO {self.TABLE_NAME} ({cols}) VALUES ({phs}) "
                        f"ON CONFLICT (ts_code, trade_date, price, buyer, seller) DO UPDATE SET {updates}", row
                    )
            conn.commit()
        finally:
            conn.close()
