"""
disclosure_date: 财报披露计划采集器
"""

from collectors.stock.finance.base import BaseFinanceCollector

_FIELDS = [
    "ts_code",
    "ann_date",
    "end_date",
    "pre_date",
    "actual_date",
    "modify_date",
]


class DisclosureDateCollector(BaseFinanceCollector):
    INTERFACE_NAME = "disclosure_date"
    TABLE_NAME = "disclosure_date"
    CORE_FIELDS = _FIELDS
    PK_COLUMNS = ["ts_code", "end_date"]
    # Unlike the VIP statements, this endpoint partitions by end_date. Sending
    # ``period`` is silently ignored by Tushare and expands the response to all
    # historical disclosure plans.
    upstream_period_parameter = "end_date"
