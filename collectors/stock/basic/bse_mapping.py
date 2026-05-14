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

import pandas as pd
import psycopg2
import psycopg2.extras
from collectors.base import BaseCollector, get_db_conn


class BseMappingCollector(BaseCollector):
    API_NAME = "bse_mapping"
    table_name = "bse_mapping"
    pk_columns = ["o_code"]

    def store(self, df: pd.DataFrame) -> int:
        """
        全量覆盖模式：先 TRUNCATE 再 INSERT。
        基类通用 UPSERT 虽然也能用，但 TRUNCATE+INSERT 性能更好且适合全量快照。
        """
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



