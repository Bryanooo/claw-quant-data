"""
股权质押统计采集器
接口：pledge_stat
采集策略：逐个股票拉
"""

import sys, os
sys.path.insert(0, "/home/ecs-user/.openclaw/workspace/claw-quant-data")

import re
import pandas as pd
import psycopg2
import psycopg2.extras
from collectors.base import BaseCollector, get_db_conn, safe_str, safe_float, safe_int


class PledgeStatCollector(BaseCollector):
    table_name = "pledge_stat"
    pk_columns = ["ts_code", "end_date"]
    API_NAME = "pledge_stat"

    def _fix_date(self, val):
        if val is None:
            return None
        s = str(val).strip()
        if not s or s.lower() in ("nan", "nat", "none"):
            return None
        m = re.match(r"^(\d{4})(\d{2})(\d{2})$", s)
        if m:
            return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
        if re.match(r"^\d{4}-\d{2}-\d{2}$", s):
            return s
        return None

    def fetch(self, **params) -> pd.DataFrame:
        fields = [
            "ts_code", "end_date", "pledge_count", "unrest_pledge",
            "rest_pledge", "total_share", "pledge_ratio",
        ]
        df = self.pro.pledge_stat(**params, fields=",".join(fields))
        if df is None or df.empty:
            return pd.DataFrame(columns=fields)
        return df

    def store(self, df: pd.DataFrame) -> int:
        conn = get_db_conn()
        try:
            with conn.cursor() as cur:
                rows = df.to_dict(orient="records")
                if not rows:
                    return 0
                cleaned = []
                for r in rows:
                    ed = self._fix_date(r.get("end_date"))
                    if ed is None:
                        continue
                    cleaned.append({
                        "ts_code": safe_str(r.get("ts_code")),
                        "end_date": ed,
                        "pledge_count": safe_int(r.get("pledge_count")),
                        "unrest_pledge": safe_float(r.get("unrest_pledge")),
                        "rest_pledge": safe_float(r.get("rest_pledge")),
                        "total_share": safe_float(r.get("total_share")),
                        "pledge_ratio": safe_float(r.get("pledge_ratio")),
                    })
                if not cleaned:
                    return 0
                columns = list(cleaned[0].keys())
                ph = ",".join(["%s"] * len(columns))
                col_names = ",".join(columns)
                update_set = ", ".join(
                    [f"{c} = EXCLUDED.{c}" for c in columns if c not in self.pk_columns]
                )
                insert_sql = (
                    f"INSERT INTO {self.table_name} ({col_names}) "
                    f"VALUES ({ph}) ON CONFLICT ({', '.join(self.pk_columns)}) "
                    f"DO UPDATE SET {update_set}"
                )
                vals = [tuple(r[c] for c in columns) for r in cleaned]
                psycopg2.extras.execute_batch(cur, insert_sql, vals)
            conn.commit()
            return len(cleaned)
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    def collect_by_stock(self, ts_code: str) -> int:
        return self.collect(ts_code=ts_code)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--ts_code", type=str, default="", help="股票代码")
    args = parser.parse_args()
    c = PledgeStatCollector()
    r = c.collect_by_stock(args.ts_code)
    print(f"\n🎯 {args.ts_code}: {r} 行")
