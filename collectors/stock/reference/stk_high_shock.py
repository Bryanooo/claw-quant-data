"""
个股严重异常波动采集器
接口：stk_high_shock
"""

import re
import pandas as pd
from collectors.base import BaseCollector


class StkHighShockCollector(BaseCollector):
    API_NAME = "stk_high_shock"
    table_name = "stk_high_shock"
    pk_columns = ["ts_code", "trade_date"]

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
        return self.pro.stk_high_shock(**params)

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        if "trade_date" in df.columns:
            df["trade_date"] = df["trade_date"].apply(self._fix_date)
        before = len(df)
        df = df.dropna(subset=["trade_date"], how="any")
        if len(df) < before:
            self.logger.warning(f"过滤掉 {before - len(df)} 行（trade_date 为空）")
        return df

    def collect_by_date(self, trade_date: str) -> int:
        return self.collect(trade_date=trade_date)
