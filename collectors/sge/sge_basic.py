"""
黄金现货基础信息采集器（sge_basic）
"""

import logging
from collectors.base import BaseCollector

logger = logging.getLogger("collector.sge_basic")

_FIELDS = [
    "ts_code","ts_name","trade_type","t_unit","p_unit","min_change",
    "price_limit","min_vol","max_vol","trade_mode","margin_rate",
    "liq_rate","trade_time","list_date",
]

class SgeBasicCollector(BaseCollector):
    INTERFACE_NAME = "sge_basic"
    TABLE_NAME = "sge_basic"
    CORE_FIELDS = _FIELDS

    def fetch(self, **params):
        return self.pro.sge_basic(**params)

    def collect_full(self):
        """全量采集所有现货合约"""
        df = self.fetch()
        if df is not None and len(df) > 0:
            self.store(df)
        logger.info(f"✅ sge_basic: 全量采集 {len(df) if df is not None else 0} 行")
        return len(df) if df is not None else 0

    def store(self, df):
        from collectors.base import get_db_conn
        conn = get_db_conn()
        try:
            cols = ",".join(self.CORE_FIELDS)
            phs = ",".join(["%s"] * len(self.CORE_FIELDS))
            updates = ",".join([f"{c}=EXCLUDED.{c}" for c in self.CORE_FIELDS if c != "ts_code"])
            vals = [
                tuple(None if v is None or (isinstance(v, float) and v != v) else v for v in [r.get(c) for c in self.CORE_FIELDS])
                for _, r in df.iterrows()
            ]
            with conn.cursor() as cur:
                for row in vals:
                    cur.execute(
                        f"INSERT INTO {self.TABLE_NAME} ({cols}) VALUES ({phs}) "
                        f"ON CONFLICT (ts_code) DO UPDATE SET {updates}", row
                    )
            conn.commit()
            logger.info(f"  ✅ sge_basic: upsert {len(df)} 行")
        finally:
            conn.close()
