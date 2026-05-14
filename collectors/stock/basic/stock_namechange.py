"""
股票曾用名采集器
接口：namechange（tushare pro）
"""

from collectors.base import BaseCollector


class NameChangeCollector(BaseCollector):
    API_NAME = "namechange"
    table_name = "namechange"
    pk_columns = ["ts_code", "start_date"]



