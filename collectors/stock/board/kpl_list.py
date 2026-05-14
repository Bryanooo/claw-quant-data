"""
开盘啦榜单数据采集器
接口：kpl_list（tushare pro）
"""

from collectors.base import BaseCollector


class KplListCollector(BaseCollector):
    API_NAME = "kpl_list"
    table_name = "kpl_list"
    pk_columns = ["ts_code", "trade_date", "tag"]
