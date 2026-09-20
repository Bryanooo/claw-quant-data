"""
卖方盈利预测数据采集器（report_rc）
"""

import hashlib

import pandas as pd

from collectors.base import BaseCollector
from collectors.contracts import PaginationMode


_IDENTITY_COLUMNS = (
    "ts_code",
    "report_date",
    "report_title",
    "org_name",
    "author_name",
    "quarter",
)
_NULL_IDENTITY_VALUE = "<NULL>"
_IDENTITY_SEPARATOR = "\x1f"


def _identity_value(value, *, is_date: bool = False) -> str:
    if value is None or pd.isna(value):
        return _NULL_IDENTITY_VALUE
    text = str(value).strip()
    if not text:
        return _NULL_IDENTITY_VALUE
    if is_date:
        parsed = pd.to_datetime(text, errors="coerce")
        if not pd.isna(parsed):
            return parsed.date().isoformat()
    return text


def report_source_key(row: pd.Series) -> str:
    """Return a stable identity for one broker report forecast row.

    A report can contain one row per forecast quarter, while many brokers can
    publish reports for the same stock on the same day.  The former
    ``(ts_code, report_date, quarter)`` key collapsed those independent rows
    and could not represent reports without a forecast quarter.
    """
    identity = _IDENTITY_SEPARATOR.join(
        _identity_value(row.get(column), is_date=column == "report_date")
        for column in _IDENTITY_COLUMNS
    )
    return hashlib.md5(identity.encode("utf-8"), usedforsecurity=False).hexdigest()


class ReportRcCollector(BaseCollector):
    API_NAME = "report_rc"
    table_name = "report_rc"
    pk_columns = ["source_key"]
    pagination_mode = PaginationMode.OFFSET

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        transformed = df.copy()
        transformed["source_key"] = transformed.apply(report_source_key, axis=1)
        return transformed
