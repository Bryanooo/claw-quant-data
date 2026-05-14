"""
同花顺行业资金流向采集器
接口：moneyflow_ind_ths（tushare pro）
"""

from collectors.base import BaseCollector


class MoneyflowIndThsCollector(BaseCollector):
    API_NAME = "moneyflow_ind_ths"
    table_name = "moneyflow_ind_ths"
    pk_columns = ["ts_code", "trade_date"]
