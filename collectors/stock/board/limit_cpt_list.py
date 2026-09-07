"""
最强板块统计采集器
接口：limit_cpt_list（tushare pro）
"""

from collectors.base import BaseCollector


class LimitCptListCollector(BaseCollector):
    API_NAME = "limit_cpt_list"
    table_name = "limit_cpt_list"
    pk_columns = ["ts_code", "trade_date"]
