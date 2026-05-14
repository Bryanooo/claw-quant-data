"""
股票基础信息采集器
接口：stock_basic（tushare pro）

运行模式：全量覆盖（TRUNCATE + INSERT），建议每日/每周跑一次
"""



import pandas as pd
import psycopg2
import psycopg2.extras
from collectors.base import BaseCollector, get_db_conn


class StockBasicCollector(BaseCollector):
    """股票基础信息采集器"""

    API_NAME = "stock_basic"
    table_name = "stock_basic"
    pk_columns = ["ts_code"]

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



