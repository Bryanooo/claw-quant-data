"""
港股通每日成交统计采集器
接口：ggt_daily（tushare pro）
"""

from collectors.base import BaseCollector


class GgtDailyCollector(BaseCollector):
    API_NAME = "ggt_daily"
    table_name = "ggt_daily"
    pk_columns = ["trade_date"]
