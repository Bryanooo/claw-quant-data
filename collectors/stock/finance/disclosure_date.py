"""
disclosure_date: 财报披露计划采集器
"""

import logging
import math
from collectors.stock.finance.base import BaseFinanceCollector

logger = logging.getLogger("collector.disclosure_date")

_FIELDS = [
    "ts_code","ann_date","end_date","pre_date","actual_date","modify_date",
]

class DisclosureDateCollector(BaseFinanceCollector):
    INTERFACE_NAME = "disclosure_date"
    TABLE_NAME = "disclosure_date"
    CORE_FIELDS = _FIELDS

    def save(self, df):
        """ann_date 可能为 null，PK = (ts_code, end_date)"""
        if df is None or len(df) == 0:
            return
        fields = self.CORE_FIELDS
        cols = ",".join(fields)
        phs = ",".join(["%s"] * len(fields))
        updates = ",".join([f"{c}=EXCLUDED.{c}" for c in fields if c not in ("ts_code","end_date")])

        with self.db.cursor() as cur:
            for _, r in df.iterrows():
                vals = tuple(
                    None if (v is None or (isinstance(v, float) and math.isnan(v)) or (isinstance(v, str) and v.strip() == ""))
                    else v for v in [r.get(c) for c in fields]
                )
                cur.execute(
                    f"INSERT INTO {self.TABLE_NAME} ({cols}) "
                    f"VALUES ({phs}) ON CONFLICT (ts_code, end_date) "
                    f"DO UPDATE SET {updates}",
                    vals
                )
        self.db.commit()
        logger.info(f"  ✅ disclosure_date: upsert {len(df)} 行")
