"""
=============================================================================
claw-quant-v2 采集基类
=============================================================================

职责：
  - 提供 Tushare Pro API 初始化、日志、重试、数据库批量写入等通用能力
  - 子类只需声明 API_NAME / table_name / pk_columns，可选覆盖 transform()
  - 一条 collect() 走完：fetch → transform → store

用法：
  class MyCollector(BaseCollector):
      API_NAME = "daily"             # → 自动调 self.pro.daily(**params)
      table_name = "daily"
      pk_columns = ["ts_code", "trade_date"]

  如果 Tushare 返回字段名与表字段不一致：
      def transform(self, df):
          return df.rename(columns={"old_name": "new_name"})
"""

import logging
import time
import sys
import os
from abc import ABC
from typing import Optional, List, Dict, Any
import calendar

import pandas as pd
import psycopg2
import psycopg2.extras

# ──────────────────────────────────────────────
# 项目根目录，方便后续 import
# ──────────────────────────────────────────────
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ──────────────────────────────────────────────
# 数据库连接（直接从环境变量或默认参数获取）
# ──────────────────────────────────────────────
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "127.0.0.1"),
    "port": int(os.getenv("DB_PORT", 5432)),
    "dbname": os.getenv("DB_NAME", "tushare_db"),
    "user": os.getenv("DB_USER", "tushare"),
    "password": os.getenv("DB_PASSWORD", "ClawQuant2026!"),
}


def get_db_conn():
    """获取数据库连接"""
    return psycopg2.connect(**DB_CONFIG)


def get_config(key: str, default=None):
    """从 sys_config 表读取配置值"""
    conn = get_db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT cfg_value FROM sys_config WHERE cfg_key = %s AND is_active = TRUE",
                (key,),
            )
            row = cur.fetchone()
            return row[0] if row else default
    finally:
        conn.close()


