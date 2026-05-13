"""
券商每月荐股采集器（broker_recommend）
采集策略：按月拉
"""

import time
import logging
from datetime import datetime, timedelta
from collectors.base import get_db_conn

logger = logging.getLogger("collector.broker_recommend")

_FIELDS = ["month", "broker", "ts_code", "name"]
_PK = ["month", "broker", "ts_code"]


class BrokerRecommendCollector:
    INTERFACE_NAME = "broker_recommend"
    TABLE_NAME = "broker_recommend"
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
        return self.pro.broker_recommend(**params)

    def collect_all_history(self, start_date="20200101", end_date="20260513"):
        total = 0
        s = datetime.strptime(start_date, "%Y%m%d")
        e = datetime.strptime(end_date, "%Y%m%d")
        # Round to month boundaries
        current = s.replace(day=1)
        end_month = e.replace(day=1)
        while current <= end_month:
            month_str = current.strftime("%Y%m")
            df = self.fetch(month=month_str, fields=",".join(_FIELDS))
            if df is not None and len(df) > 0:
                self._store(df)
                total += len(df)
            # Advance to next month
            if current.month == 12:
                current = current.replace(year=current.year + 1, month=1)
            else:
                current = current.replace(month=current.month + 1)
            time.sleep(0.35)
        logger.info(f"✅ broker_recommend: 历史补齐 {total} 行")
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
