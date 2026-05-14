"""
每日涨跌停价格采集器
接口：stk_limit（tushare pro）
"""

from collectors.base import BaseCollector


class STKLimitCollector(BaseCollector):
    API_NAME = "stk_limit"
    table_name = "stk_limit"
    pk_columns = ["trade_date", "ts_code"]
