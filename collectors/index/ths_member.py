"""
申万行业成分构成采集器（分级）
接口：ths_member（tushare pro）

说明：
  获取申万行业成分构成，可按行业代码查询成分股。
  也支持 level 参数（不传则获取所有级别）。
"""

import pandas as pd
from collectors.base import BaseCollector, NonRetryableCollectorError
from collectors.tushare_raw import IncompleteCollectionError


class ThsMemberCollector(BaseCollector):
    """申万行业成分构成采集器"""

    API_NAME = "ths_member"
    table_name = "ths_member"
    pk_columns = ["ts_code", "con_code"]
    collector_version = "2"

    RESPONSE_LIMIT = 6_000

    def fetch(self, **params) -> pd.DataFrame:
        if not params.get("ts_code") and not params.get("con_code"):
            raise NonRetryableCollectorError(
                "ths_member requires ts_code or con_code; an unbounded request "
                "can be silently truncated at 6000 rows"
            )
        return super().fetch(**params)

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        """数据清洗"""
        if df is None or df.empty:
            return df
        df = df.copy()
        if "trade_date" in df.columns:
            df["trade_date"] = df["trade_date"].astype(str)
        return df

    def validate_response(self, df: pd.DataFrame, parameters: dict) -> None:
        if len(df) >= self.RESPONSE_LIMIT:
            raise IncompleteCollectionError(
                f"ths_member returned the {self.RESPONSE_LIMIT}-row cap; "
                "a narrower board/stock partition is required"
            )
        for parameter in ("ts_code", "con_code"):
            expected = parameters.get(parameter)
            if expected and not df.empty and set(df[parameter].dropna()) != {expected}:
                raise IncompleteCollectionError(
                    f"ths_member ignored the {parameter} partition {expected}"
                )

    def store(self, df: pd.DataFrame) -> int:
        # Each automatic child requests one board. Reconcile that board inside
        # one transaction so constituents removed upstream do not remain as
        # false current members, while other boards are untouched.
        return self.store_partition_snapshot(df, partition_columns=("ts_code",))
