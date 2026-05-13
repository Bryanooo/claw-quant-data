"""
income: 利润表采集器
"""

import logging
from collectors.finance.base import BaseFinanceCollector

logger = logging.getLogger("collector.income")

_FIELDS = [
    "ts_code","ann_date","f_ann_date","end_date","report_type","comp_type",
    "basic_eps","diluted_eps",
    "revenue","total_revenue",
    "oper_cost","sell_exp","admin_exp","fin_exp","rd_exp",
    "biz_tax_surchg","assets_impair_loss",
    "invest_income","fv_value_chg_gain",
    "operate_profit","non_oper_income","non_oper_exp",
    "total_profit","income_tax",
    "n_income","n_income_attr_p","minority_gain",
    "ebit","ebitda",
    "oth_compr_income","t_compr_income","compr_inc_attr_p",
    "update_flag",
]

class IncomeCollector(BaseFinanceCollector):
    INTERFACE_NAME = "income_vip"
    TABLE_NAME = "income"
    CORE_FIELDS = _FIELDS
    PK_COLUMNS = ["ts_code", "end_date", "report_type"]
