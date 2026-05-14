"""
涨跌停列表（新）采集器
接口：limit_list_d（tushare pro）
"""

import pandas as pd
from collectors.base import BaseCollector


class LimitListDCollector(BaseCollector):
    API_NAME = "limit_list_d"
    table_name = "limit_list_d"
    pk_columns = ["ts_code", "trade_date", "limit_type"]


