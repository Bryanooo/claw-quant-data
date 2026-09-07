"""
A股日线行情采集器
接口：daily（tushare pro）
"""

import re
import pandas as pd
from collectors.base import BaseCollector


def _fix_date(val):
    if val is None:
        return None
    if isinstance(val, float) and (pd.isna(val) or str(val) == "nan"):
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


class DailyCollector(BaseCollector):
    API_NAME = "daily"
    table_name = "daily"
    pk_columns = ["ts_code", "trade_date"]

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        if "trade_date" in df.columns:
            df["trade_date"] = df["trade_date"].apply(_fix_date)
        before = len(df)
        df = df.dropna(subset=["trade_date"], how="any")
        if len(df) < before:
            self.logger.warning(f"过滤掉 {before - len(df)} 行（trade_date 为空）")
        return df

    def collect_by_date(self, trade_date: str) -> int:
        """按日期使用 Tushare 支持的全市场分区采集。

        ``ts_code`` 不接受逗号分隔列表；旧实现会把一百只代码当成一个代码，
        最终得到静默空结果。单交易日全市场请求低于接口 6000 行上限，并由
        覆盖审计进一步验证截面数量。
        """
        return self.collect(trade_date=trade_date)

    def collect_history_stock(self, ts_code: str, start_date: str = None, end_date: str = None) -> int:
        """获取单只股票全部历史日线"""
        params = {"ts_code": ts_code}
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date
        return self.collect(**params)
