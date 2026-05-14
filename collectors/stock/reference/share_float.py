"""
限售股解禁采集器（share_float）
"""

from collectors.base import BaseCollector


class ShareFloatCollector(BaseCollector):
    API_NAME = "share_float"
    table_name = "share_float"
    pk_columns = ["ts_code", "float_date", "holder_name", "share_type"]
