"""
IPO新股列表采集器
接口：new_share（tushare pro）
"""

from collectors.base import BaseCollector


class NewShareCollector(BaseCollector):
    API_NAME = "new_share"
    table_name = "new_share"
    pk_columns = ["ts_code"]



