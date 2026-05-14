"""
通达信板块信息采集器
接口：tdx_index（tushare pro）
"""

from collectors.base import BaseCollector


class TdxIndexCollector(BaseCollector):
    API_NAME = "tdx_index"
    table_name = "tdx_index"
    pk_columns = ["ts_code", "trade_date"]
