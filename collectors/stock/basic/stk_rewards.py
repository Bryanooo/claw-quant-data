"""
=============================================================================
管理层薪酬和持股采集器
=============================================================================

接口：stk_rewards（tushare pro）
文档：https://tushare.pro/document/2?doc_id=194

描述：
  获取上市公司管理层薪酬和持股数据。

权限要求：
  - 最低积分：2000
  - 5000积分以上频次较高

输出字段：
  ts_code     VARCHAR(16)   TS股票代码
  ann_date    DATE          公告日期
  end_date    DATE          截止日期（报告期）
  name        VARCHAR(32)   姓名
  title       VARCHAR(64)   职务
  reward      DECIMAL(16,2) 报酬
  hold_vol    DECIMAL(20,2) 持股数

运行模式：
  全量遍历 stock_basic 上市股票，逐只拉取
  按 (ts_code, name, ann_date) 主键幂等写入
"""

import sys, os
sys.path.insert(0, "/home/ecs-user/.openclaw/workspace/claw-quant-data")

import re
import pandas as pd
import psycopg2
import psycopg2.extras
from collectors.base import BaseCollector, get_db_conn, safe_str, safe_float


def _fix_date(val):
    """尝试将各种日期格式转为 YYYY-MM-DD，无效返回 None"""
    if val is None:
        return None
    if isinstance(val, float) and (pd.isna(val) or str(val) == "nan"):
        return None
    s = str(val).strip()
    if not s or s.lower() in ("nan", "nat", "none"):
        return None
    m = re.match(r"^(\d{4})(\d{2})$", s)
    if m:
        return f"{m.group(1)}-{m.group(2)}-01"
    m = re.match(r"^(\d{4})(\d{2})(\d{2})$", s)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    if re.match(r"^\d{4}-\d{2}-\d{2}$", s):
        return s
    return None


class StkRewardsCollector(BaseCollector):
    table_name = "stk_rewards"
    pk_columns = ["ts_code", "name", "ann_date"]

    def fetch(self, **params) -> pd.DataFrame:
        df = self.pro.stk_rewards(**params, fields="ts_code,ann_date,end_date,name,title,reward,hold_vol")
        if df is None or df.empty:
            return pd.DataFrame(columns=["ts_code","ann_date","end_date","name","title","reward","hold_vol"])
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
                    ann_date = _fix_date(r.get("ann_date"))
                    if ann_date is None:
                        continue
                    cleaned.append({
                        "ts_code": safe_str(r.get("ts_code")),
                        "ann_date": ann_date,
                        "end_date": _fix_date(r.get("end_date")),
                        "name": safe_str(r.get("name")),
                        "title": safe_str(r.get("title")),
                        "reward": safe_float(r.get("reward")),
                        "hold_vol": safe_float(r.get("hold_vol")),
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


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--ts_code", type=str, default="")
    args = parser.parse_args()

    c = StkRewardsCollector()
    if args.ts_code:
        rows = c.collect(ts_code=args.ts_code)
    else:
        from service.db import query
        stocks = query("SELECT ts_code FROM stock_basic WHERE list_status = 'L'")
        total = 0
        for i, s in enumerate(stocks):
            try:
                r = c.collect(ts_code=s["ts_code"])
                total += r
            except Exception:
                pass
            if (i+1) % 500 == 0:
                print(f"  进度: {i+1}/{len(stocks)}, 当前: {total} 行")
        print(f"🎯 合计 {total} 行")
