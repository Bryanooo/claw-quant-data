"""
东方财富题材库采集器
接口：dc_concept（tushare pro）
"""

from collectors.base import BaseCollector


class DcConceptCollector(BaseCollector):
    API_NAME = "dc_concept"
    table_name = "dc_concept"
    pk_columns = ["theme_code", "trade_date"]
