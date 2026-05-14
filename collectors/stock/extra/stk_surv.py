"""
机构调研表采集器（stk_surv）
"""

from collectors.base import BaseCollector


class StkSurvCollector(BaseCollector):
    API_NAME = "stk_surv"
    table_name = "stk_surv"
    pk_columns = ["ts_code", "surv_date", "fund_visitors", "rece_org"]
