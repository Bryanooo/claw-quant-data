"""
个股异常波动采集器
接口：stk_shock
"""

import sys, os
sys.path.insert(0, "/home/ecs-user/.openclaw/workspace/claw-quant-data")

import re
import pandas as pd
import psycopg2
import psycopg2.extras
from collectors.base import BaseCollector, get_db_conn, safe_str


class StkShockCollector(BaseCollector):
    table_name = "stk_shock"
    pk_columns = ["ts_code", "trade_date"]
    API_NAME = "stk_shock"

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
        fields = ["ts_code", "trade_date", "name", "trade_market", "reason", "period"]
        df = self.pro.stk_shock(**params, fields=",".join(fields))
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
                    td = self._fix_date(r.get("trade_date"))
                    if td is None:
                        continue
                    cleaned.append({
                        "ts_code": safe_str(r.get("ts_code")),
                        "trade_date": td,
                        "name": safe_str(r.get("name")),
                        "trade_market": safe_str(r.get("trade_market")),
                        "reason": safe_str(r.get("reason")),
                        "period": safe_str(r.get("period")),
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

    def collect_by_date(self, trade_date: str) -> int:
        return self.collect(trade_date=trade_date)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--trade_date", type=str, default="", help="交易日期 YYYYMMDD")
    args = parser.parse_args()
    c = StkShockCollector()
    r = c.collect_by_date(args.trade_date)
    print(f"\n🎯 {args.trade_date}: {r} 行")
