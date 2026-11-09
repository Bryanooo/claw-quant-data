"""
财务数据采集基类（继承自 BaseCollector）

公共功能：
- fetch(period=...): 调用 _vip 接口按季度取全市场
- store(df): 复用统一批量 UPSERT
- fetch_period/save 仅作为旧调用方兼容别名
"""

import hashlib
import logging
import time

import pandas as pd
from contextlib import closing
from psycopg2 import sql
from psycopg2.extras import execute_values
from collectors.base import BaseCollector, get_db_conn
from service.financial_statements import VERSIONED_STATEMENTS
from collectors.contracts import EmptyPolicy, PaginationMode, ResourceClass
from collectors.tushare_raw import IncompleteCollectionError, PaginationStalledError

logger = logging.getLogger("collector.finance")


class BaseFinanceCollector(BaseCollector):
    """
    按季度取全市场的财务采集器基类。
    子类只需设置：INTERFACE_NAME, TABLE_NAME, CORE_FIELDS
    """

    INTERFACE_NAME = ""  # 子类覆盖，如 "balancesheet_vip"
    TABLE_NAME = ""  # 子类覆盖
    CORE_FIELDS = []  # 子类覆盖
    PK_COLUMNS = ["ts_code", "end_date", "report_type"]  # 子类覆盖
    pagination_mode = PaginationMode.OFFSET
    empty_policy = EmptyPolicy.REQUIRES_VERIFICATION
    resource_class = ResourceClass.FINANCE
    required_parameters = ("period",)
    upstream_period_parameter = "period"

    def fetch(self, period: str | None = None, **_params):
        """Standard collector entry point for one complete report period."""
        if not period:
            raise ValueError("financial collector requires period")
        self._pagination_scopes = []
        # An explicit original/adjusted report request must not silently fall
        # back to the provider's latest consolidated default (type 1).
        report_type = _params.get("report_type")
        if report_type is not None:
            if self.TABLE_NAME not in {"income", "balancesheet", "cashflow"}:
                raise ValueError(f"{self.TABLE_NAME} does not support report_type")
            if str(report_type) not in {str(n) for n in range(1, 13)}:
                raise ValueError("report_type must be an integer from 1 to 12")
            return self._fetch_paginated(period, extra_params={"report_type": str(report_type)})
        return self.fetch_period(period)

    def partition_completion_evidence(self) -> dict:
        """Return proof that every upstream period scope reached exhaustion."""
        scopes = list(getattr(self, "_pagination_scopes", ()))
        if not scopes or not all(item.get("exhausted") for item in scopes):
            return {
                "verified": False,
                "verification_type": "financial_period_offset_exhaustion",
                "scopes": scopes,
            }
        return {
            "verified": True,
            "verification_type": "financial_period_offset_exhaustion",
            "mode": "offset",
            "scopes": scopes,
            "pages_completed": sum(item["pages_completed"] for item in scopes),
            "rows_fetched_before_deduplication": sum(
                item["rows_fetched"] for item in scopes
            ),
        }

    def fetch_period(self, period: str):
        """Exhaust one report period with explicit offset pagination."""
        return self._fetch_paginated(period)

    def _fetch_paginated(
        self,
        period: str,
        *,
        extra_params: dict | None = None,
        page_size: int = 3000,
        max_pages: int = 20,
    ) -> pd.DataFrame:
        """Fetch one bounded financial scope and reject pagination cycles."""
        fields = ",".join(self.CORE_FIELDS)
        fn = getattr(self.pro, self.INTERFACE_NAME)
        request_scope = dict(extra_params or {})
        pages = []
        seen_signatures: set[str] = set()
        for page_number in range(max_pages):
            offset = page_number * page_size
            request = {
                self.upstream_period_parameter: period,
                "fields": fields,
                "limit": page_size,
                "offset": offset,
                **request_scope,
            }
            frame = fn(**request)
            if frame is None or frame.empty:
                break
            if "report_type" in request_scope:
                types = (pd.to_numeric(frame["report_type"], errors="coerce")
                         if "report_type" in frame else pd.Series(dtype=float))
                if len(types) != len(frame) or not types.eq(int(request_scope["report_type"])).all():
                    raise IncompleteCollectionError(
                        f"{self.INTERFACE_NAME} ignored requested report_type={request_scope['report_type']}"
                    )
            if "end_date" in frame.columns:
                returned_periods = {
                    str(value) for value in frame["end_date"].dropna().unique()
                }
                if returned_periods - {period}:
                    sample = ", ".join(sorted(returned_periods)[:5])
                    raise IncompleteCollectionError(
                        f"{self.INTERFACE_NAME} ignored "
                        f"{self.upstream_period_parameter}={period}; "
                        f"response contains end_date={sample}"
                    )
            signature = hashlib.sha256(
                frame.to_json(orient="records", date_format="iso").encode("utf-8")
            ).hexdigest()
            if signature in seen_signatures:
                raise PaginationStalledError(
                    f"{self.INTERFACE_NAME} repeated an earlier page at offset {offset}"
                )
            seen_signatures.add(signature)
            pages.append(frame)
            logger.info(
                "  [%s] %s offset=%s: %s 行",
                self.INTERFACE_NAME,
                period,
                offset,
                len(frame),
            )
            if len(frame) < page_size:
                break
            time.sleep(0.25)
        else:
            raise IncompleteCollectionError(
                f"{self.INTERFACE_NAME} exceeded {max_pages} pages for {period}"
            )

        fetched_rows = sum(len(page) for page in pages)
        scope_evidence = {
            "parameter": self.upstream_period_parameter,
            "period": period,
            "parameters": request_scope,
            "page_size": page_size,
            "pages_completed": len(pages),
            "rows_fetched": fetched_rows,
            "exhausted": True,
        }
        scopes = getattr(self, "_pagination_scopes", None)
        if scopes is None:
            scopes = []
            self._pagination_scopes = scopes
        scopes.append(scope_evidence)
        if not pages:
            return pd.DataFrame(columns=self.CORE_FIELDS)
        result = pd.concat(pages, ignore_index=True)
        if self.TABLE_NAME not in VERSIONED_STATEMENTS:
            result = _select_latest_reports(result, self.PK_COLUMNS)
        logger.info("  [%s] %s complete: %s 行", self.INTERFACE_NAME, period, len(result))
        return result

    def store(self, df):
        """Normalize the selected output schema and use the shared UPSERT sink."""
        if df is None or len(df) == 0:
            return 0
        normalized = df.reindex(columns=self.CORE_FIELDS).map(_to_val)
        if self.TABLE_NAME in VERSIONED_STATEMENTS:
            with closing(get_db_conn()) as conn, conn, conn.cursor() as cursor:
                cursor.execute(sql.SQL(
                    "CREATE TEMP TABLE finance_input (LIKE {} INCLUDING DEFAULTS) ON COMMIT DROP"
                ).format(sql.Identifier(self.TABLE_NAME)))
                statement = sql.SQL("INSERT INTO finance_input ({}) VALUES %s").format(
                    sql.SQL(",").join(map(sql.Identifier, self.CORE_FIELDS))
                )
                values = [tuple(self._database_safe_value(_to_val(value), column)
                                for column, value in zip(self.CORE_FIELDS, record))
                          for record in normalized.itertuples(index=False, name=None)]
                execute_values(cursor, statement, values, page_size=1000)
                cursor.execute("SELECT archive_financial_batch(%s, 'pg_temp.finance_input', false)",
                               (self.TABLE_NAME,))
            rows = len(values)
        else:
            rows = super().store(normalized)
        periods = sorted(df["end_date"].unique()) if "end_date" in df.columns else ["?"]
        logger.info(f"  ✅ {self.TABLE_NAME} {periods}: upsert {rows} 行")
        return rows

    def save(self, df):
        """Deprecated compatibility alias for :meth:`store`."""
        return self.store(df)


