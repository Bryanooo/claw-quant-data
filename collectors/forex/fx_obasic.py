"""
外汇基础信息采集器（fx_obasic）
"""

import logging
from collectors.base import BaseCollector

logger = logging.getLogger("collector.fx_obasic")

_FIELDS = [
    "ts_code","name","classify","exchange","min_unit","max_unit",
    "pip","pip_cost","target_spread","min_stop_distance","trading_hours","break_time",
]

class FxObasicCollector(BaseCollector):
    INTERFACE_NAME = "fx_obasic"
    TABLE_NAME = "fx_obasic"
    CORE_FIELDS = _FIELDS

    def fetch(self, **params):
        return self.pro.fx_obasic(**params)

    def collect_full(self):
        """全量采集：获取所有分类的外汇基础信息"""
        total = 0
        for classify in ["FX","INDEX","COMMODITY","METAL","BUND","CRYPTO","FX_BASKET"]:
            df = self.fetch(exchange="FXCM", classify=classify, fields=",".join(self.CORE_FIELDS))
            if df is not None and len(df) > 0:
                self.store(df)
                total += len(df)
        logger.info(f"✅ fx_obasic: 全量采集 {total} 行")
        return total

    def store(self, df):
        """upsert"""
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
                        f"ON CONFLICT (ts_code) DO UPDATE SET {updates}",
                        row
                    )
            conn.commit()
            logger.info(f"  ✅ fx_obasic: upsert {len(df)} 行")
        finally:
            conn.close()
