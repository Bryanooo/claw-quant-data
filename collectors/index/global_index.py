"""
国际指数行情采集器
接口：index_global（tushare pro）

说明：
  获取国际主要指数行情。
  可用 ts_code 包括：DJI（道琼斯）、SPX（标普500）、IXIC（纳斯达克）、
  FTSE（英国富时100）、N225（日经225）等。
  支持 start_date/end_date 范围查询。
"""

import pandas as pd
from collectors.base import BaseCollector


class IndexGlobalCollector(BaseCollector):
    """国际指数行情采集器"""

    API_NAME = "index_global"
    table_name = "index_global"
    pk_columns = ["ts_code", "trade_date"]

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        """数据清洗"""
        if df is None or df.empty:
            return df
        df = df.copy()
        if "trade_date" in df.columns:
            df["trade_date"] = df["trade_date"].astype(str)
        return df
