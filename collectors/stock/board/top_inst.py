"""
龙虎榜机构明细采集器
接口：top_inst（tushare pro）
"""

from collectors.base import BaseCollector


class TopInstCollector(BaseCollector):
    API_NAME = "top_inst"
    table_name = "top_inst"
    pk_columns = ["ts_code", "trade_date", "exalter", "side"]
