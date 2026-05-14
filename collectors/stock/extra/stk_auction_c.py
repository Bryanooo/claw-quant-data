"""
股票收盘集合竞价采集器（stk_auction_c）
"""

from collectors.base import BaseCollector


class StkAuctionCCollector(BaseCollector):
    API_NAME = "stk_auction_c"
    table_name = "stk_auction_c"
    pk_columns = ["ts_code", "trade_date"]
