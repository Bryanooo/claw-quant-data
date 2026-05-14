"""
每日筹码分布采集器（cyq_chips）
"""

from collectors.base import BaseCollector


class CyqChipsCollector(BaseCollector):
    API_NAME = "cyq_chips"
    table_name = "cyq_chips"
    pk_columns = ["ts_code", "trade_date", "price"]
