"""
两融数据采集器
"""

from collectors.base import BaseCollector


class MarginCollector(BaseCollector):
    API_NAME = "margin"
    table_name = "margin"
    pk_columns = ["trade_date", "exchange_id"]


class MarginDetailCollector(BaseCollector):
    API_NAME = "margin_detail"
    table_name = "margin_detail"
    pk_columns = ["trade_date", "ts_code"]


class MarginSecsCollector(BaseCollector):
    API_NAME = "margin_secs"
    table_name = "margin_secs"
    pk_columns = ["trade_date", "ts_code"]


class SlbLenCollector(BaseCollector):
    API_NAME = "slb_len"
    table_name = "slb_len"
    pk_columns = ["trade_date"]
