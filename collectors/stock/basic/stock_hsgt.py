"""
沪深港通股票列表采集器
接口：stock_hsgt（tushare pro）
"""

from collectors.base import BaseCollector


class StockHsgtCollector(BaseCollector):
    API_NAME = "stock_hsgt"
    table_name = "stock_hsgt"
    pk_columns = ["ts_code", "trade_date", "type"]



