"""
fina_indicator: 财务指标采集器
"""

import logging
from collectors.stock.finance.base import BaseFinanceCollector

logger = logging.getLogger("collector.fina_indicator")

_FIELDS = [
    "ts_code","ann_date","end_date","report_type","comp_type",
    "eps","dt_eps","bps","ocfps","revenue_ps",
    "roe","roe_waa","roe_dt","roa","roic",
    "grossprofit_margin","netprofit_margin",
    "current_ratio","quick_ratio","debt_to_assets","debt_to_eqt","ebit_to_interest",
    "ar_turn","inv_turn","assets_turn","turn_days",
    "fcff","fcfe","salescash_to_or",
    "profit_dedt","extra_item",
    # Provider indicator definitions; never substitute these into income or
    # balancesheet fields merely because their names look similar.
    "ebit","ebitda","daa","fa_turn","total_fa_trun","fixed_assets",
    "update_flag",
]

class FinaIndicatorCollector(BaseFinanceCollector):
    INTERFACE_NAME = "fina_indicator_vip"
    TABLE_NAME = "fina_indicator"
    CORE_FIELDS = _FIELDS
    PK_COLUMNS = ["ts_code", "end_date"]
