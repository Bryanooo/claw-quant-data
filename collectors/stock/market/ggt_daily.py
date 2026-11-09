"""
港股通每日成交统计采集器
接口：ggt_daily（tushare pro）
"""

from collectors.base import BaseCollector


class GgtDailyCollector(BaseCollector):
    API_NAME = "ggt_daily"
    table_name = "ggt_daily"
    pk_columns = ["trade_date"]

    def validate_response(self, df, parameters):
        day = parameters.get("trade_date")
        if day and not df.empty and (
            len(df) != 1 or str(df.iloc[0]["trade_date"]).replace("-", "") != str(day).replace("-", "")
        ):
            raise ValueError("ggt_daily returned data outside the requested day")
