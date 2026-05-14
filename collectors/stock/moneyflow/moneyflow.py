"""
个股资金流向采集器
接口：moneyflow（tushare pro）
"""

from collectors.base import BaseCollector


class MoneyflowCollector(BaseCollector):
    API_NAME = "moneyflow"
    table_name = "moneyflow"
    pk_columns = ["ts_code", "trade_date"]
