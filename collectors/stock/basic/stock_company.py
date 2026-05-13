"""
=============================================================================
上市公司基本信息采集器
=============================================================================

接口：stock_company（tushare pro）
文档：https://tushare.pro/document/2?doc_id=112

描述：
  获取上市公司基础信息，包括法人代表、总经理、董秘、注册资本、
  员工人数、公司介绍等。

权限要求：
  - 最低积分：120
  - 单次最大 4500 行，可按交易所分批提取

输出字段：
  ts_code        VARCHAR(16)   股票代码（主键）
  com_name       VARCHAR(128)  公司全称
  com_id         VARCHAR(32)   统一社会信用代码
  exchange       VARCHAR(8)    交易所代码
  chairman       VARCHAR(32)   法人代表
  manager        VARCHAR(32)   总经理
  secretary      VARCHAR(32)   董秘
  reg_capital    DECIMAL(20,2) 注册资本(万元)
  setup_date     DATE          注册日期
  province       VARCHAR(32)   所在省份
  city           VARCHAR(32)   所在城市
  introduction   TEXT          公司介绍
  website        VARCHAR(256)  公司主页
  email          VARCHAR(128)  电子邮件
  office         VARCHAR(256)  办公室
  employees      INTEGER       员工人数
  main_business  TEXT          主要业务及产品
  business_scope TEXT          经营范围

运行模式：
  全量拉取：按交易所分批（SSE / SZSE / BSE）
  按 ts_code 主键幂等写入
"""

import sys, os
sys.path.insert(0, "/home/ecs-user/.openclaw/workspace/claw-quant-data")

import pandas as pd
from collectors.base import BaseCollector


class StockCompanyCollector(BaseCollector):
    table_name = "stock_company"
    pk_columns = ["ts_code"]

    def fetch(self, **params) -> pd.DataFrame:
        fields = [
            "ts_code", "com_name", "com_id", "exchange", "chairman", "manager",
            "secretary", "reg_capital", "setup_date", "province", "city",
            "introduction", "website", "email", "office", "employees",
            "main_business", "business_scope",
        ]
        df = self.pro.stock_company(**params, fields=",".join(fields))
        if df is None or df.empty:
            return pd.DataFrame(columns=fields)
        return df


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--exchange", type=str, default="", help="SSE/SZSE/BSE，不传=全部")
    args = parser.parse_args()

    c = StockCompanyCollector()
    if args.exchange:
        rows = c.collect(exchange=args.exchange)
    else:
        total = 0
        for ex in ["SSE", "SZSE", "BSE"]:
            try:
                r = c.collect(exchange=ex)
                total += r
                print(f"  {ex}: {r} 行")
            except Exception as e:
                print(f"  {ex}: ❌ {e}")
        print(f"🎯 合计 {total} 行")
