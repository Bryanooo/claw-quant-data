"""
stk_limit 采集器：每日涨跌停价格
Tushare 接口: stk_limit
更新频率: 每个交易日 9:00（数据 8:40 已更新）
"""

import logging
import os
from datetime import date

import psycopg2
import tushare as ts

from collectors.base import BaseCollector, get_db_conn

logger = logging.getLogger("collector.stk_limit")


class STKLimitCollector(BaseCollector):
    """每日涨跌停价格采集（全市场单次取当日）"""

    INTERFACE_NAME = "stk_limit"
    TABLE_NAME = "stk_limit"
    PK_COLUMNS = ["trade_date", "ts_code"]

    def __init__(self):
        super().__init__()
        self.db = get_db_conn()

    def fetch(self):
        """采集当日涨停/跌停价"""
        today_str = date.today().strftime("%Y%m%d")
        logger.info(f"[stk_limit] 开始采集 {today_str}")

        df = self.pro.stk_limit(trade_date=today_str)
        if df is None or len(df) == 0:
            logger.warning(f"[stk_limit] {today_str} 无数据")
            return df

        logger.info(f"[stk_limit] 获取到 {len(df)} 条")
        return df

    def save(self, df):
        """upsert 写入"""
        if df is None or len(df) == 0:
            logger.info("[stk_limit] 无数据，跳过入库")
            return

        with self.db.cursor() as cur:
            for _, row in df.iterrows():
                cur.execute("""
                    INSERT INTO stk_limit (trade_date, ts_code, up_limit, down_limit)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (trade_date, ts_code)
                    DO UPDATE SET
                        up_limit = EXCLUDED.up_limit,
                        down_limit = EXCLUDED.down_limit
                """, (row['trade_date'], row['ts_code'],
                      float(row['up_limit']), float(row['down_limit'])))
        self.db.commit()
        logger.info(f"[stk_limit] 完成 upsert {len(df)} 条，已提交")


if __name__ == "__main__":
    collector = STKLimitCollector()
    data = collector.fetch()
    collector.save(data)
