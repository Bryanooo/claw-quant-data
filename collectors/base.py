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
import hashlib
import math
import re
import time
import sys
import os
from abc import ABC
from datetime import timedelta
from typing import Optional, List, Dict, Any
import calendar

import pandas as pd
import psycopg2
import psycopg2.extras
from service.config import (
    DB_CONFIG,
    TUSHARE_CONNECT_TIMEOUT_SECONDS,
    TUSHARE_READ_TIMEOUT_SECONDS,
    get_env_tushare_token,
)
from service.collection_jobs.context import is_durable_job_active
from service.clock import business_now
from service.tushare_rate_limit import install_distributed_rate_limit
from collectors.contracts import (
    CollectorRequest,
    CollectorResult,
    CollectorSpec,
    EmptyPolicy,
    PaginationMode,
    ResourceClass,
    WriteMode,
)

# ──────────────────────────────────────────────
# 项目根目录，方便后续 import
# ──────────────────────────────────────────────
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class CollectorError(RuntimeError):
    """Base error carrying retry semantics for schedulers and workers."""

    retryable = True
    retry_after_seconds: int | None = None


class NonRetryableCollectorError(CollectorError):
    retryable = False


class CollectorRateLimitError(CollectorError):
    def __init__(self, message: str, retry_after_seconds: int):
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds


class PartialCollectionError(CollectorError):
    """At least one partition failed, so the overall result is incomplete."""

    completion_status = "incomplete"

    def __init__(self, failures: list[str], rows_inserted: int = 0):
        self.failures = tuple(failures)
        self.rows_inserted = rows_inserted
        preview = "; ".join(failures[:5])
        suffix = f"; and {len(failures) - 5} more" if len(failures) > 5 else ""
        super().__init__(
            f"{len(failures)} collection partition(s) failed after "
            f"{rows_inserted} stored rows: {preview}{suffix}"
        )


