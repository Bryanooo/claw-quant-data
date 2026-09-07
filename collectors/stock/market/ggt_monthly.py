"""
港股通每月成交统计采集器
数据源：ggt_daily（Tushare 已停止接受原 ggt_monthly 接口）
"""

import calendar

import pandas as pd

from collectors.base import BaseCollector


class GgtMonthlyCollector(BaseCollector):
    API_NAME = "ggt_daily"
    table_name = "ggt_monthly"
    pk_columns = ["month"]

    def fetch(self, **params) -> pd.DataFrame:
        start_month = params.get("start_month")
        end_month = params.get("end_month")
        if not start_month or not end_month:
            raise ValueError("start_month and end_month are required (YYYYMM)")
        if (
            len(start_month) != 6
            or len(end_month) != 6
            or not start_month.isdigit()
            or not end_month.isdigit()
            or start_month > end_month
        ):
            raise ValueError("invalid month range; use YYYYMM")

        end_year, end_number = int(end_month[:4]), int(end_month[4:])
        end_day = calendar.monthrange(end_year, end_number)[1]
        daily = self.pro.ggt_daily(
            start_date=f"{start_month}01",
            end_date=f"{end_month}{end_day:02d}",
        )
        if daily is None or daily.empty:
            return pd.DataFrame(
                columns=[
                    "month", "day_buy_amt", "day_buy_vol", "day_sell_amt",
                    "day_sell_vol", "total_buy_amt", "total_buy_vol",
                    "total_sell_amt", "total_sell_vol",
                ]
            )

        frame = daily.copy()
        frame["month"] = frame["trade_date"].astype(str).str.replace("-", "").str[:6]
        return frame.groupby("month", as_index=False).agg(
            day_buy_amt=("buy_amount", "mean"),
            day_buy_vol=("buy_volume", "mean"),
            day_sell_amt=("sell_amount", "mean"),
            day_sell_vol=("sell_volume", "mean"),
            total_buy_amt=("buy_amount", "sum"),
            total_buy_vol=("buy_volume", "sum"),
            total_sell_amt=("sell_amount", "sum"),
            total_sell_vol=("sell_volume", "sum"),
        )
