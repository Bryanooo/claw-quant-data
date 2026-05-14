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
    pk_columns = ["ts_code", "name", "ann_date"]

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        for col in ["ann_date", "end_date"]:
            if col in df.columns:
                df[col] = df[col].apply(_fix_date)
        # 过滤 ann_date 为空的记录（主键不能为空）
        before = len(df)
        df = df.dropna(subset=["ann_date"], how="any")
        if len(df) < before:
            self.logger.warning(f"过滤掉 {before - len(df)} 行（ann_date 为空）")
        return df
