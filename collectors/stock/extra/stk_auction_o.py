"""
股票开盘集合竞价采集器（stk_auction_o）
"""

from collectors.base import BaseCollector


class StkAuctionOCollector(BaseCollector):
    API_NAME = "stk_auction_o"
    table_name = "stk_auction_o"
    pk_columns = ["ts_code", "trade_date"]
