"""
游资名录采集器
接口：hm_list（tushare pro）

⚠️ 注意：Tushare 返回字段名为 "desc"，但 PG "desc" 是关键字，
   表字段实际为 "descr"，需要在 transform 中做重命名。
"""

import pandas as pd
from collectors.base import BaseCollector


class HmListCollector(BaseCollector):
    API_NAME = "hm_list"
    table_name = "hm_list"
    pk_columns = ["name"]

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        """Tushare 返回 'desc'，PG 表字段为 'descr'"""
        if df is not None and not df.empty and "desc" in df.columns:
            df = df.rename(columns={"desc": "descr"})
        return df
