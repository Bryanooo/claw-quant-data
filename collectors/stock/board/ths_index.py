"""
同花顺概念和行业指数采集器
接口：ths_index（tushare pro）
"""

from collectors.base import BaseCollector


class ThsIndexCollector(BaseCollector):
    API_NAME = "ths_index"
    table_name = "ths_index"
    pk_columns = ["ts_code"]
