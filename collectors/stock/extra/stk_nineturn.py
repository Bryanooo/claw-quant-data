"""
神奇九转指标采集器（stk_nineturn）
"""

from collectors.base import BaseCollector


class StkNineturnCollector(BaseCollector):
    API_NAME = "stk_nineturn"
    table_name = "stk_nineturn"
    pk_columns = ["ts_code", "trade_date", "freq"]
