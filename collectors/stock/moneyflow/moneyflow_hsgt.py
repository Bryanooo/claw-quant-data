"""
沪深港通资金流向采集器
接口：moneyflow_hsgt（tushare pro）
"""

from collectors.base import BaseCollector


class MoneyflowHsgtCollector(BaseCollector):
    API_NAME = "moneyflow_hsgt"
    table_name = "moneyflow_hsgt"
    pk_columns = ["trade_date"]
