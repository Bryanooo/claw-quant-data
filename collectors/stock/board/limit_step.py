"""
连板天梯采集器
接口：limit_step（tushare pro）
"""

from collectors.base import BaseCollector


class LimitStepCollector(BaseCollector):
    API_NAME = "limit_step"
    table_name = "limit_step"
    pk_columns = ["ts_code", "trade_date"]
