"""
balancesheet: 资产负债表采集器
"""

import logging
from collectors.finance.base import BaseFinanceCollector

logger = logging.getLogger("collector.balancesheet")

_FIELDS = [
    "ts_code","ann_date","f_ann_date","end_date","report_type","comp_type",
    # 资产
    "money_cap","trad_asset","notes_receiv","accounts_receiv","oth_receiv",
    "prepayment","inventories","total_cur_assets",
    "lt_eqt_invest","invest_real_estate","fix_assets","cip",
    "intan_assets","r_and_d","goodwill","lt_amor_exp","defer_tax_assets",
    "total_nca","total_assets",
    # 负债
    "st_borr","notes_payable","acct_payable","adv_receipts",
    "payroll_payable","taxes_payable","oth_payable",
    "total_cur_liab","lt_borr","bond_payable","lt_payable",
    "defer_tax_liab","total_ncl","total_liab",
    # 权益
    "total_hldr_eqy_inc_min_int","total_share","cap_rese",
    "undistr_porfit","surplus_rese","treasury_share","minority_int",
    "update_flag",
]

class BalancesheetCollector(BaseFinanceCollector):
    INTERFACE_NAME = "balancesheet_vip"
    TABLE_NAME = "balancesheet"
    CORE_FIELDS = _FIELDS
    PK_COLUMNS = ["ts_code", "end_date", "report_type"]
