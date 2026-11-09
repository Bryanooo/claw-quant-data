"""
沪深港通股票列表采集器
接口：stock_hsgt（tushare pro）
"""

from collectors.base import BaseCollector


class StockHsgtCollector(BaseCollector):
    API_NAME = "stock_hsgt"
    table_name = "stock_hsgt"
    pk_columns = ["ts_code", "trade_date", "type"]

    def fetch(self, **params):
        frame = super().fetch(**params)
        if set(params) == {'trade_date', 'type'} and (
                frame.empty or len(frame) >= 2000 or frame.ts_code.isna().any()
                or frame.ts_code.duplicated().any()
                or set(frame.trade_date.astype(str)) != {params['trade_date']}
                or set(frame.type) != {params['type']}):
            raise ValueError(f"stock_hsgt partition not certified: {params}")
        return frame



