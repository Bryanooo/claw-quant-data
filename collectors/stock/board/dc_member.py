"""
东方财富板块成分采集器
接口：dc_member（tushare pro）
"""

from collectors.base import BaseCollector


class DcMemberCollector(BaseCollector):
    API_NAME = "dc_member"
    table_name = "dc_member"
    pk_columns = ["ts_code", "trade_date", "con_code"]
