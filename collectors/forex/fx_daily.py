"""
外汇日线行情采集器（fx_daily）
采集策略：逐个品种拉，用基类按月循环补齐
"""

import time
from collectors.base import BaseCollector

_FIELDS = [
    "ts_code","trade_date","bid_open","bid_close","bid_high","bid_low",
    "ask_open","ask_close","ask_high","ask_low","tick_qty","exchange",
]

class FxDailyCollector(BaseCollector):
    INTERFACE_NAME = "fx_daily"
    TABLE_NAME = "fx_daily"
    CORE_FIELDS = _FIELDS
    pk_columns = ["ts_code", "trade_date"]

    def collect_all_history(self, start_date="20200101", end_date="20250513"):
        """逐个品种拉历史日线"""
        from service.db import query
        codes = query("SELECT ts_code FROM fx_obasic")
        total = 0
        for r in codes:
            rows = self.collect(start_date=start_date, end_date=end_date, ts_code=r["ts_code"])
            total += rows
            self.logger.info(f"  {r['ts_code']}: {rows} 行")
            time.sleep(1.0)
        self.logger.info(f"✅ fx_daily: 历史补齐 {total} 行（{len(codes)} 个品种）")
        return total

    def refresh_latest(self, days=30):
        """增量更新最近N天"""
        from datetime import datetime, timedelta
        from service.db import query
        codes = query("SELECT ts_code FROM fx_obasic")
        end = datetime.now().strftime("%Y%m%d")
        start = (datetime.now() - timedelta(days=days)).strftime("%Y%m%d")
        total = 0
        for r in codes:
            rows = self.collect(start_date=start, end_date=end, ts_code=r["ts_code"])
            total += rows
            time.sleep(0.5)
        self.logger.info(f"✅ fx_daily: 增量更新 {days}d → {total} 行")
        return total
