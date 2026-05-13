"""
限售股解禁采集器（share_float）
"""

import logging
from collectors.base import BaseCollector
from collectors.base import get_db_conn

logger = logging.getLogger("collector.share_float")

_FIELDS = ["ts_code","ann_date","float_date","float_share","float_ratio","holder_name","share_type"]

class ShareFloatCollector(BaseCollector):
    INTERFACE_NAME = "share_float"
    TABLE_NAME = "share_float"
    CORE_FIELDS = _FIELDS

    def fetch(self, **params):
        return self.pro.share_float(**params)

    def collect_all_history(self, start_date="20200101", end_date="20251231"):
        """按逐天拉取历史解禁数据"""
        from datetime import datetime, timedelta
        from service.db import query

        total = 0
        s = datetime.strptime(start_date, "%Y%m%d")
        e = datetime.strptime(end_date, "%Y%m%d")
        d = s
        import time
        while d <= e:
            ds = d.strftime("%Y%m%d")
            df = self.fetch(ann_date=ds, fields=",".join(self.CORE_FIELDS))
            if df is not None and len(df) > 0:
                self.store(df)
                total += len(df)
            d += timedelta(days=1)
            time.sleep(0.5)
        logger.info(f"✅ share_float: 历史补齐 {total} 行")
        return total

    def store(self, df):
        conn = get_db_conn()
        try:
            cols = ",".join(self.CORE_FIELDS)
            phs = ",".join(["%s"] * len(self.CORE_FIELDS))
            updates = ",".join([f"{c}=EXCLUDED.{c}" for c in self.CORE_FIELDS if c not in ("ts_code","float_date","holder_name","share_type")])
            vals = [
                tuple(None if (v is None or (isinstance(v, float) and v != v)) else v for v in [r.get(c) for c in self.CORE_FIELDS])
                for _, r in df.iterrows()
            ]
            with conn.cursor() as cur:
                for row in vals:
                    cur.execute(
                        f"INSERT INTO {self.TABLE_NAME} ({cols}) VALUES ({phs}) "
                        f"ON CONFLICT (ts_code, float_date, holder_name, share_type) DO UPDATE SET {updates}", row
                    )
            conn.commit()
        finally:
            conn.close()
