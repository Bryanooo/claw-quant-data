"""
同花顺热榜采集器
接口：ths_hot（tushare pro）
"""

import hashlib

import pandas as pd

from collectors.base import BaseCollector


class ThsHotCollector(BaseCollector):
    API_NAME = "ths_hot"
    table_name = "ths_hot"
    pk_columns = ["source_key"]

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        """Preserve non-A-share ranks whose upstream code is legitimately null."""
        frame = df.copy()

        def source_key(row: pd.Series) -> str:
            values = (
                row.get("trade_date"),
                row.get("data_type"),
                row.get("ts_code"),
                row.get("ts_name"),
                row.get("rank"),
                row.get("rank_time"),
            )
            canonical = "|".join(
                "" if pd.isna(value) else str(value).strip() for value in values
            )
            return hashlib.md5(
                canonical.encode("utf-8"), usedforsecurity=False
            ).hexdigest()

        frame["source_key"] = frame.apply(source_key, axis=1)
        return frame