def set_config(key: str, value: str, updated_by: str = "collector"):
    """写入/更新配置值"""
    conn = get_db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO sys_config (cfg_key, cfg_value, updated_by)
                VALUES (%s, %s, %s)
                ON CONFLICT (cfg_key) DO UPDATE
                SET cfg_value = EXCLUDED.cfg_value,
                    updated_at = NOW(),
                    updated_by = EXCLUDED.updated_by
                """,
                (key, value, updated_by),
            )
            conn.commit()
    finally:
        conn.close()


# ──────────────────────────────────────────────
# 日志配置
# ──────────────────────────────────────────────
def setup_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                datefmt="%H:%M:%S",
            )
        )
        logger.addHandler(handler)
    return logger


# ──────────────────────────────────────────────
# 数据清洗工具函数
# ──────────────────────────────────────────────
def safe_str(v):
    """将各种空值转为 None"""
    if v is None:
        return None
    if isinstance(v, float) and str(v) == "nan":
        return None
    s = str(v).strip()
    if not s or s.lower() in ("nan", "nat", ""):
        return None
    return s


def safe_float(v):
    """安全转浮点，NaN/None/空 → None"""
    if v is None:
        return None
    if isinstance(v, float):
        return None if str(v) == "nan" else v
    try:
        f = float(v)
        return None if str(f) == "nan" else f
    except (ValueError, TypeError):
        return None


def safe_int(v):
    """安全转整型"""
    if v is None:
        return None
    if isinstance(v, float) and str(v) == "nan":
        return None
    try:
        return int(v)
    except (ValueError, TypeError):
        return None


def _is_nan(v):
    """判断一个值是否为 None/NaN/空字符串"""
    if v is None:
        return True
    if isinstance(v, float):
        import math
        return math.isnan(v)
    if isinstance(v, str) and v.lower() in ("nan", "nat", "none", "null", ""):
        return True
    return False


# ──────────────────────────────────────────────
# 采集基类
# ──────────────────────────────────────────────
class BaseCollector(ABC):
    """
    采集基类
    ---
    子类最低配置：
      API_NAME: str     — Tushare 接口名，基类自动调 self.pro.{API_NAME}(**params)
      table_name: str   — 目标数据库表名
      pk_columns: list  — 主键字段列表（用于 UPSERT）

    可选覆盖：
      transform(df) → df   — 数据转换（列重命名、类型清洗等）
      fetch(**params)       — 完全自定义 fetch 逻辑（默认自动调 pro.{API_NAME}）
      store(df)             — 完全自定义 store 逻辑（默认通用 execute_batch UPSERT）

    基类提供的方法：
      collect(**params, skip_store=False)            — 单次采集
      collect_all_history(start_date, end_date)      — 按月循环补齐历史
    """

    # ── 子类必填 ──
    API_NAME: str = ""          # Tushare Pro 接口名
    table_name: str = ""        # 目标表名
    pk_columns: List[str] = []  # 主键字段列表

    # ── 是否支持按月范围查询 ──
    supports_range_query: bool = True  # 少数接口只支持单日查询时设 False

    def __init__(self):
        # ── 兼容旧属性映射 ──
        if hasattr(self, "INTERFACE_NAME") and self.INTERFACE_NAME and not self.API_NAME:
            self.API_NAME = self.INTERFACE_NAME
        if hasattr(self, "TABLE_NAME") and self.TABLE_NAME and not self.table_name:
            self.table_name = self.TABLE_NAME
        if hasattr(self, "PK_COLUMNS") and getattr(self, "PK_COLUMNS", None) and not self.pk_columns:
            self.pk_columns = getattr(self, "PK_COLUMNS")
        # 删除旧属性 compat helper 避免混淆
        self._old_style = hasattr(self.__class__, "INTERFACE_NAME") or hasattr(self.__class__, "TABLE_NAME")

        self.logger = setup_logger(self.__class__.__name__)

        # ── 从 sys_config 读取配置 ──
        token = get_config("tushare.token")
        if not token:
            raise RuntimeError("❌ sys_config 中未找到 tushare.token，请先写入")

        self.retry_max = int(get_config("collector.retry_max", "3"))
        self.retry_interval = int(get_config("collector.retry_interval", "30"))

        # ── 初始化 Tushare ──
        import tushare as ts

        ts.set_token(token)
        self.pro = ts.pro_api()

        # ── 给底层 HTTP Session 加超时和重试 ──
        import requests
        from requests.adapters import HTTPAdapter
        from urllib3.util.retry import Retry

        session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=2,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["POST"],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        self.pro._DataApi__session = session
        self.pro._DataApi__timeout = 60
        self.pro._DataApi__http_session = session

        self.logger.info(f"✅ {self.__class__.__name__} 初始化完成")

    # ─────────────── fetch：从 Tushare 获取数据 ───────────────
    def fetch(self, **params) -> pd.DataFrame:
        """
        默认 fetch：根据 API_NAME 自动调用 self.pro.{API_NAME}(**params)
        子类可覆盖此方法实现自定义逻辑
        """
        if not self.API_NAME:
            raise ValueError("❌ 子类必须定义 API_NAME，或覆盖 fetch() 方法")
        api = getattr(self.pro, self.API_NAME, None)
        if api is None:
            raise ValueError(f"❌ Tushare Pro 不存在接口: {self.API_NAME}")
        return api(**params)

    # ─────────────── transform：数据转换（可选覆盖） ───────────────
    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        数据转换钩子：fetch 之后、store 之前调用
        子类覆盖用于：列重命名、类型转换、字段清洗等
        """
        return df

    # ─────────────── store：通用批量写入 ───────────────
    def store(self, df: pd.DataFrame) -> int:
        """
        通用写入：execute_batch + UPSERT（幂等写入）
        子类可覆盖此方法实现特殊写入逻辑（如 TRUNCATE 全量覆盖）
        """
        if not self.table_name:
            raise ValueError("❌ 子类必须定义 table_name")
        if not self.pk_columns:
            raise ValueError("❌ 子类必须定义 pk_columns，或覆盖 store()")

        conn = get_db_conn()
        try:
            with conn.cursor() as cur:
                rows = df.to_dict(orient="records")
                if not rows:
                    return 0

                columns = list(rows[0].keys())
                rows = [{c: None if _is_nan(r.get(c)) else r.get(c) for c in columns} for r in rows]
                placeholders = ",".join(["%s"] * len(columns))
                col_names = ",".join(columns)

                update_cols = [c for c in columns if c not in self.pk_columns]
                if update_cols:
                    update_set = ", ".join([f"{c} = EXCLUDED.{c}" for c in update_cols])
                    conflict_sql = f"ON CONFLICT ({', '.join(self.pk_columns)}) DO UPDATE SET {update_set}"
                else:
                    conflict_sql = "ON CONFLICT DO NOTHING"

                insert_sql = (
                    f"INSERT INTO {self.table_name} ({col_names}) "
                    f"VALUES ({placeholders}) {conflict_sql}"
                )

                values = [[r.get(c) for c in columns] for r in rows]
                psycopg2.extras.execute_batch(cur, insert_sql, values)

            conn.commit()
            return len(rows)

        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    # ─────────────── collect：单次采集流程（带重试） ───────────────
    def collect(self, skip_store: bool = False, **params) -> int:
        """
        采集主流程：fetch → transform → [store]

        参数：
          skip_store: True 时不入库（用于调试/预览），返回 DataFrame 行数
          **params:   传给 fetch 的参数（如 trade_date='20260513'）

        返回：入库行数（skip_store=True 时返回 DataFrame 行数）
        """
        last_error = None
        for attempt in range(1, self.retry_max + 1):
            try:
                self.logger.info(f"📡 正在获取 {self.table_name} 数据... (第{attempt}次)")
                df = self.fetch(**params)

                if df is None or df.empty:
                    self.logger.warning(f"⚠️  {self.table_name}: 无数据返回")
                    return 0

                df = self.transform(df)

                if skip_store:
                    self.logger.info(f"🔍 {self.table_name}: 获取 {len(df)} 行（skip_store，未入库）")
                    return len(df)

                rows = self.store(df)
                self.logger.info(f"✅ {self.table_name}: 入库 {rows} 行")
                return rows

            except Exception as e:
                last_error = e
                self.logger.error(f"❌ 第{attempt}次失败: {e}")
                if attempt < self.retry_max:
                    wait = self.retry_interval * attempt
                    self.logger.info(f"⏳ 等待 {wait}s 后重试...")
                    time.sleep(wait)

        raise RuntimeError(
            f"❌ {self.table_name} 采集失败（已重试 {self.retry_max} 次）: {last_error}"
        )

    # ─────────────── collect_all_history：按月补齐历史 ───────────────
    DEFAULT_START = "20200101"

    def collect_all_history(self, start_date: str = None, end_date: str = None) -> int:
        """
        按月循环补齐历史数据
        对 supports_range_query=True 的接口：按月范围查询
        对 supports_range_query=False 的接口：逐日查询

        参数：
          start_date: 开始日期 YYYYMMDD，默认 20200101
          end_date:   结束日期 YYYYMMDD，默认昨天

        返回：总入库行数
        """
        from datetime import datetime, timedelta

        if start_date is None:
            start_date = self.DEFAULT_START
        if end_date is None:
            end_date = datetime.now().strftime("%Y%m%d")

        total = 0
        s = datetime.strptime(start_date, "%Y%m%d")
        e = datetime.strptime(end_date, "%Y%m%d")

        if self.supports_range_query:
            # ── 按月范围查询 ──
            cur = s.replace(day=1)
            while cur <= e:
                _, ld = calendar.monthrange(cur.year, cur.month)
                month_end = min(cur.replace(day=ld), e)
                s_str = cur.strftime("%Y%m%d")
                e_str = month_end.strftime("%Y%m%d")
                try:
                    rows = self.collect(start_date=s_str, end_date=e_str)
                    total += rows
                    self.logger.info(f"  {s_str}~{e_str}: {rows} 行")
                except Exception as ex:
                    self.logger.warning(f"  {s_str}~{e_str}: {ex}")
                # 下个月
                if cur.month == 12:
                    cur = cur.replace(year=cur.year + 1, month=1)
                else:
                    cur = cur.replace(month=cur.month + 1)
                time.sleep(0.3)
        else:
            # ── 逐日查询（ccass_hold_detail 等不支持范围查询的接口） ──
            d = s
            while d <= e:
                ds = d.strftime("%Y%m%d")
                try:
                    rows = self.collect(trade_date=ds)
                    total += rows
                except Exception as ex:
                    self.logger.warning(f"  {ds}: {ex}")
                d += timedelta(days=1)
                time.sleep(0.3)

        self.logger.info(f"🏁 {self.table_name} 历史补齐完成，合计 {total} 行")
        return total
