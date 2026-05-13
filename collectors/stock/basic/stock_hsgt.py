"""
=============================================================================
沪深港通股票列表采集器
=============================================================================

接口：stock_hsgt（tushare pro）
文档：https://tushare.pro/document/2?doc_id=398

描述：
  获取沪深港通股票列表，数据从 2025-08-12 开始。

权限要求：
  - 最低积分：3000
  - 单次最大 2000 行
  - 每天上午 9:20 更新

输出字段：
  ts_code     VARCHAR(16)  股票代码
  trade_date  DATE         交易日期
  type        VARCHAR(8)   类型（HK_SZ / SZ_HK / HK_SH / SH_HK）
  name        VARCHAR(64)  股票名称
  type_name   VARCHAR(32)  类型名称

运行模式：
  按日增量：每天盘前取当日数据
  按 (ts_code, trade_date, type) 主键幂等写入
"""

import sys, os
sys.path.insert(0, "/home/ecs-user/.openclaw/workspace/claw-quant-data")

import pandas as pd
from collectors.base import BaseCollector


class StockHsgtCollector(BaseCollector):
    table_name = "stock_hsgt"
    pk_columns = ["ts_code", "trade_date", "type"]

    def fetch(self, **params) -> pd.DataFrame:
        df = self.pro.stock_hsgt(**params, fields="ts_code,trade_date,type,name,type_name")
        if df is None or df.empty:
            return pd.DataFrame(columns=["ts_code","trade_date","type","name","type_name"])
        return df


if __name__ == "__main__":
    import argparse
    from datetime import datetime
    parser = argparse.ArgumentParser()
    parser.add_argument("--trade_date", type=str, default=datetime.now().strftime("%Y%m%d"))
    parser.add_argument("--type", type=str, default="HK_SZ", help="HK_SZ/SZ_HK/HK_SH/SH_HK")
    args = parser.parse_args()

    c = StockHsgtCollector()
    # 四种类型各取一次
    types = [args.type] if args.type else ["HK_SZ", "SZ_HK", "HK_SH", "SH_HK"]
    total = 0
    for t in types:
        try:
            r = c.collect(trade_date=args.trade_date, type=t)
            print(f"  {t}: {r} 行")
            total += r
        except Exception as e:
            print(f"  {t}: ❌ {e}")
    print(f"\n🎯 合计 {total} 行")
