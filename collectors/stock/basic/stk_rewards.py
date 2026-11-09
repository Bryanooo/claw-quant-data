"""
管理层薪酬和持股采集器
接口：stk_rewards（tushare pro）
"""

import re
import pandas as pd
from collectors.base import BaseCollector


def _fix_date(val):
    """尝试将各种日期格式转为 YYYY-MM-DD，无效返回 None"""
    if val is None:
        return None
    if isinstance(val, float) and (pd.isna(val) or str(val) == "nan"):
        return None
    s = str(val).strip()
    if not s or s.lower() in ("nan", "nat", "none"):
        return None
    m = re.match(r"^(\d{4})(\d{2})$", s)
    if m:
        return f"{m.group(1)}-{m.group(2)}-01"
    m = re.match(r"^(\d{4})(\d{2})(\d{2})$", s)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    if re.match(r"^\d{4}-\d{2}-\d{2}$", s):
        return s
    return None


class StkRewardsCollector(BaseCollector):
    API_NAME = "stk_rewards"
    table_name = "stk_rewards"
    pk_columns = ["ts_code", "name", "end_date", "ann_date"]

    def fetch(self, **params):
        frame = super().fetch(**params)
        if params.get('end_date') and params.get('ts_code') and not frame.empty:
            allowed = set(params['ts_code'].split(','))
            if (not set(frame.ts_code).issubset(allowed)
                    or set(frame.end_date.astype(str)) != {params['end_date']}):
                raise ValueError('stk_rewards returned an out-of-scope stock or period')
        return frame

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        for col in ["ann_date", "end_date"]:
            if col in df.columns:
                df[col] = df[col].apply(_fix_date)
        # Never silently collapse revised pay disclosures.
        if df[self.pk_columns].isna().any().any():
            raise ValueError('stk_rewards missing disclosure identity')
        df = df.drop_duplicates()
        if df.duplicated(self.pk_columns).any():
            raise ValueError('stk_rewards conflicting pay records for the same announcement')
        # All identical source duplicates are harmless.
        before = len(df)
        df = df.dropna(subset=["ts_code", "name", "end_date"], how="any")
        if len(df) < before:
            self.logger.warning(f"过滤掉 {before - len(df)} 行（薪酬主键不完整）")
        return df
