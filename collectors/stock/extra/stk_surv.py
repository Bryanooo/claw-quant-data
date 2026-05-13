"""
机构调研表采集器（stk_surv）
采集策略：按 surv_date 逐天拉（单次100条需分页）
"""

import time
import logging
from datetime import datetime, timedelta
from collectors.base import get_db_conn

logger = logging.getLogger("collector.stk_surv")

_FIELDS = ["ts_code", "name", "surv_date", "fund_visitors", "rece_place",
           "rece_mode", "rece_org", "org_type", "comp_rece", "content"]
_PK = ["ts_code", "surv_date", "fund_visitors", "rece_org"]


class StkSurvCollector:
    INTERFACE_NAME = "stk_surv"
    TABLE_NAME = "stk_surv"
    CORE_FIELDS = _FIELDS

    def __init__(self):
        import tushare as ts
        from collectors.base import get_config
        token = get_config("tushare.token")
        if token:
            ts.set_token(token)
        self.pro = ts.pro_api()
        self.logger = logger

    def fetch(self, **params):
        return self.pro.stk_surv(**params)

    def collect_all_history(self, start_date="20200101", end_date="20260513"):
        total = 0
        s = datetime.strptime(start_date, "%Y%m%d")
        e = datetime.strptime(end_date, "%Y%m%d")
        d = s
        while d <= e:
            ds = d.strftime("%Y%m%d")
            offset = 0
            while True:
                df = self.fetch(surv_date=ds, limit=100, offset=offset, fields=",".join(_FIELDS))
                if df is None or len(df) == 0:
                    break
                self._store(df)
                total += len(df)
                offset += 100
                time.sleep(0.4)
            d += timedelta(days=1)
            time.sleep(0.3)
        logger.info(f"✅ stk_surv: 历史补齐 {total} 行")
        return total

    def _store(self, df):
        conn = get_db_conn()
        try:
            cols = ",".join(_FIELDS)
            phs = ",".join(["%s"] * len(_FIELDS))
            updates = ",".join([f"{c}=EXCLUDED.{c}" for c in _FIELDS if c not in _PK])
            vals = []
            for _, r in df.iterrows():
                vals.append(tuple(
                    None if (v is None or (isinstance(v, float) and v != v)) else v
                    for v in [r.get(c) for c in _FIELDS]
                ))
            with conn.cursor() as cur:
                import psycopg2.extras
                insert_sql = f"INSERT INTO {self.TABLE_NAME} ({cols}) VALUES ({phs}) ON CONFLICT ({', '.join(_PK)}) DO UPDATE SET {updates}"
                psycopg2.extras.execute_batch(cur, insert_sql, vals)
            conn.commit()
        finally:
            conn.close()

    def store(self, df):
        self._store(df)
        return len(df)
