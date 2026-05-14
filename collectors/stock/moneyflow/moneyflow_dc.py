"""
个股资金流向（东方财富 DC）采集器
接口：moneyflow_dc（tushare pro）
"""

from collectors.base import BaseCollector


class MoneyflowDcCollector(BaseCollector):
    API_NAME = "moneyflow_dc"
    table_name = "moneyflow_dc"
    pk_columns = ["ts_code", "trade_date"]
