"""
股票基础信息采集器
接口：stock_basic（tushare pro）

运行模式：staging + 原子快照合并，建议每日/每周跑一次
"""



import pandas as pd
from collectors.base import BaseCollector
from collectors.contracts import ResourceClass, WriteMode


class StockBasicCollector(BaseCollector):
    """股票基础信息采集器"""

    write_mode = WriteMode.SNAPSHOT
    resource_class = ResourceClass.REFERENCE

    API_NAME = "stock_basic"
    table_name = "stock_basic"
    pk_columns = ["ts_code"]

    _FIELDS = (
        "ts_code,symbol,name,area,industry,fullname,enname,cnspell,market,"
        "exchange,curr_type,list_status,list_date,delist_date,is_hs,"
        "act_name,act_ent_type"
    )

    def fetch(self, **_params) -> pd.DataFrame:
        """Fetch active, delisted and paused universes with status evidence."""
        frames = [
            self.pro.stock_basic(list_status=status, fields=self._FIELDS)
            for status in ("L", "D", "P")
        ]
        non_empty = [frame for frame in frames if frame is not None and not frame.empty]
        return pd.concat(non_empty, ignore_index=True) if non_empty else pd.DataFrame()

    def store(self, df: pd.DataFrame) -> int:
        """Merge a complete snapshot atomically without an ACCESS EXCLUSIVE lock."""
        return self.store_snapshot(df)
