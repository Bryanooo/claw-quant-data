"""
黄金现货日行情采集器（sge_daily）
"""

import logging
import time
from datetime import datetime, timedelta
from collectors.base import BaseCollector

logger = logging.getLogger("collector.sge_daily")

_FIELDS = [
    "ts_code","trade_date","close","open","high","low","price_avg",
    "change","pct_change","vol","amount","oi","settle_vol","settle_dire",
]

class SgeDailyCollector(BaseCollector):
    INTERFACE_NAME = "sge_daily"
    TABLE_NAME = "sge_daily"
    CORE_FIELDS = _FIELDS

    def fetch(self, **params):
        return self.pro.sge_daily(**params)

    def collect_all_history(self, start_date="20190101", end_date="20250513"):
        """逐个合约拉历史日线"""
        from service.db import query

        codes = query("SELECT ts_code FROM sge_basic")
        total = 0
        step = 500  # 单次2000行限制，用500天步长
        for r in codes:
            ts_code = r["ts_code"]
            s = start_date
            while s < end_date:
                e = self._add_days(s, step)
                if e > end_date:
                    e = end_date
                df = self.fetch(ts_code=ts_code, start_date=s, end_date=e,
                                fields=",".join(self.CORE_FIELDS))
                if df is not None and len(df) > 0:
                    self.store(df)
                    total += len(df)
                s = e
                time.sleep(0.8)
        logger.info(f"✅ sge_daily: 历史补齐 {total} 行（{len(codes)} 个合约）")
        return total

    def refresh_latest(self, days=10):
        """增量更新"""
        from service.db import query
        codes = query("SELECT ts_code FROM sge_basic")
        end = datetime.now().strftime("%Y%m%d")
        start = (datetime.now() - timedelta(days=days)).strftime("%Y%m%d")
        total = 0
        for r in codes:
            df = self.fetch(ts_code=r["ts_code"], start_date=start, end_date=end,
                            fields=",".join(self.CORE_FIELDS))
            if df is not None and len(df) > 0:
                self.store(df)
                total += len(df)
            time.sleep(0.5)
        logger.info(f"✅ sge_daily: 增量 {days}d → {total} 行")
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
                        f"ON CONFLICT (ts_code, trade_date) DO UPDATE SET {updates}", row
                    )
            conn.commit()
            logger.info(f"  ✅ sge_daily: upsert {len(df)} 行")
        finally:
            conn.close()

    @staticmethod
    def _add_days(date_str, days):
        d = datetime.strptime(date_str, "%Y%m%d") + timedelta(days=days)
        return d.strftime("%Y%m%d")
