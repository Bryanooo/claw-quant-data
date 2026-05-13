"""
dividend: 分红送股采集器（无vip接口）
"""

import logging
import pandas as pd
from collectors.base import BaseCollector

logger = logging.getLogger("collector.dividend")

_FIELDS = [
    "ts_code","end_date","ann_date","div_proc",
    "stk_div","stk_bo_rate","stk_co_rate",
    "cash_div","cash_div_tax",
    "record_date","ex_date","pay_date","div_listdate","imp_ann_date",
    "base_share",
]

class DividendCollector(BaseCollector):
    INTERFACE_NAME = "dividend"
    TABLE_NAME = "dividend"
    # 没有vip接口 — 按股票逐个取

    def fetch(self, ts_code=None, **params):
        types = ["实施","预案"]
        all_rows = []
        for t in types:
            df = self.pro.dividend(ts_code=ts_code, div_proc=t, fields=",".join(_FIELDS))
            if df is not None and len(df) > 0:
                all_rows.append(df)
        return pd.concat(all_rows, ignore_index=True) if all_rows else pd.DataFrame()
