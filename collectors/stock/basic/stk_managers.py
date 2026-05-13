"""
=============================================================================
上市公司管理层采集器
=============================================================================

接口：stk_managers（tushare pro）
文档：https://tushare.pro/document/2?doc_id=193

描述：
  获取上市公司管理层信息，支持单个或多个股票代码输入。

权限要求：
  - 最低积分：2000

输出字段：
  ts_code     VARCHAR(16)  TS股票代码
  ann_date    DATE         公告日期
  name        VARCHAR(32)  姓名
  gender      VARCHAR(4)   性别
  lev         VARCHAR(32)  岗位类别
  title       VARCHAR(64)  岗位
  edu         VARCHAR(16)  学历
  national    VARCHAR(16)  国籍
  birthday    VARCHAR(16)  出生年月
  begin_date  DATE         上任日期
  end_date    DATE         离任日期
  resume      TEXT         个人简历

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
from collectors.base import BaseCollector, get_db_conn, safe_str


def _fix_date(val):
    """尝试将各种日期格式转为 YYYY-MM-DD，无效返回 None"""
    if val is None:
        return None
    if isinstance(val, float) and (pd.isna(val) or str(val) == "nan"):
        return None
    s = str(val).strip()
    if not s or s.lower() in ("nan", "nat", "none"):
        return None
    # YYYYMM → YYYY-MM-01
    m = re.match(r"^(\d{4})(\d{2})$", s)
    if m:
        return f"{m.group(1)}-{m.group(2)}-01"
    # YYYYMMDD → YYYY-MM-DD
    m = re.match(r"^(\d{4})(\d{2})(\d{2})$", s)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    # 已经是 YYYY-MM-DD
    if re.match(r"^\d{4}-\d{2}-\d{2}$", s):
        return s
    return None


class StkManagersCollector(BaseCollector):
    table_name = "stk_managers"
    pk_columns = ["ts_code", "name", "ann_date"]

    def fetch(self, **params) -> pd.DataFrame:
        df = self.pro.stk_managers(**params, fields="ts_code,ann_date,name,gender,lev,title,edu,national,birthday,begin_date,end_date,resume")
        if df is None or df.empty:
            return pd.DataFrame(columns=["ts_code","ann_date","name","gender","lev","title","edu","national","birthday","begin_date","end_date","resume"])
        return df

    def store(self, df: pd.DataFrame) -> int:
        conn = get_db_conn()
        try:
            with conn.cursor() as cur:
                rows = df.to_dict(orient="records")
                if not rows:
                    return 0

                # 清洗：修复日期格式
                cleaned = []
                for r in rows:
                    cleaned.append({
                        "ts_code": safe_str(r.get("ts_code")),
                        "ann_date": _fix_date(r.get("ann_date")),
                        "name": safe_str(r.get("name")),
                        "gender": safe_str(r.get("gender")),
                        "lev": safe_str(r.get("lev")),
                        "title": safe_str(r.get("title")),
                        "edu": safe_str(r.get("edu")),
                        "national": safe_str(r.get("national")),
                        "birthday": safe_str(r.get("birthday")),
                        "begin_date": _fix_date(r.get("begin_date")),
                        "end_date": _fix_date(r.get("end_date")),
                        "resume": safe_str(r.get("resume")),
                    })
                # 过滤掉 ann_date 为 None 的行（主键不能为空）
                cleaned = [r for r in cleaned if r["ann_date"] is not None]
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

    c = StkManagersCollector()
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
                print(f"  进度: {i+1}/{len(stocks)}, 当前累计: {total} 行")
        print(f"🎯 合计 {total} 行")
