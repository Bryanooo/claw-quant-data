"""每日筹码分布采集器（cyq_chips）。"""

from collectors.base import BaseCollector
from collectors.stock.extra.adaptive_date_window import (
    AdaptiveDateWindowCollectorMixin,
)


class CyqChipsCollector(AdaptiveDateWindowCollectorMixin, BaseCollector):
    API_NAME = "cyq_chips"
    table_name = "cyq_chips"
    pk_columns = ["ts_code", "trade_date", "price"]
    collector_version = "3"
