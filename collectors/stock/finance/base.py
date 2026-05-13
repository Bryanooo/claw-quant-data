"""
财务数据采集基类（继承自 BaseCollector）

公共功能：
- fetch_period(period): 调用 _vip 接口按季度取全市场
- save(df): 批量 upsert
"""

import logging
import math
from collectors.base import BaseCollector, get_db_conn

logger = logging.getLogger("collector.finance")


class BaseFinanceCollector(BaseCollector):
    """
    按季度取全市场的财务采集器基类。
    子类只需设置：INTERFACE_NAME, TABLE_NAME, CORE_FIELDS
    """

    INTERFACE_NAME = ""      # 子类覆盖，如 "balancesheet_vip"
    TABLE_NAME = ""           # 子类覆盖
    CORE_FIELDS = []          # 子类覆盖
    PK_COLUMNS = ["ts_code", "end_date", "report_type"]  # 子类覆盖

    def __init__(self):
        super().__init__()
        self.db = get_db_conn()

    def fetch(self, **params):
        """兼容 BaseCollector 抽象方法"""
        import pandas as pd
        return pd.DataFrame()

    def fetch_period(self, period: str):
        """取某个报告期全市场数据"""
        fields = ",".join(self.CORE_FIELDS)
        fn = getattr(self.pro, self.INTERFACE_NAME)
        df = fn(period=period, fields=fields)
        if df is not None and len(df) > 0:
            logger.info(f"  [{self.INTERFACE_NAME}] {period}: {len(df)} 行")
        return df

    def save(self, df):
        """批量 upsert"""
        if df is None or len(df) == 0:
            return

        # 使用显式 PK_COLUMNS（子类覆盖）
        base_keys = self.PK_COLUMNS[:]

        fields = self.CORE_FIELDS
        placeholders = ",".join(["%s"] * len(fields))
        cols = ",".join(fields)
        updates = ",".join([f"{c}=EXCLUDED.{c}" for c in fields if c not in base_keys])
        pk_str = ",".join(base_keys)

        with self.db.cursor() as cur:
            for _, r in df.iterrows():
                vals = tuple(
                    _to_val(r.get(c)) for c in fields
                )
                cur.execute(
                    f"INSERT INTO {self.TABLE_NAME} ({cols}) "
                    f"VALUES ({placeholders}) "
                    f"ON CONFLICT ({pk_str}) DO UPDATE SET {updates}",
                    vals
                )
        self.db.commit()
        periods = sorted(df["end_date"].unique()) if "end_date" in df.columns else ["?"]
        logger.info(f"  ✅ {self.TABLE_NAME} {periods}: upsert {len(df)} 行")


def _to_val(v, k=None):
    """将 NaN/None 转为 None"""
    import math
    if v is None:
        return None
    if isinstance(v, float) and math.isnan(v):
        return None
    if isinstance(v, str) and v.strip() == "":
        return None
    return v
