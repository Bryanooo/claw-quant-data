"""
中央结算系统持股汇总采集器（ccass_hold）
采集策略：按月范围查询
"""

from collectors.base import BaseCollector


class CcassHoldCollector(BaseCollector):
    API_NAME = "ccass_hold"
    table_name = "ccass_hold"
    pk_columns = ["ts_code", "trade_date"]
