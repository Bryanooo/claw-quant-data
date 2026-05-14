"""
个股资金流向（同花顺）采集器
接口：moneyflow_ths（tushare pro）
"""

from collectors.base import BaseCollector


class MoneyflowThsCollector(BaseCollector):
    API_NAME = "moneyflow_ths"
    table_name = "moneyflow_ths"
    pk_columns = ["ts_code", "trade_date"]
