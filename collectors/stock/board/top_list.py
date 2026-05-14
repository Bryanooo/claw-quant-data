"""
龙虎榜每日明细采集器
接口：top_list（tushare pro）
"""

from collectors.base import BaseCollector


class TopListCollector(BaseCollector):
    API_NAME = "top_list"
    table_name = "top_list"
    pk_columns = ["ts_code", "trade_date"]
