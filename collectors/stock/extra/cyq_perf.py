"""
每日筹码及胜率采集器（cyq_perf）
采集策略：逐个股票逐段拉（ts_code 从 stock_basic 取）
"""

import time
import logging
from datetime import datetime, timedelta
from collectors.base import get_db_conn

logger = logging.getLogger("collector.cyq_perf")

_FIELDS = ["ts_code", "trade_date", "his_low", "his_high", "cost_5pct",
           "cost_15pct", "cost_50pct", "cost_85pct", "cost_95pct",
           "weight_avg", "winner_rate"]
_PK = ["ts_code", "trade_date"]


class CyqPerfCollector:
    INTERFACE_NAME = "cyq_perf"
    TABLE_NAME = "cyq_perf"
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
        return self.pro.cyq_perf(**params)

    def collect_all_history(self, start_date="20200101", end_date="20260513"):
        """逐个股票逐段拉"""
        all_codes = self._get_stock_codes()
        total = 0
        chunk_size = 500
        for i in range(0, len(all_codes), chunk_size):
            codes_chunk = all_codes[i:i + chunk_size]
            for ts_code in codes_chunk:
                df = self.fetch(ts_code=ts_code, start_date=start_date, end_date=end_date,
                                fields=",".join(_FIELDS))
                if df is not None and len(df) > 0:
                    self._store(df)
                    total += len(df)
                time.sleep(0.35)
            time.sleep(1)
        logger.info(f"✅ cyq_perf: 历史补齐 {total} 行")
        return total

    def _get_stock_codes(self):
        conn = get_db_conn()
        try:
            cur = conn.cursor()
            cur.execute("SELECT ts_code FROM stock_basic")
            return [r[0] for r in cur.fetchall()]
        finally:
            conn.close()

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
