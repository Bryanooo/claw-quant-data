"""
同花顺概念板块成分采集器
接口：ths_member（tushare pro）
"""

from collectors.base import BaseCollector


class ThsMemberCollector(BaseCollector):
    API_NAME = "ths_member"
    table_name = "ths_member"
    pk_columns = ["ts_code", "con_code"]
