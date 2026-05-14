"""
股票回购采集器
接口：repurchase
采集策略：按公告日期分页拉
"""

import re
import pandas as pd
from collectors.base import BaseCollector, safe_str, safe_float


class RepurchaseCollector(BaseCollector):
    API_NAME = "repurchase"
    table_name = "repurchase"
    pk_columns = ["ts_code", "ann_date"]

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
        fields = [
            "ts_code", "ann_date", "end_date", "proc", "exp_date",
            "vol", "amount", "high_limit", "low_limit",
        ]
        df = self.pro.repurchase(**params, fields=",".join(fields))
        if df is None or df.empty:
            return pd.DataFrame(columns=fields)
        return df

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        for col in ["ann_date", "end_date", "exp_date"]:
            if col in df.columns:
                df[col] = df[col].apply(self._fix_date)
        # 过滤掉关键字段为空的记录
        before = len(df)
        df = df.dropna(subset=["ann_date", "ts_code"], how="any")
        if len(df) < before:
            self.logger.warning(f"过滤掉 {before - len(df)} 行（ann_date/ts_code 为空）")
        return df

    def collect_by_date(self, start_date: str, end_date: str = "") -> int:
        params = {"start_date": start_date}
        if end_date:
            params["end_date"] = end_date
        return self.collect(**params)
