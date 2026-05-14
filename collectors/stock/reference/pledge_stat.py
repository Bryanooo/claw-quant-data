"""
股权质押统计采集器
接口：pledge_stat
采集策略：逐个股票拉
"""

import re
import pandas as pd
from collectors.base import BaseCollector


class PledgeStatCollector(BaseCollector):
    API_NAME = "pledge_stat"
    table_name = "pledge_stat"
    pk_columns = ["ts_code", "end_date"]

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
        return self.pro.pledge_stat(**params)

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        if "end_date" in df.columns:
            df["end_date"] = df["end_date"].apply(self._fix_date)
        # 过滤掉关键字段为空的记录
        before = len(df)
        df = df.dropna(subset=["end_date"], how="any")
        if len(df) < before:
            self.logger.warning(f"过滤掉 {before - len(df)} 行（end_date 为空）")
        return df

    def collect_by_stock(self, ts_code: str) -> int:
        return self.collect(ts_code=ts_code)
