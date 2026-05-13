"""
ggt_top10 采集器：港股通十大成交股
Tushare 接口: ggt_top10
"""

import logging
from datetime import date

import pandas as pd

from collectors.base import BaseCollector, get_db_conn

logger = logging.getLogger("collector.ggt_top10")


class GgtTop10Collector(BaseCollector):
    INTERFACE_NAME = "ggt_top10"
    TABLE_NAME = "ggt_top10"
    PK_COLUMNS = ["trade_date", "ts_code", "market_type"]

    def __init__(self):
        super().__init__()
        self.db = get_db_conn()

    def fetch(self, trade_date: str):
        df = self.pro.ggt_top10(trade_date=trade_date)
        if df is not None and len(df) > 0:
            logger.info(f"[ggt_top10] {trade_date}: {len(df)} 条")
        return df

    def save(self, df):
        if df is None or len(df) == 0:
            return
        with self.db.cursor() as cur:
            for _, r in df.iterrows():
                cur.execute("""
                    INSERT INTO ggt_top10 (trade_date, ts_code, name, close, p_change, rank, market_type,
                        amount, net_amount, sh_amount, sh_net_amount, sh_buy, sh_sell,
                        sz_amount, sz_net_amount, sz_buy, sz_sell)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT (trade_date, ts_code, market_type)
                    DO UPDATE SET close=EXCLUDED.close, p_change=EXCLUDED.p_change, rank=EXCLUDED.rank,
                        amount=EXCLUDED.amount, net_amount=EXCLUDED.net_amount
                """, (
                    r["trade_date"], r["ts_code"], r.get("name"),
                    _f(r, "close"), _f(r, "p_change"), _i(r, "rank"), int(r["market_type"]),
                    _f(r, "amount"), _f(r, "net_amount"),
                    _f(r, "sh_amount"), _f(r, "sh_net_amount"), _f(r, "sh_buy"), _f(r, "sh_sell"),
                    _f(r, "sz_amount"), _f(r, "sz_net_amount"), _f(r, "sz_buy"), _f(r, "sz_sell"),
                ))
        self.db.commit()
        logger.info(f"[ggt_top10] 完成 upsert {len(df)} 条")


def _f(r, k): return float(r[k]) if k in r and r[k] is not None else None
def _i(r, k): return int(r[k]) if k in r and r[k] is not None else None
