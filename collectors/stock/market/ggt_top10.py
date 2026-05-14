"""
港股通十大成交股采集器
接口：ggt_top10（tushare pro）
"""

from collectors.base import BaseCollector


class GgtTop10Collector(BaseCollector):
    API_NAME = "ggt_top10"
    table_name = "ggt_top10"
    pk_columns = ["trade_date", "ts_code", "market_type"]
