"""
股东人数采集器（stk_holdernumber）
"""

from datetime import date, datetime
import hashlib

import pandas as pd

from collectors.base import BaseCollector


_NULL_IDENTITY_VALUE = "<NULL>"
_IDENTITY_SEPARATOR = "\x1f"


def _identity_value(value) -> str:
    if value is None or pd.isna(value):
        return _NULL_IDENTITY_VALUE
    if isinstance(value, (date, datetime)):
        return value.date().isoformat() if isinstance(value, datetime) else value.isoformat()
    text = str(value).strip()
    return text or _NULL_IDENTITY_VALUE


def holdernumber_source_key(row: pd.Series) -> str:
    """Return the stable identity of one upstream shareholder-count record."""
    identity = _IDENTITY_SEPARATOR.join(
        _identity_value(row.get(column))
        for column in ("ts_code", "ann_date", "end_date")
    )
    return hashlib.md5(identity.encode("utf-8"), usedforsecurity=False).hexdigest()


class StkHoldernumberCollector(BaseCollector):
    API_NAME = "stk_holdernumber"
    table_name = "stk_holdernumber"
    # ``end_date`` is nullable in real upstream payloads. Announcement date is
    # part of the source identity so corrections remain lossless instead of
    # overwriting an earlier announcement for the same effective period.
    pk_columns = ["source_key"]

    @staticmethod
    def _canonical_date(value):
        if value is None or pd.isna(value) or str(value).strip() == "":
            return None
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        parsed = pd.to_datetime(str(value).strip(), format="%Y%m%d", errors="coerce")
        if pd.isna(parsed):
            parsed = pd.to_datetime(str(value).strip(), errors="coerce")
        return None if pd.isna(parsed) else parsed.date()

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        result = df.copy()
        for column in ("ann_date", "end_date"):
            if column in result.columns:
                result[column] = result[column].map(self._canonical_date)

        result["source_key"] = result.apply(holdernumber_source_key, axis=1)
        return result
