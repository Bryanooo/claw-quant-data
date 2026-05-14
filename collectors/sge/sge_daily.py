"""
黄金现货日行情采集器（sge_daily）
采集策略：按合约逐个拉，合约间按月分批
"""

from collectors.base import BaseCollector


class SgeDailyCollector(BaseCollector):
    API_NAME = "sge_daily"
    table_name = "sge_daily"
    pk_columns = ["ts_code", "trade_date"]

    def collect_all_history(self, start_date="20190101", end_date="20250513"):
        """逐个合约拉历史日线"""
        import time
        from service.db import query
        codes = query("SELECT ts_code FROM sge_basic")
        total = 0
        for r in codes:
            try:
                rows = self.collect(start_date=start_date, end_date=end_date, ts_code=r["ts_code"])
                total += rows
                self.logger.info(f"  {r['ts_code']}: {rows} 行")
                time.sleep(0.5)
            except Exception as e:
                self.logger.warning(f"  {r['ts_code']}: {e}")
        self.logger.info(f"✅ sge_daily: 历史补齐 {total} 行（{len(codes)} 个合约）")
        return total

    def refresh_latest(self, days=10):
        """增量更新最近 N 天"""
        import time
        from datetime import datetime, timedelta
        from service.db import query
        codes = query("SELECT ts_code FROM sge_basic")
        end = datetime.now().strftime("%Y%m%d")
        start = (datetime.now() - timedelta(days=days)).strftime("%Y%m%d")
        total = 0
        for r in codes:
            try:
                rows = self.collect(start_date=start, end_date=end, ts_code=r["ts_code"])
                total += rows
                time.sleep(0.3)
            except Exception as e:
                self.logger.warning(f"  {r['ts_code']}: {e}")
        self.logger.info(f"✅ sge_daily: 增量 {days}d → {total} 行")
        return total
