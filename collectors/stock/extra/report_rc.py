"""
卖方盈利预测数据采集器（report_rc）
"""

from collectors.base import BaseCollector


class ReportRcCollector(BaseCollector):
    API_NAME = "report_rc"
    table_name = "report_rc"
    pk_columns = ["ts_code", "report_date", "quarter"]
