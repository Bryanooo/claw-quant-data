"""
前十大股东采集器
接口：top10_holders
采集策略：逐个股票按报告期拉
"""

import sys, os
sys.path.insert(0, "/home/ecs-user/.openclaw/workspace/claw-quant-data")

import re
import time
import pandas as pd
import psycopg2
import psycopg2.extras
from collectors.base import BaseCollector, get_db_conn, safe_str, safe_float


class Top10HoldersCollector(BaseCollector):
    table_name = "top10_holders"
    pk_columns = ["ts_code", "end_date", "holder_name"]
    API_NAME = "top10_holders"

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
            "ts_code", "ann_date", "end_date", "holder_name",
            "hold_amount", "hold_ratio", "hold_float_ratio",
            "hold_change", "holder_type",
        ]
        df = self.pro.top10_holders(**params, fields=",".join(fields))
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
                    hn = safe_str(r.get("holder_name"))
                    if ed is None or hn is None:
                        continue
                    cleaned.append({
                        "ts_code": safe_str(r.get("ts_code")),
                        "ann_date": self._fix_date(r.get("ann_date")),
                        "end_date": ed,
                        "holder_name": hn,
                        "hold_amount": safe_float(r.get("hold_amount")),
                        "hold_ratio": safe_float(r.get("hold_ratio")),
                        "hold_float_ratio": safe_float(r.get("hold_float_ratio")),
                        "hold_change": safe_float(r.get("hold_change")),
                        "holder_type": safe_str(r.get("holder_type")),
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

    def collect_by_stock(self, ts_code: str, start_date: str = "", end_date: str = "") -> int:
        params = {"ts_code": ts_code}
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date
        return self.collect(**params)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--ts_code", type=str, default="", help="股票代码")
    parser.add_argument("--start_date", type=str, default="", help="开始日期")
    parser.add_argument("--end_date", type=str, default="", help="结束日期")
    args = parser.parse_args()
    c = Top10HoldersCollector()
    r = c.collect_by_stock(args.ts_code, args.start_date, args.end_date)
    print(f"\n🎯 {args.ts_code}: {r} 行")
