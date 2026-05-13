"""
=============================================================================
交易日历采集器
=============================================================================

接口：trade_cal（tushare pro）
文档：https://tushare.pro/document/2?doc_id=26

描述：
  获取各大交易所的交易日历数据，包括每日开/休市状态和前一交易日。

权限要求：
  - 最低积分：2000

输出表字段：
  exchange      VARCHAR(8)   交易所 SSE/SZSE
  cal_date      DATE         日历日期
  is_open       SMALLINT     是否交易：0休市 1交易
  pretrade_date DATE         上一个交易日

运行模式：
  按日增量：每天跑一次，取当前日期~往后一个月
  幂等写入，按 (exchange, cal_date) 主键覆盖
"""

import sys
import os

sys.path.insert(0, "/home/ecs-user/.openclaw/workspace/claw-quant-data")

import pandas as pd
from collectors.base import BaseCollector


class TradeCalCollector(BaseCollector):
    """交易日历采集器"""

    table_name = "trade_cal"
    pk_columns = ["exchange", "cal_date"]
    API_NAME = "trade_cal"

    def fetch(self, **params) -> pd.DataFrame:
        """
        获取交易日历。

        参数：
          - exchange:    交易所（默认空=SSE）
          - start_date:  起始日期 YYYYMMDD
          - end_date:    截止日期 YYYYMMDD
        """
        fields = ["exchange", "cal_date", "is_open", "pretrade_date"]
        df = self.pro.trade_cal(**params, fields=",".join(fields))
        if df is None or df.empty:
            return pd.DataFrame(columns=fields)
        return df

    def store(self, df: pd.DataFrame) -> int:
        """
        trade_cal 的 pretrade_date 首行为 NaN，基类通用 store 处理不了，
        需要预处理掉 NaN 值再调父类。
        """
        # 对 pretrade_date 特殊处理：NaN → None
        if "pretrade_date" in df.columns:
            mask = df["pretrade_date"].isna()
            df.loc[mask, "pretrade_date"] = None
        return super().store(df)


# ──────────────────────────────────────────────
# 命令行入口
# ──────────────────────────────────────────────
if __name__ == "__main__":
    import argparse
    from datetime import datetime, timedelta

    parser = argparse.ArgumentParser(description="采集交易日历")
    parser.add_argument("--exchange", type=str, default="SSE", help="交易所")
    parser.add_argument("--start", type=str, help="起始日期 YYYYMMDD")
    parser.add_argument("--end", type=str, help="截止日期 YYYYMMDD")
    args = parser.parse_args()

    if not args.start:
        args.start = datetime.now().strftime("%Y%m%d")
    if not args.end:
        args.end = (datetime.now() + timedelta(days=31)).strftime("%Y%m%d")

    collector = TradeCalCollector()
    rows = collector.collect(exchange=args.exchange,
                             start_date=args.start,
                             end_date=args.end)
    print(f"\n🎯 合计入库 {rows} 行")
