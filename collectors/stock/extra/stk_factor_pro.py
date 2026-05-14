"""
股票技术面因子（专业版）采集器（stk_factor_pro）
采集策略：按股票逐个拉（只补2026年）

注意：该接口返回261列（含200+技术指标），表必须建全量列。
使用自定义 store 处理 numpy 类型和空值，基类通用 store 也能处理。
"""

import time
import logging
from datetime import datetime, timedelta
from collectors.base import BaseCollector, get_db_conn

logger = logging.getLogger("collector.stk_factor_pro")

_PK = ["ts_code", "trade_date"]


class StkFactorProCollector(BaseCollector):
    API_NAME = "stk_factor_pro"
    table_name = "stk_factor_pro"
    pk_columns = ["ts_code", "trade_date"]

    def _clean_val(self, v):
        """统一处理空值和numpy类型"""
        import numpy as np
        if v is None:
            return None
        if isinstance(v, float) and (np.isnan(v) or np.isinf(v)):
            return None
        if isinstance(v, np.integer):
            return int(v)
        if isinstance(v, np.floating):
            return float(v)
        if isinstance(v, np.bool_):
            return bool(v)
        if isinstance(v, list):
            return ",".join(str(x) for x in v)
        if isinstance(v, dict):
            return str(v)
        if hasattr(v, 'dtype'):
            return None
        return v

    def store(self, df):
        """批量upsert（基类通用 store 的 _is_nan 对 numpy 类型也兼容，但保留自定义以处理 numpy 特殊类型）"""
        if df is None or len(df) == 0:
            return 0
        df = df.copy()
        conn = get_db_conn()
        try:
            ac = list(df.columns)
            cs = ",".join(ac)
            ph = ",".join(["%s"] * len(ac))
            upk = ", ".join(self.pk_columns)
            dc = [c for c in ac if c not in self.pk_columns]
            upd = ", ".join(f"{c}=EXCLUDED.{c}" for c in dc)
            sql = f"INSERT INTO {self.table_name} ({cs}) VALUES ({ph}) ON CONFLICT ({upk}) DO UPDATE SET {upd}"
            with conn.cursor() as cur:
                import psycopg2.extras as pg_extras
                rows = []
                for _, r in df.iterrows():
                    rows.append(tuple(self._clean_val(r[c]) for c in ac))
                pg_extras.execute_batch(cur, sql, rows)
            conn.commit()
            return len(df)
        except Exception as e:
            conn.rollback()
            logger.error(f"_store 错误: {e}")
            return 0
        finally:
            conn.close()

    def collect_all_history(self, start_date="20260101", end_date="20260513"):
        """采集全量历史数据（逐个股票拉2026年数据）"""
        conn = get_db_conn()
        cur = conn.cursor()
        cur.execute("SELECT ts_code FROM stock_basic")
        codes = [r[0] for r in cur.fetchall()]
        cur.close()
        conn.close()

        total = 0
        for i, code in enumerate(codes):
            try:
                df = self.fetch(ts_code=code, start_date=start_date, end_date=end_date)
                if df is not None and len(df) > 0:
                    total += self.store(df)
            except Exception as e:
                logger.warning(f"  [{i+1}/{len(codes)}] {code}: {e}")
            if (i + 1) % 200 == 0:
                logger.info(f"  [{i+1}/{len(codes)}] {total}行")
        logger.info(f"✅ stk_factor_pro: 历史补齐 {total} 行")
        return total
