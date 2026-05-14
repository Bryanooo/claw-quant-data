"""
通达信板块行情采集器
接口：tdx_daily（tushare pro）
"""

from collectors.base import BaseCollector


class TdxDailyCollector(BaseCollector):
    API_NAME = "tdx_daily"
    table_name = "tdx_daily"
    pk_columns = ["ts_code", "trade_date"]
