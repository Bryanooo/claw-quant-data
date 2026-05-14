"""
每日筹码及胜率采集器（cyq_perf）
"""

from collectors.base import BaseCollector


class CyqPerfCollector(BaseCollector):
    API_NAME = "cyq_perf"
    table_name = "cyq_perf"
    pk_columns = ["ts_code", "trade_date"]
