"""
forecast: 业绩预告采集器
"""

import logging
from collectors.stock.finance.base import BaseFinanceCollector

logger = logging.getLogger("collector.forecast")

_FIELDS = [
    "ts_code","ann_date","end_date","type",
    "p_change_min","p_change_max","net_profit_min","net_profit_max",
    "last_parent_net","first_ann_date","summary","change_reason",
]

class ForecastCollector(BaseFinanceCollector):
    INTERFACE_NAME = "forecast_vip"
    TABLE_NAME = "forecast"
    CORE_FIELDS = _FIELDS
    PK_COLUMNS = ["ts_code", "end_date", "ann_date"]
    # PK = (ts_code, end_date, ann_date) — 可能同一天多条
