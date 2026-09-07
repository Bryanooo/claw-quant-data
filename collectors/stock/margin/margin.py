"""
两融数据采集器
"""

from collectors.base import BaseCollector
from collectors.contracts import PaginationMode


class MarginCollector(BaseCollector):
    API_NAME = "margin"
    table_name = "margin"
    pk_columns = ["trade_date", "exchange_id"]


class MarginDetailCollector(BaseCollector):
    API_NAME = "margin_detail"
    table_name = "margin_detail"
    pk_columns = ["trade_date", "ts_code"]
    # Live verification shows that the gateway accepts standard limit/offset.
    # A complete market day is normally larger than the old 2,000-row response
    # boundary, so a single request must never be treated as exhaustive.
    pagination_mode = PaginationMode.OFFSET
    collector_version = "2"


class MarginSecsCollector(BaseCollector):
    API_NAME = "margin_secs"
    table_name = "margin_secs"
    pk_columns = ["trade_date", "ts_code"]


class SlbLenCollector(BaseCollector):
    API_NAME = "slb_len"
    table_name = "slb_len"
    pk_columns = ["trade_date"]
    pagination_mode = PaginationMode.OFFSET
    collector_version = "2"
