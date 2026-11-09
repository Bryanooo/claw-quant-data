"""
fina_mainbz: 主营业务构成采集器
"""

import logging

import pandas as pd

from collectors.tushare_raw import IncompleteCollectionError
from collectors.stock.finance.base import BaseFinanceCollector

logger = logging.getLogger("collector.fina_mainbz")

_FIELDS = [
    "ts_code",
    "end_date",
    "bz_item",
    "bz_code",
    "bz_sales",
    "bz_profit",
    "bz_cost",
]


class FinaMainbzCollector(BaseFinanceCollector):
    INTERFACE_NAME = "fina_mainbz_vip"
    TABLE_NAME = "fina_mainbz"
    CORE_FIELDS = _FIELDS
    PK_COLUMNS = ["ts_code", "end_date", "bz_item", "bz_code"]

    def partition_completion_evidence(self):
        proof = super().partition_completion_evidence()
        scopes = proof["scopes"]
        complete = (
            len(scopes) == 3
            and {s["parameters"].get("type") for s in scopes} == {"I", "P", "D"}
            and len({s["period"] for s in scopes}) == 1
        )
        proof["mainbz_classifications_verified"] = proof["verified"] and complete
        proof["verified"] = proof["mainbz_classifications_verified"]
        return proof

    def fetch_period(self, period: str):
        """按行业、产品和地区分别取完当前报告期。"""
        all_rows = []
        for bz_type, label in [("I", "按行业"), ("P", "按产品"), ("D", "按地区")]:
            df = self._fetch_paginated(period, extra_params={"type": bz_type})
            if df is not None and len(df) > 0:
                if "bz_code" not in df or not df["bz_code"].eq(bz_type).all():
                    raise IncompleteCollectionError(f"fina_mainbz_vip returned a different classification for type={bz_type}")
                logger.info(f"  fina_mainbz({period}, {label}): {len(df)} 行")
                all_rows.append(df)
        if not all_rows:
            return pd.DataFrame(columns=self.CORE_FIELDS)
        return pd.concat(all_rows, ignore_index=True).drop_duplicates(
            subset=self.PK_COLUMNS,
            keep="last",
        )
