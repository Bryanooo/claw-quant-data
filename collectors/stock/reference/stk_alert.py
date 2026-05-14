"""
交易所重点提示证券采集器
接口：stk_alert
"""

import re
import pandas as pd
from collectors.base import BaseCollector


class StkAlertCollector(BaseCollector):
    API_NAME = "stk_alert"
    table_name = "stk_alert"
    pk_columns = ["ts_code", "start_date"]

    def _fix_date(self, val):
        if val is None:
            return None
        s = str(val).strip()
        if not s or s.lower() in ("nan", "nat", "none"):
            return None
        m = re.match(r"^(\d{4})(\d{2})(\d{2})$", s)
        if m:
            return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
        if re.match(r"^\d{4}-\d{2}-\d{2}$", s):
            return s
        return None

    def fetch(self, **params) -> pd.DataFrame:
        return self.pro.stk_alert(**params)

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        for col in ["start_date", "end_date"]:
            if col in df.columns:
                df[col] = df[col].apply(self._fix_date)
        before = len(df)
        df = df.dropna(subset=["start_date"], how="any")
        if len(df) < before:
            self.logger.warning(f"过滤掉 {before - len(df)} 行（start_date 为空）")
        return df

    def collect_by_date(self, trade_date: str) -> int:
        return self.collect(start_date=trade_date, end_date=trade_date)
