"""
cashflow: 现金流量表采集器
"""

import logging
from collectors.finance.base import BaseFinanceCollector

logger = logging.getLogger("collector.cashflow")

_FIELDS = [
    "ts_code","ann_date","f_ann_date","end_date","report_type","comp_type",
    "c_fr_sale_sg","c_inf_fr_operate_a","c_paid_goods_s","c_paid_to_for_empl",
    "c_paid_for_taxes","st_cash_out_act","n_cashflow_act",
    "c_disp_withdrwl_invest","c_recp_return_invest","n_recp_disp_fiolta",
    "stot_inflows_inv_act","c_pay_acq_const_fiolta","c_paid_invest",
    "stot_out_inv_act","n_cashflow_inv_act",
    "c_recp_borrow","stot_cash_in_fnc_act","c_prepay_amt_borr",
    "c_pay_dist_dpcp_int_exp","stot_cashout_fnc_act","n_cash_flows_fnc_act",
    "free_cashflow","n_incr_cash_cash_equ","c_cash_equ_beg_period",
    "c_cash_equ_end_period","net_profit","financian_exp",
    "depr_fa_coga_dpba","oth_cash_pay_oper_act",
    "update_flag",
]

class CashflowCollector(BaseFinanceCollector):
    INTERFACE_NAME = "cashflow_vip"
    TABLE_NAME = "cashflow"
    CORE_FIELDS = _FIELDS
    PK_COLUMNS = ["ts_code", "end_date", "report_type"]
