"""
股东人数采集器（stk_holdernumber）
"""

import logging
import time
from collectors.base import BaseCollector
from collectors.base import get_db_conn

logger = logging.getLogger("collector.stk_holdernumber")

_FIELDS = ["ts_code","ann_date","end_date","holder_num"]

class StkHoldernumberCollector(BaseCollector):
    INTERFACE_NAME = "stk_holdernumber"
    TABLE_NAME = "stk_holdernumber"
    CORE_FIELDS = _FIELDS

    def fetch(self, **params):
        return self.pro.stk_holdernumber(**params)

    def collect_all_history(self, start_date="20200101", end_date="20250513"):
        from service.db import query
        codes = query("SELECT ts_code FROM stock_basic ORDER BY ts_code")
        total = 0
        for r in codes:
            ts_code = r["ts_code"]
            df = self.fetch(ts_code=ts_code, start_date=start_date, end_date=end_date,
                            fields=",".join(self.CORE_FIELDS))
            if df is not None and len(df) > 0:
                self.store(df)
                total += len(df)
            time.sleep(1)
        logger.info(f"✅ stk_holdernumber: 历史补齐 {total} 行")
        return total

    def store(self, df):
        conn = get_db_conn()
        try:
            cols = ",".join(self.CORE_FIELDS)
            phs = ",".join(["%s"] * len(self.CORE_FIELDS))
            updates = ",".join([f"{c}=EXCLUDED.{c}" for c in self.CORE_FIELDS if c not in ("ts_code","end_date")])
            vals = [
                tuple(None if (v is None or (isinstance(v, float) and v != v)) else v for v in [r.get(c) for c in self.CORE_FIELDS])
                for _, r in df.iterrows()
            ]
            with conn.cursor() as cur:
                for row in vals:
                    cur.execute(
                        f"INSERT INTO {self.TABLE_NAME} ({cols}) VALUES ({phs}) "
                        f"ON CONFLICT (ts_code, end_date) DO UPDATE SET {updates}", row
                    )
            conn.commit()
        finally:
            conn.close()
