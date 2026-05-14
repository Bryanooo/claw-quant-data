"""
每日停复牌信息采集器
接口：suspend_d（tushare pro）
"""

from collectors.base import BaseCollector


class SuspendDCollector(BaseCollector):
    API_NAME = "suspend_d"
    table_name = "suspend_d"
    pk_columns = ["ts_code", "trade_date", "suspend_type"]
