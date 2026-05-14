"""
大宗交易采集器（block_trade）
"""

from collectors.base import BaseCollector

_FIELDS = ["ts_code","trade_date","price","vol","amount","buyer","seller"]

class BlockTradeCollector(BaseCollector):
    API_NAME = "block_trade"
    table_name = "block_trade"
    pk_columns = ["ts_code", "trade_date", "price", "buyer", "seller"]
