"""
东方财富题材成分采集器
接口：dc_concept_cons（tushare pro）
"""

from collectors.base import BaseCollector


class DcConceptConsCollector(BaseCollector):
    API_NAME = "dc_concept_cons"
    table_name = "dc_concept_cons"
    pk_columns = ["ts_code", "trade_date", "theme_code"]
