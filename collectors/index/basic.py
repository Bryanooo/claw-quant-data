"""
指数基本信息采集器
接口：index_basic（tushare pro）

说明：
  获取各类指数的基本信息，包括代码、名称、发布方、指数类型、币种等。
  market 参数可以用 "SSE" / "SZSE" 等限定交易所，或留空获取全部。
"""

import pandas as pd
from collectors.base import BaseCollector


class IndexBasicCollector(BaseCollector):
    """指数基本信息采集器"""

    API_NAME = "index_basic"
    table_name = "index_basic"
    pk_columns = ["ts_code"]

    def collect(self, market: str = None, **kwargs) -> int:
        """
        采集指数基本信息。

        参数：
          market: 交易所 SSE/SZSE/ALL（空则全量）
        """
        params = {}
        if market:
            params["market"] = market
        return super().collect(**params, **kwargs)
