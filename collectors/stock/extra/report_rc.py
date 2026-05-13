"""
卖方盈利预测数据采集器（report_rc）
采集策略：按 report_date 逐天拉（有分页，limit=3000 offset 循环）
"""

import time
import logging
from datetime import datetime, timedelta
from collectors.base import get_db_conn, safe_float

logger = logging.getLogger("collector.report_rc")

_FIELDS = [
    "ts_code", "name", "report_date", "report_title", "report_type",
    "classify", "org_name", "author_name", "quarter", "op_rt", "op_pr",
    "tp", "np", "eps", "pe", "rd", "roe", "ev_ebitda", "rating",
    "max_price", "min_price", "imp_dg", "create_time",
]
_PK = ["ts_code", "report_date", "quarter"]


class ReportRcCollector:
    INTERFACE_NAME = "report_rc"
    TABLE_NAME = "report_rc"
    CORE_FIELDS = _FIELDS

    def __init__(self):
        from collectors.base import BaseCollector
        self._inner = BaseCollector.__new__(BaseCollector)
        self._inner.logger = logger
        self._inner.pro = None
        token_cfg = __import__("collectors.base", fromlist=["get_config"]).get_config
        import tushare as ts
        token = token_cfg("tushare.token")
        if token:
            ts.set_token(token)
        self.pro = ts.pro_api()
        self.logger = logger

    def fetch(self, **params):
        return self.pro.report_rc(**params)

    def collect_all_history(self, start_date="20100101", end_date="20260513"):
        total = 0
        s = datetime.strptime(start_date, "%Y%m%d")
        e = datetime.strptime(end_date, "%Y%m%d")
        d = s
        while d <= e:
            ds = d.strftime("%Y%m%d")
            logger.info(f"📡 report_rc: 采集 {ds}")
            offset = 0
            while True:
                df = self.fetch(report_date=ds, limit=3000, offset=offset, fields=",".join(_FIELDS))
                if df is None or len(df) == 0:
                    break
                self._store(df)
                total += len(df)
                offset += 3000
                time.sleep(0.4)
            d += timedelta(days=1)
            time.sleep(0.3)
        logger.info(f"✅ report_rc: 历史补齐 {total} 行")
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
