"""
股票回购采集器
接口：repurchase
采集策略：按公告日期分页拉
"""

import sys, os
sys.path.insert(0, "/home/ecs-user/.openclaw/workspace/claw-quant-data")

import re
import pandas as pd
import psycopg2
import psycopg2.extras
from collectors.base import BaseCollector, get_db_conn, safe_str, safe_float


class RepurchaseCollector(BaseCollector):
    table_name = "repurchase"
    pk_columns = ["ts_code", "ann_date"]
    API_NAME = "repurchase"

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
            "ts_code", "ann_date", "end_date", "proc", "exp_date",
            "vol", "amount", "high_limit", "low_limit",
        ]
        df = self.pro.repurchase(**params, fields=",".join(fields))
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
                    ad = self._fix_date(r.get("ann_date"))
                    tc = safe_str(r.get("ts_code"))
                    if ad is None or tc is None:
                        continue
                    cleaned.append({
                        "ts_code": tc,
                        "ann_date": ad,
                        "end_date": self._fix_date(r.get("end_date")),
                        "proc": safe_float(r.get("proc")),
                        "exp_date": self._fix_date(r.get("exp_date")),
                        "vol": safe_float(r.get("vol")),
                        "amount": safe_float(r.get("amount")),
                        "high_limit": safe_float(r.get("high_limit")),
                        "low_limit": safe_float(r.get("low_limit")),
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

    def collect_by_date(self, start_date: str, end_date: str = "") -> int:
        params = {"start_date": start_date}
        if end_date:
            params["end_date"] = end_date
        return self.collect(**params)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--start_date", type=str, required=True, help="开始日期 YYYYMMDD")
    parser.add_argument("--end_date", type=str, default="", help="结束日期 YYYYMMDD")
    args = parser.parse_args()
    c = RepurchaseCollector()
    r = c.collect_by_date(args.start_date, args.end_date)
    print(f"\n🎯 {args.start_date}~{args.end_date}: {r} 行")
