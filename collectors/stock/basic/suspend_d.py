"""
suspend_d 采集器：每日停复牌信息
Tushare 接口: suspend_d
更新频率: 每个交易日 09:10 跑
"""

import logging
from datetime import date, datetime, timedelta

from collectors.base import BaseCollector, get_db_conn

logger = logging.getLogger("collector.suspend_d")


class SuspendDCollector(BaseCollector):
    """每日停复牌信息采集（增量：取指定日期范围）"""

    INTERFACE_NAME = "suspend_d"
    TABLE_NAME = "suspend_d"
    PK_COLUMNS = ["ts_code", "trade_date", "suspend_type"]

    def __init__(self):
        super().__init__()
        self.db = get_db_conn()

    def fetch(self, start_date: str, end_date: str):
        """按日期范围获取停复牌信息"""
        logger.info(f"[suspend_d] 采集 {start_date} ~ {end_date}")

        # 一次取全量（单次不限制）
        df = self.pro.suspend_d(start_date=start_date, end_date=end_date)
        if df is None or len(df) == 0:
            logger.info(f"[suspend_d] {start_date}~{end_date} 无数据")
            return df

        logger.info(f"[suspend_d] 获取到 {len(df)} 条")
        return df

    def save(self, df):
        """upsert 写入"""
        if df is None or len(df) == 0:
            logger.info("[suspend_d] 无数据，跳过入库")
            return

        cnt = 0
        with self.db.cursor() as cur:
            for _, row in df.iterrows():
                cur.execute("""
                    INSERT INTO suspend_d (ts_code, trade_date, suspend_timing, suspend_type)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (ts_code, trade_date, suspend_type)
                    DO UPDATE SET
                        suspend_timing = EXCLUDED.suspend_timing
                """, (
                    row['ts_code'],
                    row['trade_date'],
                    row.get('suspend_timing') or None,
                    row['suspend_type'],
                ))
                cnt += 1
        self.db.commit()
        logger.info(f"[suspend_d] 完成 upsert {cnt} 条，已提交")


def backfill_2026():
    """补 2026 年历史数据"""
    c = SuspendDCollector()
    start = "20260101"
    end = date.today().strftime("%Y%m%d")
    logger.info(f"[suspend_d] 开始补历史: {start} ~ {end}")

    # 月份逐步取（防止单次超量，也方便断点续跑）
    d = datetime.strptime(start, "%Y%m%d")
    today = datetime.strptime(end, "%Y%m%d")
    total = 0
    while d < today:
        month_end = d.replace(day=28) + timedelta(days=4)
        month_end = month_end.replace(day=1) - timedelta(days=1)
        if month_end > today:
            month_end = today
        s = d.strftime("%Y%m%d")
        e = month_end.strftime("%Y%m%d")
        df = c.fetch(s, e)
        if df is not None and len(df) > 0:
            c.save(df)
            total += len(df)
        d = month_end + timedelta(days=1)
    logger.info(f"[suspend_d] 补历史完成，合计 {total} 条")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "backfill":
        backfill_2026()
    else:
        # 默认：取当日数据
        today_str = date.today().strftime("%Y%m%d")
        c = SuspendDCollector()
        df = c.fetch(today_str, today_str)
        c.save(df)
