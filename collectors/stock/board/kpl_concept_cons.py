"""
开盘啦题材成分采集器
接口：kpl_concept_cons（tushare pro）
"""

from collectors.base import BaseCollector


class KplConceptConsCollector(BaseCollector):
    API_NAME = "kpl_concept_cons"
    table_name = "kpl_concept_cons"
    pk_columns = ["ts_code", "con_code", "trade_date"]
