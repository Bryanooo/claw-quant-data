"""
申万行业成分构成采集器（分级）
接口：ths_member（tushare pro）

说明：
  获取申万行业成分构成，可按行业代码查询成分股。
  也支持 level 参数（不传则获取所有级别）。
"""

import pandas as pd
from collectors.base import BaseCollector


class ThsMemberCollector(BaseCollector):
    """申万行业成分构成采集器"""

    API_NAME = "ths_member"
    table_name = "ths_member"
    pk_columns = ["ts_code", "con_code"]

    supports_range_query = True

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        """数据清洗"""
        if df is None or df.empty:
            return df
        df = df.copy()
        if "trade_date" in df.columns:
            df["trade_date"] = df["trade_date"].astype(str)
        return df
