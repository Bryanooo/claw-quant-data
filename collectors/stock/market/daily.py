"""
A股日线行情采集器
接口：daily（tushare pro）
"""

import re
import time
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
        """按日期获取当日全市场行情（分组100只/组）"""
        total = 0
        from service.db import query
        stocks = query("SELECT ts_code FROM stock_basic WHERE list_status = 'L'")
        codes = [s["ts_code"] for s in stocks]

        for i in range(0, len(codes), 100):
            group = codes[i:i+100]
            code_str = ",".join(group)
            try:
                rows = self.collect(ts_code=code_str, trade_date=trade_date)
                total += rows
            except Exception as e:
                self.logger.warning(f"⚠️  组 {i//100} 失败: {e}")
            time.sleep(0.3)

        return total

    def collect_history_stock(self, ts_code: str, start_date: str = None, end_date: str = None) -> int:
        """获取单只股票全部历史日线"""
        params = {"ts_code": ts_code}
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date
        return self.collect(**params)


