"""
=============================================================================
A股日线行情采集器
=============================================================================

接口：daily（tushare pro）
文档：https://tushare.pro/document/2?doc_id=27

描述：
  获取A股日线行情（未复权），停牌期间不提供数据。
  支持按日期批量取全市场，或按股票取历史。

权限要求：
  - 基础积分每分钟500次，每次最多6000条
  - 一次请求≈一只股票23年历史

输出字段：
  ts_code     VARCHAR(16)   TS股票代码（主键）
  trade_date  DATE          交易日期（主键）
  open        DECIMAL(16,4) 开盘价
  high        DECIMAL(16,4) 最高价
  low         DECIMAL(16,4) 最低价
  close       DECIMAL(16,4) 收盘价
  pre_close   DECIMAL(16,4) 昨收价（除权价）
  change      DECIMAL(16,4) 涨跌额
  pct_chg     DECIMAL(10,4) 涨跌幅（%）
  vol         DECIMAL(20,2) 成交量（手）
  amount      DECIMAL(20,4) 成交额（千元）

运行模式：
  盘后增量（每日16:00）：分组100只/组，取当日全市场
  历史补全：逐只股票取全部历史，每调用 sleep 100ms
"""

import sys, os
sys.path.insert(0, "/home/ecs-user/.openclaw/workspace/claw-quant-data")

import re
import time
import pandas as pd
import psycopg2
import psycopg2.extras
from datetime import datetime, timedelta
from collectors.base import BaseCollector, get_db_conn, safe_str, safe_float


class DailyCollector(BaseCollector):
    table_name = "daily"
    pk_columns = ["ts_code", "trade_date"]

    def _fix_date(self, val):
        if val is None:
            return None
        if isinstance(val, float) and (pd.isna(val) or str(val) == "nan"):
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
        df = self.pro.daily(**params)
        if df is None or df.empty:
            return pd.DataFrame(columns=["ts_code","trade_date","open","high","low","close","pre_close","change","pct_chg","vol","amount"])
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
                        "open": safe_float(r.get("open")),
                        "high": safe_float(r.get("high")),
                        "low": safe_float(r.get("low")),
                        "close": safe_float(r.get("close")),
                        "pre_close": safe_float(r.get("pre_close")),
                        "change": safe_float(r.get("change")),
                        "pct_chg": safe_float(r.get("pct_chg")),
                        "vol": safe_float(r.get("vol")),
                        "amount": safe_float(r.get("amount")),
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
        """按日期获取当日全市场行情（分组100只/组）"""
        total = 0
        from service.db import query
        stocks = query("SELECT ts_code FROM stock_basic WHERE list_status = 'L'")
        codes = [s["ts_code"] for s in stocks]

        for i in range(0, len(codes), 100):
            group = codes[i:i+100]
            code_str = ",".join(group)
            try:
                df = self.collect(ts_code=code_str, trade_date=trade_date)
                total += df
            except Exception as e:
                self.logger.warning(f"⚠️  组 {i//100} 失败: {e}")
            time.sleep(0.3)

        return total

    def collect_history_stock(self, ts_code: str, start_date: str = None, end_date: str = None) -> int:
        """获取单只股票全部历史日线"""
        params = {"ts_code": ts_code}
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date
        return self.collect(**params)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", type=str, choices=["today", "history_batch", "history_single"], default="today")
    parser.add_argument("--ts_code", type=str, default="")
    parser.add_argument("--trade_date", type=str, default="")
    args = parser.parse_args()

    c = DailyCollector()

    if args.mode == "today":
        td = args.trade_date or datetime.now().strftime("%Y%m%d")
        total = c.collect_by_date(td)
        print(f"\n🎯 {td} 日线: {total} 行")

    elif args.mode == "history_single":
        r = c.collect_history_stock(args.ts_code)
        print(f"\n🎯 {args.ts_code}: {r} 行")

    elif args.mode == "history_batch":
        from service.db import query
        stocks = query("SELECT ts_code FROM stock_basic WHERE list_status = 'L'")
        total = 0
        start = time.time()
        for i, s in enumerate(stocks):
            try:
                r = c.collect_history_stock(s["ts_code"])
                total += r
            except Exception as e:
                c.logger.warning(f"⚠️  {s['ts_code']}: {e}")
            time.sleep(0.1)  # 每调用一次 sleep 100ms
            if (i+1) % 500 == 0:
                elapsed = time.time() - start
                rate = total / elapsed if elapsed > 0 else 0
                eta = (len(stocks) - i - 1) * (elapsed / (i+1))
                print(f"  进度: {i+1}/{len(stocks)}, 累计 {total} 行, {rate:.0f}行/s, 预计剩余 {eta/60:.0f}m")
        elapsed = time.time() - start
        print(f"\n🎯 历史完成: {total} 行, 耗时 {elapsed/60:.1f}m")
