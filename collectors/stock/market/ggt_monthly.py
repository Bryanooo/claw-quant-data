"""
港股通每月成交统计采集器
接口：ggt_monthly（tushare pro）
"""

from collectors.base import BaseCollector


class GgtMonthlyCollector(BaseCollector):
    API_NAME = "ggt_monthly"
    table_name = "ggt_monthly"
    pk_columns = ["month"]
