"""
hsgt_top10 采集器：沪深股通十大成交股
Tushare 接口: hsgt_top10
更新时间: 每个交易日 18:00~20:00
调度: 20:00
"""

import logging
from datetime import date

from collectors.base import BaseCollector, get_db_conn

logger = logging.getLogger("collector.hsgt_top10")


class HsgtTop10Collector(BaseCollector):
    INTERFACE_NAME = "hsgt_top10"
    TABLE_NAME = "hsgt_top10"
    PK_COLUMNS = ["trade_date", "ts_code", "market_type"]

    def __init__(self):
        super().__init__()
        self.db = get_db_conn()

    def fetch(self, trade_date: str):
        """取当日沪深股通十大成交股（沪+深）"""
        dfs = []
        for mkt, label in [("1", "沪市"), ("3", "深市")]:
            df = self.pro.hsgt_top10(trade_date=trade_date, market_type=mkt)
            if df is not None and len(df) > 0:
                dfs.append(df)
                logger.info(f"[hsgt_top10] {label} {trade_date}: {len(df)} 条")
        return pd.concat(dfs) if dfs else None

    def save(self, df):
        if df is None or len(df) == 0:
            return
        with self.db.cursor() as cur:
            for _, r in df.iterrows():
                cur.execute("""
                    INSERT INTO hsgt_top10 (trade_date, ts_code, name, close, "change", rank, market_type, amount, net_amount, buy, sell)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT (trade_date, ts_code, market_type)
                    DO UPDATE SET close=EXCLUDED.close, "change"=EXCLUDED."change", rank=EXCLUDED.rank,
                        amount=EXCLUDED.amount, net_amount=EXCLUDED.net_amount, buy=EXCLUDED.buy, sell=EXCLUDED.sell
                """, (r["trade_date"], r["ts_code"], r.get("name"), _f(r, "close"), _f(r, "change"),
                      _i(r, "rank"), int(r["market_type"]), _f(r, "amount"), _f(r, "net_amount"),
                      _f(r, "buy"), _f(r, "sell")))
        self.db.commit()
        logger.info(f"[hsgt_top10] 完成 upsert {len(df)} 条")


import pandas as pd
def _f(r, k): return float(r[k]) if k in r and r[k] is not None else None
def _i(r, k): return int(r[k]) if k in r and r[k] is not None else None
