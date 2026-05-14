"""
AH股比价采集器（stk_ah_comparison）
"""

from collectors.base import BaseCollector


class StkAhComparisonCollector(BaseCollector):
    API_NAME = "stk_ah_comparison"
    table_name = "stk_ah_comparison"
    pk_columns = ["trade_date", "ts_code"]
