"""
大盘指数每日指标采集器
接口：index_dailybasic（tushare pro）

说明：
  获取大盘指数每日指标，包括换手率、量比、市盈率、市净率等。
  支持范围查询（start_date/end_date），不指定 ts_code 时返回全部指数。
"""

import pandas as pd
from collectors.base import BaseCollector


class IndexDailybasicCollector(BaseCollector):
    """大盘指数每日指标采集器"""

    API_NAME = "index_dailybasic"
    table_name = "index_dailybasic"
    pk_columns = ["ts_code", "trade_date"]

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        """数据清洗"""
        if df is None or df.empty:
            return df
        df = df.copy()
        if "trade_date" in df.columns:
            df["trade_date"] = df["trade_date"].astype(str)
        return df
