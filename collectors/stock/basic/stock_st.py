"""
ST股票列表采集器（含风险警示板明细）
接口：
  - stock_st  → ST股票列表（3000积分，每天9:20更新）
  - st        → ST风险警示板明细（6000积分）

两步走：
1. 每日调 stock_st 获取当日所有ST股票列表
2. 对列表中的每只股票，调 st 接口获取详细的变更原因

注意：此采集器的 fetch 方法做了两个 API 的合并，store 也因此保留了自定义逻辑。
"""

import time
import pandas as pd
import psycopg2
import psycopg2.extras
from collectors.base import BaseCollector, get_db_conn, safe_str


class StockSTCollector(BaseCollector):
    API_NAME = "stock_st"  # 仅用于标识，实际 fetch 也会调 st 接口
    table_name = "stock_st"
    pk_columns = ["ts_code", "trade_date"]

    # ── step 1: 获取当日ST列表 ──
    def fetch_stock_st(self, trade_date: str) -> pd.DataFrame:
        """调 stock_st 接口获取当日ST股票列表"""
        df = self.pro.stock_st(
            trade_date=trade_date,
            fields="ts_code,name,trade_date,type,type_name"
        )
        if df is None or df.empty:
            return pd.DataFrame(columns=["ts_code", "name", "trade_date", "type", "type_name"])
        return df

    # ── step 2: 获取单只股票的风险警示明细 ──
    def fetch_st_detail(self, ts_code: str) -> list[dict]:
        """调 st 接口获取某只股票的ST警示板明细"""
        try:
            df = self.pro.st(
                ts_code=ts_code,
                fields="ts_code,name,pub_date,imp_date,st_tpye,st_reason,st_explain"
            )
            if df is None or df.empty:
                return []
            return df.to_dict(orient="records")
        except Exception as e:
            self.logger.warning(f"  ⚠️  {ts_code} st明细获取失败: {e}")
            return []

    # ── 采集入口 ──
    def fetch(self, **params) -> pd.DataFrame:
        """
        参数：
          - trade_date: 交易日期 YYYYMMDD
        """
        trade_date = params.get("trade_date", "")
        if not trade_date:
            raise ValueError("必须指定 trade_date")

        # step 1: 获取ST列表
        self.logger.info(f"📋 step1: 获取 {trade_date} ST列表...")
        list_df = self.fetch_stock_st(trade_date)
        if list_df.empty:
            return list_df

        stocks = list_df.to_dict(orient="records")
        self.logger.info(f"  共 {len(stocks)} 只ST标的")

        # step 2: 逐只获取明细
        self.logger.info(f"🔍 step2: 逐只获取风险警示明细...")
        detail_map = {}
        for i, s in enumerate(stocks):
            code = s["ts_code"]
            details = self.fetch_st_detail(code)
            if details:
                sorted_d = sorted(details, key=lambda x: x.get("imp_date", "") or "", reverse=True)
                detail_map[code] = sorted_d[0]
            if (i + 1) % 50 == 0:
                self.logger.info(f"  明细进度: {i+1}/{len(stocks)}")
                time.sleep(0.5)

        # step 3: 合并数据
        merged = []
        for s in stocks:
            code = s["ts_code"]
            row = {
                "ts_code": code,
                "name": s.get("name"),
                "trade_date": s.get("trade_date"),
                "type": s.get("type"),
                "type_name": s.get("type_name"),
                "pub_date": None,
                "imp_date": None,
                "st_type": None,
                "st_reason": None,
                "st_explain": None,
            }
            if code in detail_map:
                d = detail_map[code]
                row["pub_date"] = safe_str(d.get("pub_date"))
                row["imp_date"] = safe_str(d.get("imp_date"))
                row["st_type"] = safe_str(d.get("st_tpye"))
                row["st_reason"] = safe_str(d.get("st_reason"))
                row["st_explain"] = safe_str(d.get("st_explain"))
            merged.append(row)

        return pd.DataFrame(merged)

    def store(self, df: pd.DataFrame) -> int:
        """自定义 store：合并了 stock_st 和 st 两个接口的数据"""
        conn = get_db_conn()
        try:
            with conn.cursor() as cur:
                rows = df.to_dict(orient="records")
                if not rows:
                    return 0

                insert_sql = """
                    INSERT INTO stock_st (ts_code, name, trade_date, type, type_name,
                                          pub_date, imp_date, st_type, st_reason, st_explain)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT (ts_code, trade_date) DO UPDATE
                    SET name = EXCLUDED.name,
                        type = EXCLUDED.type,
                        type_name = EXCLUDED.type_name,
                        pub_date = EXCLUDED.pub_date,
                        imp_date = EXCLUDED.imp_date,
                        st_type = EXCLUDED.st_type,
                        st_reason = EXCLUDED.st_reason,
                        st_explain = EXCLUDED.st_explain
                """

                vals = [tuple(r.get(c) for c in [
                    "ts_code", "name", "trade_date", "type", "type_name",
                    "pub_date", "imp_date", "st_type", "st_reason", "st_explain"
                ]) for r in rows]

                psycopg2.extras.execute_batch(cur, insert_sql, vals)

            conn.commit()
            return len(rows)
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()



