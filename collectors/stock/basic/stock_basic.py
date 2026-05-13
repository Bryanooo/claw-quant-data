"""
=============================================================================
股票基础信息采集器
=============================================================================

接口：stock_basic（tushare pro）
文档：https://tushare.pro/document/2?doc_id=25

描述：
  获取沪深全量股票的基础信息，包括代码、名称、行业、上市日期、实控人等。

权限要求：
  - 最低积分：2000
  - 单次最大 6000 行（全市场一次足够）

输出表字段：
  ts_code      VARCHAR(16)   TS代码（主键）
  symbol       VARCHAR(8)    纯数字代码
  name         VARCHAR(32)   股票名称
  area         VARCHAR(32)   地域
  industry     VARCHAR(64)   所属行业
  fullname     VARCHAR(128)  股票全称
  enname       VARCHAR(128)  英文全称
  cnspell      VARCHAR(16)   拼音缩写
  market       VARCHAR(16)   市场类型
  exchange     VARCHAR(8)    交易所代码
  curr_type    VARCHAR(8)    交易货币
  list_status  VARCHAR(4)    上市状态
  list_date    VARCHAR(16)   上市日期
  delist_date  VARCHAR(16)   退市日期
  is_hs        VARCHAR(4)    沪深港通标的
  act_name     VARCHAR(64)   实控人名称
  act_ent_type VARCHAR(64)   实控人企业性质

运行模式：
  全量覆盖（TRUNCATE + INSERT），建议每日/每周跑一次
"""

import sys
import os

sys.path.insert(0, "/home/ecs-user/.openclaw/workspace/claw-quant-data")

import pandas as pd
import psycopg2
import psycopg2.extras
from collectors.base import BaseCollector, get_db_conn


class StockBasicCollector(BaseCollector):
    """股票基础信息采集器"""

    table_name = "stock_basic"
    pk_columns = ["ts_code"]
    API_NAME = "stock_basic"

    def fetch(self, **params) -> pd.DataFrame:
        """
        获取全量股票基础信息。
        默认取全部 L 上市股票。
        """
        fields = [
            "ts_code", "symbol", "name", "area", "industry",
            "fullname", "enname", "cnspell", "market", "exchange",
            "curr_type", "list_status", "list_date", "delist_date",
            "is_hs", "act_name", "act_ent_type",
        ]
        df = self.pro.stock_basic(**params, fields=",".join(fields))
        if df is None or df.empty:
            return pd.DataFrame(columns=fields)
        return df

    def store(self, df: pd.DataFrame) -> int:
        """
        全量覆盖模式：先 TRUNCATE 再 INSERT。
        基础信息表是全量快照，增量更新无意义。
        """
        conn = get_db_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(f"TRUNCATE TABLE {self.table_name}")

                rows = df.to_dict(orient="records")
                if not rows:
                    return 0

                columns = list(rows[0].keys())
                placeholders = ",".join(["%s"] * len(columns))
                col_names = ",".join(columns)

                insert_sql = (
                    f"INSERT INTO {self.table_name} ({col_names}) "
                    f"VALUES ({placeholders})"
                )
                values = [[r.get(c) for c in columns] for r in rows]
                psycopg2.extras.execute_batch(cur, insert_sql, values)

            conn.commit()
            return len(rows)
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()


# ──────────────────────────────────────────────
# 命令行入口
# ──────────────────────────────────────────────
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="采集股票基础信息")
    parser.add_argument("--list_status", type=str, default="L",
                        help="上市状态 L上市 D退市 (默认 L)")
    parser.add_argument("--exchange", type=str, default="",
                        help="交易所 SSE/SZSE/BSE (默认空=全部)")
    args = parser.parse_args()

    collector = StockBasicCollector()
    rows = collector.collect(list_status=args.list_status, exchange=args.exchange)
    print(f"\n🎯 合计入库 {rows} 行")
