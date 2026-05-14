"""
沪深股通十大成交股采集器
接口：hsgt_top10（tushare pro）
"""

from collectors.base import BaseCollector


class HsgtTop10Collector(BaseCollector):
    API_NAME = "hsgt_top10"
    table_name = "hsgt_top10"
    pk_columns = ["trade_date", "ts_code", "market_type"]
