"""
东方财富热榜采集器
接口：dc_hot（tushare pro）
"""

from collectors.base import BaseCollector


class DcHotCollector(BaseCollector):
    API_NAME = "dc_hot"
    table_name = "dc_hot"
    pk_columns = ["trade_date", "ts_code", "rank", "data_type", "rank_time"]
