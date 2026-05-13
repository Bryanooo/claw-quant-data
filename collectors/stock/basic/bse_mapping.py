"""
=============================================================================
北交所新旧代码对照采集器
=============================================================================

接口：bse_mapping（tushare pro）
文档：https://tushare.pro/document/2?doc_id=375

描述：北交所股票代码变更后新旧代码映射表，总量约 300 条。
权限：120积分，单次最大1000条

运行模式：全量拉取，TRUNCATE+INSERT覆盖
"""

import sys, os
sys.path.insert(0, "/home/ecs-user/.openclaw/workspace/claw-quant-data")

import pandas as pd
import psycopg2
import psycopg2.extras
from collectors.base import BaseCollector, get_db_conn


class BseMappingCollector(BaseCollector):
    table_name = "bse_mapping"
    pk_columns = ["o_code"]

    def fetch(self, **params) -> pd.DataFrame:
        df = self.pro.bse_mapping(**params, fields="name,o_code,n_code,list_date")
        if df is None or df.empty:
            return pd.DataFrame(columns=["name", "o_code", "n_code", "list_date"])
        return df

    def store(self, df: pd.DataFrame) -> int:
        conn = get_db_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(f"TRUNCATE TABLE {self.table_name}")
                rows = df.to_dict(orient="records")
                if not rows:
                    return 0
                columns = list(rows[0].keys())
                ph = ",".join(["%s"] * len(columns))
                sql = f"INSERT INTO {self.table_name} ({','.join(columns)}) VALUES ({ph})"
                vals = [[r.get(c) for c in columns] for r in rows]
                psycopg2.extras.execute_batch(cur, sql, vals)
            conn.commit()
            return len(rows)
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()


if __name__ == "__main__":
    c = BseMappingCollector()
    rows = c.collect()
    print(f"🎯 {rows} 行")
