"""
股权质押明细采集器
接口：pledge_detail
采集策略：逐个股票拉
"""

import re
import pandas as pd
from collectors.base import BaseCollector


class PledgeDetailCollector(BaseCollector):
    API_NAME = "pledge_detail"
    table_name = "pledge_detail"
    pk_columns = ["ts_code", "ann_date", "holder_name", "start_date"]

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
        return self.pro.pledge_detail(**params)

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        for col in ["ann_date", "start_date", "end_date", "release_date"]:
            if col in df.columns:
                df[col] = df[col].apply(self._fix_date)
        # 过滤掉关键字段为空的记录
        before = len(df)
        df = df.dropna(subset=["ann_date", "holder_name", "start_date"], how="any")
        if len(df) < before:
            self.logger.warning(f"过滤掉 {before - len(df)} 行（ann_date/holder_name/start_date 为空）")
        return df

    def collect_by_stock(self, ts_code: str) -> int:
        return self.collect(ts_code=ts_code)
