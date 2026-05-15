"""
指数周线行情采集器
接口：index_weekly（tushare pro）

注意：
  index_weekly 不支持 start_date/end_date 范围查询，只支持单日 trade_date 参数。
  且只有周五才有数据。
  因此 supports_range_query = False，基类的 collect_all_history 会自动降级为逐日查询。
"""

import pandas as pd
from collectors.base import BaseCollector


class IndexWeeklyCollector(BaseCollector):
    """指数周线行情采集器"""

    API_NAME = "index_weekly"
    table_name = "index_weekly"
    pk_columns = ["ts_code", "trade_date"]

    supports_range_query = True  # 支持 start_date/end_date 范围查询

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        """数据清洗"""
        if df is None or df.empty:
            return df
        df = df.copy()
        if "trade_date" in df.columns:
            df["trade_date"] = df["trade_date"].astype(str)
        return df