def _select_latest_reports(frame: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
    """Select a whole revision, never synthesize a report from mixed revisions.

    Provider/page order is not revision order. Prefer the latest disclosure,
    then the update flag, then the richest row within that same revision.
    A newer sparse revision must still supersede an older rich revision.
    """
    if not frame.duplicated(keys).any():
        return frame
    ranked = frame.copy()
    dates = [pd.to_datetime(ranked[name], format='%Y%m%d', errors='coerce')
             for name in ('ann_date', 'f_ann_date') if name in ranked]
    ranked['_disclosed_at'] = pd.concat(dates, axis=1).max(axis=1) if dates else pd.NaT
    ranked['_revision_flag'] = pd.to_numeric(ranked.get('update_flag', pd.Series(0, index=ranked.index)), errors='coerce').fillna(0)
    ranked['_populated_fields'] = frame.notna().sum(axis=1)
    ordering = ['_disclosed_at', '_revision_flag', '_populated_fields']
    return (ranked.sort_values(ordering, kind='stable', na_position='first')
            .drop_duplicates(keys, keep='last').drop(columns=ordering))


def _to_val(value):
    """将 NaN/None 转为 None"""
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if hasattr(value, "item"):
        value = value.item()
    if value is None:
        return None
    if isinstance(value, str) and value.strip() == "":
        return None
    return value
