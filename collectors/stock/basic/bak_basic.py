"""
=============================================================================
股票历史列表（每日）采集器
=============================================================================

接口：bak_basic（tushare pro）
文档：https://tushare.pro/document/2?doc_id=262
"""

import re
import pandas as pd
from collectors.base import BaseCollector


def _fix_date(val):
    """尝试将各种日期转 YYYY-MM-DD，无效返回 None"""
    if val is None:
        return None
    if isinstance(val, float) and (pd.isna(val) or str(val) == "nan"):
        return None
    s = str(val).strip()
    if not s or s.lower() in ("nan", "nat", "none", "0", ""):
        return None
    m = re.match(r"^(\d{4})(\d{2})(\d{2})$", s)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    if re.match(r"^\d{4}-\d{2}-\d{2}$", s):
        return s
    return None


class BakBasicCollector(BaseCollector):
    API_NAME = "bak_basic"
    table_name = "bak_basic"
    pk_columns = ["trade_date", "ts_code"]

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        for col in ["trade_date", "list_date"]:
            if col in df.columns:
                df[col] = df[col].apply(_fix_date)
        # 过滤 trade_date 为空的记录
        before = len(df)
        df = df.dropna(subset=["trade_date"], how="any")
        if len(df) < before:
            self.logger.warning(f"过滤掉 {before - len(df)} 行（trade_date 为空）")
        return df
