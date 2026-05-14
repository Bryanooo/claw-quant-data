"""
券商每月荐股采集器（broker_recommend）
采集策略：按月拉（month参数，不支持start_date/end_date范围查询）
"""

import time
import logging
from datetime import datetime, timedelta
from collectors.base import BaseCollector, get_db_conn

logger = logging.getLogger("collector.broker_recommend")


class BrokerRecommendCollector(BaseCollector):
    API_NAME = "broker_recommend"
    table_name = "broker_recommend"
    pk_columns = ["month", "broker", "ts_code"]
    supports_range_query = False  # 使用 month 参数而非日期范围

    def collect_all_history(self, start_date="20200101", end_date="20260513"):
        """按月循环补齐历史数据（使用 month 参数）"""
        total = 0
        s = datetime.strptime(start_date, "%Y%m%d")
        e = datetime.strptime(end_date, "%Y%m%d")
        current = s.replace(day=1)
        end_month = e.replace(day=1)
        while current <= end_month:
            month_str = current.strftime("%Y%m")
            try:
                rows = self.collect(skip_store=False, month=month_str)
                total += rows
            except Exception as ex:
                self.logger.warning(f"  {month_str}: {ex}")
            if current.month == 12:
                current = current.replace(year=current.year + 1, month=1)
            else:
                current = current.replace(month=current.month + 1)
            time.sleep(0.3)
        self.logger.info(f"🏁 broker_recommend: 历史补齐 {total} 行")
        return total
