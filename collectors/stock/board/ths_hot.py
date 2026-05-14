"""
同花顺热榜采集器
接口：ths_hot（tushare pro）
"""

from collectors.base import BaseCollector


class ThsHotCollector(BaseCollector):
    API_NAME = "ths_hot"
    table_name = "ths_hot"
    pk_columns = ["trade_date", "ts_code", "rank", "data_type", "rank_time"]
