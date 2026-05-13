"""
express: 业绩快报采集器
"""

import logging
from collectors.stock.finance.base import BaseFinanceCollector

logger = logging.getLogger("collector.express")

_FIELDS = [
    "ts_code","ann_date","end_date",
    "revenue","operate_profit","total_profit","n_income","total_assets",
    "total_hldr_eqy_exc_min_int","diluted_eps","diluted_roe",
    "yoy_net_profit","bps","yoy_sales","yoy_dedu_np",
    "is_audit","perf_summary","update_flag",
]

class ExpressCollector(BaseFinanceCollector):
    INTERFACE_NAME = "express_vip"
    TABLE_NAME = "express"
    CORE_FIELDS = _FIELDS
    PK_COLUMNS = ["ts_code", "end_date", "ann_date"]
