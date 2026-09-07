"""
指数周线行情采集器
接口：index_weekly（tushare pro）

完整性策略：按最后交易日分区，并使用 Tushare 标准 limit/offset 穷尽全市场。
"""

import pandas as pd
from collectors.base import BaseCollector
from collectors.contracts import PaginationMode


class IndexWeeklyCollector(BaseCollector):
    """指数周线行情采集器"""

    API_NAME = "index_weekly"
    table_name = "index_weekly"
    pk_columns = ["ts_code", "trade_date"]

    supports_range_query = True  # 支持 start_date/end_date 范围查询
    pagination_mode = PaginationMode.OFFSET
    collector_version = "2"

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        """数据清洗"""
        if df is None or df.empty:
            return df
        df = df.copy()
        if "trade_date" in df.columns:
            df["trade_date"] = df["trade_date"].astype(str)
        return df
