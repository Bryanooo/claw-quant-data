"""
外汇日线行情采集器（fx_daily）
"""

import logging
import time
from collectors.base import BaseCollector

logger = logging.getLogger("collector.fx_daily")

_FIELDS = [
    "ts_code","trade_date","bid_open","bid_close","bid_high","bid_low",
    "ask_open","ask_close","ask_high","ask_low","tick_qty","exchange",
]

class FxDailyCollector(BaseCollector):
    INTERFACE_NAME = "fx_daily"
    TABLE_NAME = "fx_daily"
    CORE_FIELDS = _FIELDS

    def fetch(self, **params):
        return self.pro.fx_daily(**params)

    def collect_all_history(self, start_date="20200101", end_date="20250513"):
        """逐个品种拉历史日线"""
        from service.db import query
        codes = query("SELECT ts_code FROM fx_obasic")
        total = 0
        for r in codes:
            ts_code = r["ts_code"]
            df = self.fetch(ts_code=ts_code, start_date=start_date, end_date=end_date,
                            fields=",".join(self.CORE_FIELDS))
            if df is not None and len(df) > 0:
                self.store(df)
                total += len(df)
            time.sleep(1.2)
        logger.info(f"✅ fx_daily: 历史补齐 {total} 行（{len(codes)} 个品种）")
        return total

    def refresh_latest(self, days=30):
        """增量更新最近N天数据"""
        from datetime import datetime, timedelta
        from service.db import query

        codes = query("SELECT ts_code FROM fx_obasic")
        end = datetime.now().strftime("%Y%m%d")
        start = (datetime.now() - timedelta(days=days)).strftime("%Y%m%d")
        total = 0
        for r in codes:
            ts_code = r["ts_code"]
            df = self.fetch(ts_code=ts_code, start_date=start, end_date=end,
                            fields=",".join(self.CORE_FIELDS))
            if df is not None and len(df) > 0:
                self.store(df)
                total += len(df)
            time.sleep(0.5)
        logger.info(f"✅ fx_daily: 增量更新 {days}d → {total} 行")
        return total

    def store(self, df):
        from collectors.base import get_db_conn
        conn = get_db_conn()
        try:
            cols = ",".join(self.CORE_FIELDS)
            phs = ",".join(["%s"] * len(self.CORE_FIELDS))
            updates = ",".join([f"{c}=EXCLUDED.{c}" for c in self.CORE_FIELDS if c not in ("ts_code","trade_date")])
            vals = [
                tuple(None if (v is None or (isinstance(v, float) and v != v)) else v for v in [r.get(c) for c in self.CORE_FIELDS])
                for _, r in df.iterrows()
            ]
            with conn.cursor() as cur:
                for row in vals:
                    cur.execute(
                        f"INSERT INTO {self.TABLE_NAME} ({cols}) VALUES ({phs}) "
                        f"ON CONFLICT (ts_code, trade_date) DO UPDATE SET {updates}",
                        row
                    )
            conn.commit()
            logger.info(f"  ✅ fx_daily: upsert {len(df)} 行")
        finally:
            conn.close()
