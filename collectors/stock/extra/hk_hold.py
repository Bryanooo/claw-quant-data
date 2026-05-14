"""
沪深港股通持股明细采集器（hk_hold）
"""

from collectors.base import BaseCollector


class HkHoldCollector(BaseCollector):
    API_NAME = "hk_hold"
    table_name = "hk_hold"
    pk_columns = ["ts_code", "trade_date"]
