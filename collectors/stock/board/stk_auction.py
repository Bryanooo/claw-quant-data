"""
当日集合竞价采集器
接口：stk_auction（tushare pro）
"""

from collectors.base import BaseCollector


class StkAuctionCollector(BaseCollector):
    API_NAME = "stk_auction"
    table_name = "stk_auction"
    pk_columns = ["ts_code", "trade_date"]
