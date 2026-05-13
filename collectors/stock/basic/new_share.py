"""
=============================================================================
IPO新股列表采集器
=============================================================================

接口：new_share（tushare pro）
文档：https://tushare.pro/document/2?doc_id=123

描述：
  获取新股上市列表数据。

权限要求：
  - 最低积分：120
  - 单次最大 2000 条

输出字段：
  ts_code       VARCHAR(16)    TS股票代码（主键）
  sub_code      VARCHAR(16)    申购代码
  name          VARCHAR(32)    名称
  ipo_date      DATE           上网发行日期
  issue_date    DATE           上市日期
  amount        DECIMAL(20,2)  发行总量（万股）
  market_amount DECIMAL(20,2)  上网发行总量（万股）
  price         DECIMAL(10,2)  发行价格
  pe            DECIMAL(10,2)  市盈率
  limit_amount  DECIMAL(10,4)  个人申购上限（万股）
  funds         DECIMAL(16,2)  募集资金（亿元）
  ballot        DECIMAL(10,4)  中签率

运行模式：
  全量拉取：一次性拉取所有历史 IPO 数据
  按 ts_code 主键幂等写入
"""

import sys, os
sys.path.insert(0, "/home/ecs-user/.openclaw/workspace/claw-quant-data")

import pandas as pd
from collectors.base import BaseCollector


class NewShareCollector(BaseCollector):
    table_name = "new_share"
    pk_columns = ["ts_code"]

    def fetch(self, **params) -> pd.DataFrame:
        fields = [
            "ts_code","sub_code","name","ipo_date","issue_date","amount",
            "market_amount","price","pe","limit_amount","funds","ballot",
        ]
        df = self.pro.new_share(**params, fields=",".join(fields))
        if df is None or df.empty:
            return pd.DataFrame(columns=fields)
        return df


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", type=str, default="19900101")
    parser.add_argument("--end", type=str, default="20261231")
    args = parser.parse_args()

    c = NewShareCollector()
    rows = c.collect(start_date=args.start, end_date=args.end)
    print(f"🎯 {rows} 行")
