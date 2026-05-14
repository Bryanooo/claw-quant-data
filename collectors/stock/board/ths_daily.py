"""
同花顺板块指数行情采集器
接口：ths_daily（tushare pro）
"""

from collectors.base import BaseCollector


class ThsDailyCollector(BaseCollector):
    API_NAME = "ths_daily"
    table_name = "ths_daily"
    pk_columns = ["ts_code", "trade_date"]
