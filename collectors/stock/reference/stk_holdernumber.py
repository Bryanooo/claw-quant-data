"""
股东人数采集器（stk_holdernumber）
"""

from collectors.base import BaseCollector


class StkHoldernumberCollector(BaseCollector):
    API_NAME = "stk_holdernumber"
    table_name = "stk_holdernumber"
    pk_columns = ["ts_code", "end_date"]
