"""
前十大流通股东采集器
接口：top10_floatholders
采集策略：逐个股票按报告期拉
"""

import re
import pandas as pd
from collectors.base import BaseCollector


class Top10FloatholdersCollector(BaseCollector):
    API_NAME = "top10_floatholders"
    table_name = "top10_floatholders"
    pk_columns = ["ts_code", "end_date", "holder_name"]

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
        return self.pro.top10_floatholders(**params)

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        for col in ["ann_date", "end_date"]:
            if col in df.columns:
                df[col] = df[col].apply(self._fix_date)
        before = len(df)
        df = df.dropna(subset=["end_date", "holder_name"], how="any")
        if len(df) < before:
            self.logger.warning(f"过滤掉 {before - len(df)} 行（end_date/holder_name 为空）")
        return df

    def collect_by_stock(self, ts_code: str, start_date: str = "", end_date: str = "") -> int:
        params = {"ts_code": ts_code}
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date
        return self.collect(**params)
