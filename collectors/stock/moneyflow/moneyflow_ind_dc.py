"""
东财板块资金流向采集器（行业+概念，由 content_type 区分）
接口：moneyflow_ind_dc（tushare pro）
"""

from collectors.base import BaseCollector


class MoneyflowIndDcCollector(BaseCollector):
    API_NAME = "moneyflow_ind_dc"
    table_name = "moneyflow_ind_dc"
    pk_columns = ["ts_code", "trade_date", "content_type"]
