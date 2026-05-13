"""
=============================================================================
claw-quant-v2 采集基类
=============================================================================

职责：
  1. 从 sys_config 表读取配置（Token、重试参数等）
  2. 初始化 Tushare Pro API
  3. 提供统一的重试、日志、DB 连接管理
  4. 子类只需实现 fetch() 和 store() 两个抽象方法

用法：
  class MyCollector(BaseCollector):
      def fetch(self, **params) -> pd.DataFrame:
          ...
      def store(self, df: pd.DataFrame) -> int:
          ...
"""

import logging
import time
import sys
import os
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any

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
    "password": os.getenv("DB_PASSWORD"),  # 必填：从环境变量读取，无默认值。见 .env.example
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
# 采集基类
# ──────────────────────────────────────────────
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


class BaseCollector(ABC):
    """
    采集基类
    ---
    子类需要实现：
      - table_name: str        — 目标表名（用于日志和校验）
      - pk_columns: list       — 主键字段列表（用于 ON CONFLICT）
      - fetch(**params)        — 从 Tushare 获取 DataFrame
      - fetch_params(defaults) — 返回默认的 fetch 参数（可选覆盖）
    """

    # 子类覆盖
    table_name: str = ""
    pk_columns: list = []  # 主键字段，用于幂等写入

    def __init__(self):
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
            total=3,                     # 最多重试 3 次（含连接+读取失败）
            backoff_factor=2,            # 退避：1s, 2s, 4s
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["POST"],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        # 超时：connect=30s, read=60s
        from tushare.pro.client import DataApi
        self.pro._DataApi__session = session
        # 直接设置 DataApi 的超时属性（tushare 内部使用 __session.post(url, timeout=...)）
        self.pro._DataApi__timeout = 60
        self.pro._DataApi__http_session = session

        self.logger.info(f"✅ {self.__class__.__name__} 初始化完成")

    # ─────────────── 子类必须实现的抽象方法 ───────────────
    @abstractmethod
    def fetch(self, **params) -> pd.DataFrame:
        """从 Tushare 获取数据，返回 DataFrame"""
        ...

    # ─────────────── 通用 store 方法 ───────────────
    def store(self, df: pd.DataFrame) -> int:
        """
        通用写入：自动根据 pk_columns 生成 UPSERT（幂等写入）。
        子类如果写入逻辑特殊（如 TRUNCATE 全量覆盖），可覆盖此方法。
        """
        if not self.table_name:
            raise ValueError("❌ 子类必须定义 table_name")
        if not self.pk_columns:
            raise ValueError("❌ 子类必须定义 pk_columns，或用 TRUNCATE 模式覆盖 store()")

        conn = get_db_conn()
        try:
            with conn.cursor() as cur:
                rows = df.to_dict(orient="records")
                if not rows:
                    return 0

                # 清洗：'NaN' 字符串 → None（pandas to_dict 会把 'NaN' 转成 float nan）
                # 但真正的 float 类型的 None/NaN 也需要处理
                def _is_nan(v):
                    if v is None:
                        return True
                    if isinstance(v, float):
                        import math
                        return math.isnan(v)
                    if isinstance(v, str) and v.lower() in ("nan", "nat", "none", "null", ""):
                        return True
                    return False

                columns = list(rows[0].keys())
                rows = [{c: None if _is_nan(r.get(c)) else r.get(c) for c in columns} for r in rows]
                placeholders = ",".join(["%s"] * len(columns))
                col_names = ",".join(columns)

                # 构造 ON CONFLICT UPDATE 子句（排除主键）
                update_cols = [c for c in columns if c not in self.pk_columns]
                if update_cols:
                    update_set = ", ".join(
                        [f"{c} = EXCLUDED.{c}" for c in update_cols]
                    )
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

    # ─────────────── 通用采集流程（含重试） ───────────────
    def collect(self, **params) -> int:
        """
        采集主流程：fetch → store，含重试和日志
        返回：入库行数
        """
        last_error = None
        for attempt in range(1, self.retry_max + 1):
            try:
                self.logger.info(f"📡 正在获取 {self.table_name} 数据... (第{attempt}次)")
                df = self.fetch(**params)

                if df is None or df.empty:
                    self.logger.warning(f"⚠️  {self.table_name}: 无数据返回")
                    return 0

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