def _tushare_error(error: Exception) -> CollectorError | None:
    """Classify HTTP-200 Tushare errors that should not use blind retries."""
    message = str(error)
    if "频率超限" in message or "访问频率" in message:
        match = re.search(r"(\d+)次/(分钟|小时|天)", message)
        if not match:
            retry_after = 60
        elif match.group(2) == "天":
            # “N次/天” is a hard daily allocation, not a request-spacing rule.
            # Retrying after 86400/N seconds creates a retry storm once the
            # allocation is exhausted. Defer until the next Shanghai day with
            # a small buffer so the durable queue can safely try again.
            now = business_now()
            reset_at = (now + timedelta(days=1)).replace(
                hour=0, minute=5, second=0, microsecond=0
            )
            retry_after = max(math.ceil((reset_at - now).total_seconds()), 60)
        else:
            count = max(int(match.group(1)), 1)
            window = {"分钟": 60, "小时": 3600}[match.group(2)]
            retry_after = max(window // count, 1)
        return CollectorRateLimitError(message, retry_after)
    permanent_markers = (
        "没有接口",
        "访问权限",
        "参数校验失败",
        "必填参数",
        "正确的接口名",
    )
    if any(marker in message for marker in permanent_markers):
        return NonRetryableCollectorError(message)
    return None

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
    logger.propagate = False
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


def sanitize_postgres_value(value: Any) -> tuple[Any, int]:
    """Remove NUL bytes that PostgreSQL text/JSON cannot represent.

    Tushare occasionally returns embedded ``\\x00`` bytes in descriptive
    strings. PostgreSQL rejects those bytes in both text and jsonb values. The
    sanitizer preserves the rest of the value and returns a count so every
    collection result can expose auditable cleaning evidence.
    """
    if isinstance(value, str):
        count = value.count("\x00")
        return value.replace("\x00", ""), count
    if isinstance(value, dict):
        cleaned: dict[Any, Any] = {}
        total = 0
        for key, item in value.items():
            clean_key, key_count = sanitize_postgres_value(key)
            clean_item, item_count = sanitize_postgres_value(item)
            cleaned[clean_key] = clean_item
            total += key_count + item_count
        return cleaned, total
    if isinstance(value, list):
        cleaned_list = []
        total = 0
        for item in value:
            clean_item, count = sanitize_postgres_value(item)
            cleaned_list.append(clean_item)
            total += count
        return cleaned_list, total
    if isinstance(value, tuple):
        cleaned_tuple = []
        total = 0
        for item in value:
            clean_item, count = sanitize_postgres_value(item)
            cleaned_tuple.append(clean_item)
            total += count
        return tuple(cleaned_tuple), total
    return value, 0


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
    write_mode = WriteMode.UPSERT
    pagination_mode = PaginationMode.DATE_RANGE
    empty_policy = EmptyPolicy.REQUIRES_VERIFICATION
    resource_class = ResourceClass.MARKET
    collector_version = "1"
    required_parameters: tuple[str, ...] = ()

    @classmethod
    def spec(cls) -> CollectorSpec:
        """Return static metadata without constructing an SDK/DB client."""
        api_name = getattr(cls, "API_NAME", "") or getattr(cls, "INTERFACE_NAME", "")
        table_name = getattr(cls, "table_name", "") or getattr(cls, "TABLE_NAME", "")
        primary_keys = getattr(cls, "pk_columns", ()) or getattr(cls, "PK_COLUMNS", ())
        return CollectorSpec(
            qualified_name=f"{cls.__module__}.{cls.__name__}",
            api_name=api_name,
            table_name=table_name,
            primary_keys=tuple(primary_keys),
            write_mode=WriteMode(cls.write_mode),
            pagination_mode=PaginationMode(cls.pagination_mode),
            empty_policy=EmptyPolicy(cls.empty_policy),
            resource_class=ResourceClass(cls.resource_class),
            version=str(cls.collector_version),
            required_parameters=tuple(cls.required_parameters),
        )

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
        self._sanitization_nul_characters = 0
        self._sanitization_fields: set[str] = set()

        # Environment configuration is convenient for containers and CI.
        # Keep sys_config as a backwards-compatible fallback for deployments
        # that already store the token in PostgreSQL.
        token = get_env_tushare_token() or get_config("tushare.token")
        if not token:
            raise RuntimeError(
                "❌ 未配置 Tushare Token，请设置 TUSHARE_TOKEN 或写入 "
                "sys_config['tushare.token']"
            )

        # The durable queue owns whole-job retries. Inside a worker, avoid
        # multiplying them by another collector-level retry loop.
        retry_default = "1" if is_durable_job_active() else "3"
        self.retry_max = int(get_config("collector.retry_max", retry_default))
        self.retry_interval = int(get_config("collector.retry_interval", "30"))

        # ── 初始化 Tushare ──
        import tushare as ts

        ts.set_token(token)
        self.pro = ts.pro_api()

        # Tushare dynamically routes every SDK endpoint through query().
        # Wrapping it once means dedicated and catalog collectors participate
        # in the same token-wide, cross-process rate limit.
        install_distributed_rate_limit(self.pro)
        self._distributed_rate_limit_installed = True
        self._request_count = 0
        rate_limited_query = self.pro.query

        def counted_query(api_name, *args, **kwargs):
            self._request_count += 1
            return rate_limited_query(api_name, *args, **kwargs)

        self.pro.query = counted_query

        # Transport retries are intentionally disabled here. Every real
        # Tushare attempt must pass through query(), reserve a distributed
        # rate-limit slot, and be observed by the collector/worker retry loop.
        import requests
        from requests.adapters import HTTPAdapter
        session = requests.Session()
        adapter = HTTPAdapter(max_retries=0)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        self.pro._DataApi__session = session
        # Requests accepts a ``(connect, read)`` timeout tuple.  A dead Docker
        # route or DNS socket must fail quickly, while a connected Tushare
        # response still gets enough time to return a large page.
        self.pro._DataApi__timeout = (
            TUSHARE_CONNECT_TIMEOUT_SECONDS,
            TUSHARE_READ_TIMEOUT_SECONDS,
        )
        self.pro._DataApi__http_session = session

        self.logger.info(f"✅ {self.__class__.__name__} 初始化完成")

    def _database_safe_value(self, value: Any, field: str) -> Any:
        cleaned, count = sanitize_postgres_value(value)
        if count:
            self._sanitization_nul_characters = (
                getattr(self, "_sanitization_nul_characters", 0) + count
            )
            fields = getattr(self, "_sanitization_fields", set())
            fields.add(field)
            self._sanitization_fields = fields
        return cleaned

    def _sanitization_evidence(self) -> dict[str, Any]:
        return {
            "nul_characters_removed": getattr(
                self, "_sanitization_nul_characters", 0
            ),
            "affected_fields": sorted(getattr(self, "_sanitization_fields", set())),
        }

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

        present_keys = [key for key in self.pk_columns if key in df.columns]
        if len(present_keys) == len(self.pk_columns):
            duplicate_mask = df.duplicated(subset=present_keys, keep="last")
            duplicate_count = int(duplicate_mask.sum())
            if duplicate_count:
                logger = getattr(self, "logger", logging.getLogger(__name__))
                logger.warning(
                    "⚠️  %s: 上游批次包含 %s 个重复主键，保留每组最后一条",
                    self.table_name,
                    duplicate_count,
                )
                df = df.loc[~duplicate_mask].copy()

        conn = get_db_conn()
        try:
            with conn.cursor() as cur:
                rows = df.to_dict(orient="records")
                if not rows:
                    return 0

                columns = list(rows[0].keys())
                rows = [
                    {
                        c: (
                            None
                            if _is_nan(r.get(c))
                            else self._database_safe_value(r.get(c), c)
                        )
                        for c in columns
                    }
                    for r in rows
                ]
                quote = lambda value: psycopg2.extensions.quote_ident(value, conn)
                col_names = ",".join(quote(c) for c in columns)

                update_cols = [c for c in columns if c not in self.pk_columns]
                if update_cols:
                    update_set = ", ".join(
                        f"{quote(c)} = EXCLUDED.{quote(c)}" for c in update_cols
                    )
                    conflict_columns = ", ".join(quote(c) for c in self.pk_columns)
                    conflict_sql = (
                        f"ON CONFLICT ({conflict_columns}) DO UPDATE SET {update_set} "
                        "WHERE "
                        + " OR ".join(
                            f"target.{quote(c)} IS DISTINCT FROM EXCLUDED.{quote(c)}"
                            for c in update_cols
                        )
                    )
                else:
                    conflict_sql = "ON CONFLICT DO NOTHING"

                insert_sql = (
                    f"INSERT INTO {quote(self.table_name)} AS target ({col_names}) "
                    f"VALUES %s {conflict_sql}"
                )

                values = [tuple(r.get(c) for c in columns) for r in rows]
                psycopg2.extras.execute_values(
                    cur,
                    insert_sql,
                    values,
                    page_size=1000,
                )

            conn.commit()
            return len(rows)

        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    def store_snapshot(self, df: pd.DataFrame) -> int:
        """Atomically merge a complete snapshot without taking a TRUNCATE lock.

        Rows are validated in a session-local staging table, then upserted and
        stale keys are deleted in one transaction. An empty upstream response
        is always fail-safe and never clears the target table.
        """
        if df is None or df.empty:
            return 0
        if not self.table_name or not self.pk_columns:
            raise ValueError("snapshot collector requires table_name and pk_columns")

        rows = df.to_dict(orient="records")
        columns = list(rows[0])
        missing_keys = [key for key in self.pk_columns if key not in columns]
        if missing_keys:
            raise ValueError(
                f"snapshot for {self.table_name} is missing keys: {missing_keys}"
            )
        normalized = [
            tuple(
                None
                if _is_nan(row.get(column))
                else self._database_safe_value(row.get(column), column)
                for column in columns
            )
            for row in rows
        ]
        connection = get_db_conn()
        try:
            quote = lambda value: psycopg2.extensions.quote_ident(value, connection)
            target = quote(self.table_name)
            staging_name = quote(f"cq_stage_{self.table_name}"[:60])
            column_sql = ",".join(quote(column) for column in columns)
            updates = [column for column in columns if column not in self.pk_columns]
            if updates:
                update_sql = ", ".join(
                    f"{quote(column)} = EXCLUDED.{quote(column)}" for column in updates
                )
                distinct_sql = " OR ".join(
                    f"target.{quote(column)} IS DISTINCT FROM EXCLUDED.{quote(column)}"
                    for column in updates
                )
                conflict_sql = (
                    f"ON CONFLICT ({','.join(quote(key) for key in self.pk_columns)}) "
                    f"DO UPDATE SET {update_sql} WHERE {distinct_sql}"
                )
            else:
                conflict_sql = "ON CONFLICT DO NOTHING"
            key_match = " AND ".join(
                f"target.{quote(key)} = stage.{quote(key)}" for key in self.pk_columns
            )

            with connection.cursor() as cursor:
                cursor.execute(
                    f"CREATE TEMP TABLE {staging_name} "
                    f"(LIKE {target} INCLUDING DEFAULTS) ON COMMIT DROP"
                )
                psycopg2.extras.execute_values(
                    cursor,
                    f"INSERT INTO {staging_name} ({column_sql}) VALUES %s",
                    normalized,
                    page_size=1000,
                )
                cursor.execute(
                    f"INSERT INTO {target} AS target ({column_sql}) "
                    f"SELECT {column_sql} FROM {staging_name} {conflict_sql}"
                )
                cursor.execute(
                    f"DELETE FROM {target} AS target "
                    f"WHERE NOT EXISTS (SELECT 1 FROM {staging_name} AS stage "
                    f"WHERE {key_match})"
                )
            connection.commit()
            return len(rows)
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    # ─────────────── run：统一采集流程（带重试） ───────────────
    def run(
        self,
        request: CollectorRequest | None = None,
        *,
        skip_store: bool = False,
        **params,
    ) -> CollectorResult:
        """Execute fetch → transform → store and return structured evidence."""
        if request is not None and (params or skip_store):
            raise ValueError("pass either CollectorRequest or keyword parameters")
        effective = request or CollectorRequest(params, skip_store=skip_store)
        missing = [
            name for name in self.required_parameters
            if effective.parameters.get(name) in (None, "")
        ]
        if missing:
            raise NonRetryableCollectorError(
                f"{self.API_NAME} missing required parameters: {', '.join(missing)}"
            )

        spec = self.spec()
        """
        The retry loop lives at this boundary so each attempt repeats the
        complete, rate-limited SDK request rather than retrying invisibly in
        requests/urllib3.
        """
        last_error = None
        self._request_count = 0
        self._sanitization_nul_characters = 0
        self._sanitization_fields = set()
        for attempt in range(1, self.retry_max + 1):
            try:
                self.logger.info(f"📡 正在获取 {self.table_name} 数据... (第{attempt}次)")
                df = self.fetch(**dict(effective.parameters))

                if df is None or df.empty:
                    self.logger.warning(f"⚠️  {self.table_name}: 无数据返回")
                    return CollectorResult(
                        collector_name=spec.qualified_name,
                        collector_version=spec.version,
                        api_name=spec.api_name,
                        table_name=spec.table_name,
                        fetched_rows=0,
                        stored_rows=0,
                        request_count=max(
                            int(getattr(self, "_request_count", 0)), attempt
                        ),
                        partitions=((effective.partition_key,) if effective.partition_key else ()),
                        empty_reason="upstream_returned_no_rows",
                        evidence={
                            "empty_policy": spec.empty_policy.value,
                            "sanitization": self._sanitization_evidence(),
                        },
                    )

                df = self.transform(df)
                fetched_rows = len(df)
                # Keep only a deterministic digest as pagination evidence. It
                # lets the outer paginator detect endpoints that silently
                # ignore ``offset`` without retaining or exposing payloads.
                try:
                    page_signature = hashlib.sha256(
                        df.to_json(
                            orient="split",
                            date_format="iso",
                            default_handler=str,
                        ).encode("utf-8")
                    ).hexdigest()
                except Exception:
                    page_signature = hashlib.sha256(
                        repr(df.to_dict(orient="records")).encode("utf-8")
                    ).hexdigest()

                if effective.skip_store:
                    self.logger.info(f"🔍 {self.table_name}: 获取 {len(df)} 行（skip_store，未入库）")
                    rows = 0
                else:
                    rows = self.store(df)
                    self.logger.info(f"✅ {self.table_name}: 入库 {rows} 行")

                return CollectorResult(
                    collector_name=spec.qualified_name,
                    collector_version=spec.version,
                    api_name=spec.api_name,
                    table_name=spec.table_name,
                    fetched_rows=fetched_rows,
                    stored_rows=rows,
                    request_count=max(
                        int(getattr(self, "_request_count", 0)), attempt
                    ),
                    partitions=((effective.partition_key,) if effective.partition_key else ()),
                    evidence={
                        "write_mode": spec.write_mode.value,
                        "pagination_mode": spec.pagination_mode.value,
                        "skip_store": effective.skip_store,
                        "page_signature": page_signature,
                        "sanitization": self._sanitization_evidence(),
                    },
                )

            except Exception as e:
                last_error = e
                self.logger.error(f"❌ 第{attempt}次失败: {e}")
                # The distributed limiter has not called the upstream yet.
                # Preserve its queue-level deferral semantics instead of
                # wrapping it as a collector failure and consuming retries.
                if getattr(e, "defer_without_failure", False):
                    raise
                classified = _tushare_error(e)
                if classified is not None:
                    classified.retry_count = attempt - 1
                    raise classified from e
                if attempt < self.retry_max:
                    wait = self.retry_interval * attempt
                    self.logger.info(f"⏳ 等待 {wait}s 后重试...")
                    time.sleep(wait)

        error = CollectorError(
            f"❌ {self.table_name} 采集失败（已重试 {self.retry_max} 次）: {last_error}"
        )
        error.retry_count = max(self.retry_max - 1, 0)
        raise error from last_error

    def run_offset_paginated(
        self,
        *,
        page_size: int = 1000,
        max_pages: int = 100,
        skip_store: bool = False,
        **params,
    ) -> CollectorResult:
        """Exhaust one offset-capable logical partition, failing closed.

        Each page goes through :meth:`run`, preserving collector retries,
        transforms and idempotent writes. Completion is claimed only after a
        short page (including an empty first page) proves exhaustion.
        """
        if "limit" in params or "offset" in params:
            raise ValueError("limit and offset are managed by run_offset_paginated")
        if page_size < 1 or page_size > 10_000:
            raise ValueError("page_size must be between 1 and 10000")
        if max_pages < 1 or max_pages > 1_000:
            raise ValueError("max_pages must be between 1 and 1000")

        spec = self.spec()
        fetched_total = 0
        stored_total = 0
        request_total = 0
        pages_completed = 0
        signatures: set[str] = set()
        nul_characters_removed = 0
        affected_fields: set[str] = set()
        warnings: list[str] = []

        for page in range(max_pages):
            offset = page * page_size
            result = self.run(
                skip_store=skip_store,
                **params,
                limit=page_size,
                offset=offset,
            )
            request_total += result.request_count
            sanitization = result.evidence.get("sanitization", {})
            nul_characters_removed += int(
                sanitization.get("nul_characters_removed", 0)
            )
            affected_fields.update(sanitization.get("affected_fields", ()))
            warnings.extend(result.warnings)

            if result.fetched_rows:
                signature = str(result.evidence.get("page_signature", ""))
                if signature and signature in signatures:
                    error = PartialCollectionError(
                        [
                            f"{self.API_NAME} repeated an earlier page at offset "
                            f"{offset}; upstream may ignore offset"
                        ],
                        stored_total,
                    )
                    error.rows_fetched = fetched_total
                    raise error
                if signature:
                    signatures.add(signature)
                fetched_total += result.fetched_rows
                stored_total += result.stored_rows
                pages_completed += 1

            if result.fetched_rows < page_size:
                partition = next(
                    (
                        str(params[name])
                        for name in (
                            "trade_date",
                            "date",
                            "cal_date",
                            "ann_date",
                            "period",
                        )
                        if params.get(name) not in (None, "")
                    ),
                    None,
                )
                return CollectorResult(
                    collector_name=spec.qualified_name,
                    collector_version=spec.version,
                    api_name=spec.api_name,
                    table_name=spec.table_name,
                    fetched_rows=fetched_total,
                    stored_rows=stored_total,
                    request_count=request_total,
                    partitions=((partition,) if partition else ()),
                    empty_reason=(
                        "upstream_returned_no_rows" if fetched_total == 0 else None
                    ),
                    warnings=tuple(dict.fromkeys(warnings)),
                    evidence={
                        "verified": True,
                        "verification_type": "offset_exhaustion",
                        "mode": "offset",
                        "page_size": page_size,
                        "pages_completed": pages_completed,
                        "rows_fetched": fetched_total,
                        "rows_stored": stored_total,
                        "exhausted": True,
                        "skip_store": skip_store,
                        "sanitization": {
                            "nul_characters_removed": nul_characters_removed,
                            "affected_fields": sorted(affected_fields),
                        },
                    },
                )

        error = PartialCollectionError(
            [
                f"{self.API_NAME} reached max_pages={max_pages} before "
                "offset exhaustion"
            ],
            stored_total,
        )
        error.rows_fetched = fetched_total
        error.completion_evidence = {
            "verified": False,
            "mode": "offset",
            "page_size": page_size,
            "pages_completed": pages_completed,
            "rows_fetched": fetched_total,
            "rows_stored": stored_total,
            "exhausted": False,
        }
        raise error

    # ─────────────── collect：兼容旧调用方的整数返回值 ───────────────
    def collect(self, skip_store: bool = False, **params) -> int:
        """Compatibility wrapper; new runtime code should call :meth:`run`."""
        result = self.run(skip_store=skip_store, **params)
        return result.fetched_rows if skip_store else result.stored_rows

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
            end_date = business_now().strftime("%Y%m%d")

        total = 0
        s = datetime.strptime(start_date, "%Y%m%d")
        e = datetime.strptime(end_date, "%Y%m%d")

        if self.supports_range_query:
            # ── 按月范围查询 ──
            cur = s.replace(day=1)
            failures: list[str] = []
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
                    failures.append(f"{s_str}~{e_str}: {ex}")
                # 下个月
                if cur.month == 12:
                    cur = cur.replace(year=cur.year + 1, month=1)
                else:
                    cur = cur.replace(month=cur.month + 1)
                time.sleep(0.3)
        else:
            # ── 逐日查询（ccass_hold_detail 等不支持范围查询的接口） ──
            d = s
            failures = []
            while d <= e:
                ds = d.strftime("%Y%m%d")
                try:
                    rows = self.collect(trade_date=ds)
                    total += rows
                except Exception as ex:
                    self.logger.warning(f"  {ds}: {ex}")
                    failures.append(f"{ds}: {ex}")
                d += timedelta(days=1)
                time.sleep(0.3)

        if failures:
            raise PartialCollectionError(failures, total)
        self.logger.info(f"🏁 {self.table_name} 历史补齐完成，合计 {total} 行")
        return total
