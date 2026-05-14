"""
东方财富概念板块采集器
接口：dc_index（tushare pro）
"""

from collectors.base import BaseCollector


class DcIndexCollector(BaseCollector):
    API_NAME = "dc_index"
    table_name = "dc_index"
    pk_columns = ["ts_code", "trade_date"]
