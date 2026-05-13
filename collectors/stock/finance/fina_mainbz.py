"""
fina_mainbz: 主营业务构成采集器
"""

import logging
from collectors.stock.finance.base import BaseFinanceCollector

logger = logging.getLogger("collector.fina_mainbz")

_FIELDS = [
    "ts_code","end_date","bz_item","bz_code","bz_sales","bz_profit","bz_cost",
]

class FinaMainbzCollector(BaseFinanceCollector):
    INTERFACE_NAME = "fina_mainbz_vip"
    TABLE_NAME = "fina_mainbz"
    CORE_FIELDS = _FIELDS
    PK_COLUMNS = ["ts_code", "end_date", "bz_item", "bz_code"]

    def fetch_period(self, period: str):
        """取行业分类(I) + 产品分类(P)，合并"""
        import pandas as pd
        all_rows = []
        for bz_type, label, limit in [("I","按行业",None), ("P","按产品",10000)]:
            kwargs = {"period": period, "type": bz_type, "fields": ",".join(self.CORE_FIELDS)}
            # type P可能超量，需要循环
            df = self.pro.fina_mainbz_vip(**kwargs)
            if df is not None and len(df) > 0:
                logger.info(f"  fina_mainbz({period}, {label}): {len(df)} 行")
                all_rows.append(df)
        return pd.concat(all_rows, ignore_index=True) if all_rows else pd.DataFrame()
