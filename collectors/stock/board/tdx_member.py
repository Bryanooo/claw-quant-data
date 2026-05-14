"""
通达信板块成分采集器
接口：tdx_member（tushare pro）
"""

from collectors.base import BaseCollector


class TdxMemberCollector(BaseCollector):
    API_NAME = "tdx_member"
    table_name = "tdx_member"
    pk_columns = ["ts_code", "trade_date", "con_code"]
