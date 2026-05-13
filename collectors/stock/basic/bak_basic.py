"""
=============================================================================
股票历史列表（每日）采集器
=============================================================================

接口：bak_basic（tushare pro）
文档：https://tushare.pro/document/2?doc_id=262

描述：
  获取每日股票的备用基础列表，含行业、PE、股本、财务比率等。
  数据从 2016 年开始。

权限要求：
  - 正式权限需要 5000 积分
  - 单次最大 7000 条

输出字段：
  trade_date          DATE          交易日期（主键）
  ts_code             VARCHAR(16)   TS股票代码（主键）
  name                VARCHAR(32)   股票名称
  industry            VARCHAR(64)   行业
  area                VARCHAR(32)   地域
  pe                  DECIMAL(16,4) 市盈率（动）
  float_share         DECIMAL(20,4) 流通股本（亿）
  total_share         DECIMAL(20,4) 总股本（亿）
  total_assets        DECIMAL(20,4) 总资产（亿）
  liquid_assets       DECIMAL(20,4) 流动资产（亿）
  fixed_assets        DECIMAL(20,4) 固定资产（亿）
  reserved            DECIMAL(20,4) 公积金
  reserved_pershare   DECIMAL(16,4) 每股公积金
  eps                 DECIMAL(16,4) 每股收益
  bvps                DECIMAL(16,4) 每股净资产
  pb                  DECIMAL(16,4) 市净率
  list_date           DATE          上市日期
  undp                DECIMAL(20,4) 未分配利润
  per_undp            DECIMAL(16,4) 每股未分配利润
  rev_yoy             DECIMAL(10,2) 收入同比（%）
  profit_yoy          DECIMAL(10,2) 利润同比（%）
  gpr                 DECIMAL(10,2) 毛利率（%）
  npr                 DECIMAL(10,2) 净利润率（%）
  holder_num          INTEGER       股东人数

运行模式：
  按日增量：每天盘后取当日数据
  按 (trade_date, ts_code) 主键幂等写入
"""

import sys, os
sys.path.insert(0, "/home/ecs-user/.openclaw/workspace/claw-quant-data")

import re
import pandas as pd
import psycopg2
import psycopg2.extras
from collectors.base import BaseCollector, get_db_conn, safe_str, safe_float, safe_int


def _fix_date(val):
    """尝试将各种日期转 YYYY-MM-DD，无效返回 None"""
    if val is None:
        return None
    if isinstance(val, float) and (pd.isna(val) or str(val) == "nan"):
        return None
    s = str(val).strip()
    if not s or s.lower() in ("nan", "nat", "none", "0", ""):
        return None
    m = re.match(r"^(\d{4})(\d{2})(\d{2})$", s)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    if re.match(r"^\d{4}-\d{2}-\d{2}$", s):
        return s
    return None


class BakBasicCollector(BaseCollector):
    table_name = "bak_basic"
    pk_columns = ["trade_date", "ts_code"]

    def fetch(self, **params) -> pd.DataFrame:
        fields = [
            "trade_date","ts_code","name","industry","area","pe",
            "float_share","total_share","total_assets","liquid_assets","fixed_assets",
            "reserved","reserved_pershare","eps","bvps","pb","list_date",
            "undp","per_undp","rev_yoy","profit_yoy","gpr","npr","holder_num",
        ]
        df = self.pro.bak_basic(**params, fields=",".join(fields))
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
                    trade_date = _fix_date(r.get("trade_date"))
                    if trade_date is None:
                        continue
                    cleaned.append({
                        "trade_date": trade_date,
                        "ts_code": safe_str(r.get("ts_code")),
                        "name": safe_str(r.get("name")),
                        "industry": safe_str(r.get("industry")),
                        "area": safe_str(r.get("area")),
                        "pe": safe_float(r.get("pe")),
                        "float_share": safe_float(r.get("float_share")),
                        "total_share": safe_float(r.get("total_share")),
                        "total_assets": safe_float(r.get("total_assets")),
                        "liquid_assets": safe_float(r.get("liquid_assets")),
                        "fixed_assets": safe_float(r.get("fixed_assets")),
                        "reserved": safe_float(r.get("reserved")),
                        "reserved_pershare": safe_float(r.get("reserved_pershare")),
                        "eps": safe_float(r.get("eps")),
                        "bvps": safe_float(r.get("bvps")),
                        "pb": safe_float(r.get("pb")),
                        "list_date": _fix_date(r.get("list_date")),
                        "undp": safe_float(r.get("undp")),
                        "per_undp": safe_float(r.get("per_undp")),
                        "rev_yoy": safe_float(r.get("rev_yoy")),
                        "profit_yoy": safe_float(r.get("profit_yoy")),
                        "gpr": safe_float(r.get("gpr")),
                        "npr": safe_float(r.get("npr")),
                        "holder_num": safe_int(r.get("holder_num")),
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
    from datetime import datetime
    parser = argparse.ArgumentParser()
    parser.add_argument("--trade_date", type=str, default=datetime.now().strftime("%Y%m%d"))
    args = parser.parse_args()

    c = BakBasicCollector()
    rows = c.collect(trade_date=args.trade_date)
    print(f"\n🎯 合计入库 {rows} 行")
