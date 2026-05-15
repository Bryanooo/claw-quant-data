"""
申万行业日线行情采集器
接口：ths_daily（tushare pro）

说明：
  获取申万行业指数的日线行情。
  index_code 参数格式如 801010（不带 .SI 后缀）。
  支持 start_date/end_date 范围查询。

注意：
  Tushare 此接口的参数名是 index_code（不是 ts_code），需要在 fetch 时特殊处理。
"""

import pandas as pd
from collectors.base import BaseCollector


class ThsDailyCollector(BaseCollector):
    """申万行业日线行情采集器"""

    API_NAME = "ths_daily"
    table_name = "ths_daily"
    pk_columns = ["ts_code", "trade_date"]

    supports_range_query = True

    def fetch(self, **params) -> pd.DataFrame:
        """
        覆盖父类 fetch：
        ths_daily 接口的参数名是 index_code（非标准的 ts_code），
        直接通过 pro.query() 调用。
        """
        if not self.API_NAME:
            raise ValueError(f"❌ 子类必须定义 API_NAME")
        return self.pro.query(self.API_NAME, **params)

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        """数据清洗"""
        if df is None or df.empty:
            return df
        df = df.copy()
        if "trade_date" in df.columns:
            df["trade_date"] = df["trade_date"].astype(str)
        return df
