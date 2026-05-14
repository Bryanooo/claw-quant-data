"""
东财概念板块行情采集器
接口：dc_daily（tushare pro）
"""

from collectors.base import BaseCollector


class DcDailyCollector(BaseCollector):
    API_NAME = "dc_daily"
    table_name = "dc_daily"
    pk_columns = ["ts_code", "trade_date"]
