"""
交易日历采集器
接口：trade_cal（tushare pro）

注意：trade_cal 的 pretrade_date 首行为 NaN，基类通用 store 处理不了，
需要预处理掉 NaN 值再调父类。
"""



import pandas as pd
from collectors.base import BaseCollector


class TradeCalCollector(BaseCollector):
    """交易日历采集器"""

    API_NAME = "trade_cal"
    table_name = "trade_cal"
    pk_columns = ["exchange", "cal_date"]

    def store(self, df: pd.DataFrame) -> int:
        """
        trade_cal 的 pretrade_date 首行为 NaN，基类通用 store 处理不了，
        需要预处理掉 NaN 值再调父类。
        """
        if "pretrade_date" in df.columns:
            mask = df["pretrade_date"].isna()
            if mask.any():
                df = df.copy()
                df.loc[mask, "pretrade_date"] = None
        return super().store(df)



