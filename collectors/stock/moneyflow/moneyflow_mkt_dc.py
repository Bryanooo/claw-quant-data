"""
大盘资金流向（东方财富 DC）采集器
接口：moneyflow_mkt_dc（tushare pro）
"""

from collectors.base import BaseCollector


class MoneyflowMktDcCollector(BaseCollector):
    API_NAME = "moneyflow_mkt_dc"
    table_name = "moneyflow_mkt_dc"
    pk_columns = ["trade_date"]
