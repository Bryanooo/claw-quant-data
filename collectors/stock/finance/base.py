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
from collectors.base import BaseCollector
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
        result = result.drop_duplicates(subset=self.PK_COLUMNS, keep="last")
        logger.info("  [%s] %s complete: %s 行", self.INTERFACE_NAME, period, len(result))
        return result

    def store(self, df):
        """Normalize the selected output schema and use the shared UPSERT sink."""
        if df is None or len(df) == 0:
            return 0
        normalized = df.reindex(columns=self.CORE_FIELDS).map(_to_val)
        rows = super().store(normalized)
        periods = sorted(df["end_date"].unique()) if "end_date" in df.columns else ["?"]
        logger.info(f"  ✅ {self.TABLE_NAME} {periods}: upsert {rows} 行")
        return rows

    def save(self, df):
        """Deprecated compatibility alias for :meth:`store`."""
        return self.store(df)


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
