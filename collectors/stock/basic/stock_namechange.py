"""
=============================================================================
股票曾用名采集器
=============================================================================

接口：namechange（tushare pro）
文档：https://tushare.pro/document/2?doc_id=100

描述：
  历史名称变更记录。输入股票代码可获取该股票的全部曾用名历史。

输出字段：
  ts_code       VARCHAR(16)  TS代码
  name          VARCHAR(32)  证券名称
  start_date    DATE         开始日期
  end_date      DATE         结束日期（None=至今）
  ann_date      DATE         公告日期
  change_reason VARCHAR(128) 变更原因

运行模式：
  全量拉取：遍历 stock_basic 中所有 ts_code，逐只拉取
  幂等写入，按 (ts_code, start_date) 主键覆盖
"""

import sys, os
sys.path.insert(0, "/home/ecs-user/.openclaw/workspace/claw-quant-data")

import pandas as pd
from collectors.base import BaseCollector


class NameChangeCollector(BaseCollector):
    table_name = "namechange"
    pk_columns = ["ts_code", "start_date"]

    def fetch(self, **params) -> pd.DataFrame:
        df = self.pro.namechange(**params, fields="ts_code,name,start_date,end_date,ann_date,change_reason")
        if df is None or df.empty:
            return pd.DataFrame(columns=["ts_code", "name", "start_date", "end_date", "ann_date", "change_reason"])
        return df


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--ts_code", type=str, default="", help="指定股票代码，不传=取全部")
    args = parser.parse_args()

    c = NameChangeCollector()
    if args.ts_code:
        rows = c.collect(ts_code=args.ts_code)
    else:
        # 全量遍历
        from service.db import query
        stocks = query("SELECT ts_code FROM stock_basic WHERE list_status = 'L'")
        total = 0
        for i, s in enumerate(stocks):
            try:
                r = c.collect(ts_code=s["ts_code"])
                total += r
            except Exception as e:
                print(f"  ⚠️  {s['ts_code']}: {e}")
            if (i+1) % 500 == 0:
                print(f"  进度: {i+1}/{len(stocks)}")
        print(f"🎯 合计 {total} 行")
