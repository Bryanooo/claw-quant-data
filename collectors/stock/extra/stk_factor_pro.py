"""
股票技术面因子（专业版）采集器（stk_factor_pro）
采集策略：按交易日逐天拉（只补2026年）
"""

import time
import logging
from datetime import datetime, timedelta
from collectors.base import get_db_conn

logger = logging.getLogger("collector.stk_factor_pro")

_FIELDS = [
    "ts_code", "trade_date", "open", "open_hfq", "open_qfq",
    "high", "high_hfq", "high_qfq", "low", "low_hfq", "low_qfq",
    "close", "close_hfq", "close_qfq", "pre_close", "change", "pct_chg",
    "vol", "amount", "turnover_rate", "turnover_rate_f", "volume_ratio",
    "pe", "pe_ttm", "pb", "ps", "ps_ttm", "dv_ratio", "dv_ttm",
    "total_share", "float_share", "free_share", "total_mv", "circ_mv",
    "adj_factor",
]
_PK = ["ts_code", "trade_date"]


class StkFactorProCollector:
    INTERFACE_NAME = "stk_factor_pro"
    TABLE_NAME = "stk_factor_pro"
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
        return self.pro.stk_factor_pro(**params)

    def collect_all_history(self, start_date="20260101", end_date="20260513"):
        total = 0
        s = datetime.strptime(start_date, "%Y%m%d")
        e = datetime.strptime(end_date, "%Y%m%d")
        d = s
        while d <= e:
            ds = d.strftime("%Y%m%d")
            df = self.fetch(trade_date=ds, fields=",".join(_FIELDS))
            if df is not None and len(df) > 0:
                self._store(df)
                total += len(df)
            d += timedelta(days=1)
            time.sleep(0.5)
        logger.info(f"✅ stk_factor_pro: 历史补齐 {total} 行")
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
