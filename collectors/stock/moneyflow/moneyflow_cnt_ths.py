"""
同花顺概念板块资金流向采集器
接口：moneyflow_cnt_ths（tushare pro）
"""

from collectors.base import BaseCollector


class MoneyflowCntThsCollector(BaseCollector):
    API_NAME = "moneyflow_cnt_ths"
    table_name = "moneyflow_cnt_ths"
    pk_columns = ["ts_code", "trade_date"]
