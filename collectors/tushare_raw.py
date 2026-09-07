"""Catalog-driven collector for authorized Tushare interfaces.

Specialized collectors continue to own normalized business tables. This
collector provides complete read-interface coverage without manufacturing a
fragile table and hand-written class for every upstream endpoint.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import date, datetime
from decimal import Decimal
import hashlib
import json
import math
from typing import Any

import pandas as pd
import psycopg2.extras

from collectors.base import BaseCollector, get_db_conn, sanitize_postgres_value
from collectors.contracts import (
    EmptyPolicy,
    PaginationMode,
    ResourceClass,
    WriteMode,
)
from service.tushare_catalog import TushareInterfaceCatalog
from service.tushare_policy import TusharePolicyRegistry
from service.tushare_rate_limit import reserve_tushare_request
from service.tushare_normalization import (
    NormalizationIncompleteError,
    TushareNormalizer,
)


class IncompleteCollectionError(RuntimeError):
    """Raised instead of silently accepting a capped or stalled result."""

    retryable = False
    completion_status = "incomplete"


class PaginationStalledError(IncompleteCollectionError):
    pass


class CollectionScopeBusyError(RuntimeError):
    """Another worker is already collecting the same API request scope."""

    retryable = True
    retry_after_seconds = 30
    completion_status = "retrying"


_SUSPICIOUS_RESPONSE_CAPS = {
    1_000,
    2_000,
    3_000,
    4_000,
    5_000,
    6_000,
    7_000,
    10_000,
    15_000,
}


def collection_partition_supplied(strategy: str, params: dict[str, Any]) -> bool:
    """Return whether one request is bounded for its policy strategy."""
    candidates = {
        "trade_date": {
            "trade_date",
            "date",
            "cal_date",
            "ann_date",
            "nav_date",
            "ex_date",
            "start_date",
            "end_date",
        },
        "date_window": {"trade_date", "date", "start_date", "end_date"},
        "month": {"month", "m", "start_m", "end_m", "start_month", "end_month"},
        "report_period": {"period", "report_date", "end_date"},
        "week": {"week", "start_week", "end_week"},
        "ts_code_fanout": {"ts_code", "symbol", "code"},
        "dependency_fanout": {
            "factor_name",
            "name",
            "ts_code",
            "index_code",
            "con_code",
            "l1_code",
            "l2_code",
            "l3_code",
        },
    }
    required = candidates.get(strategy, set())
    return not required or bool(required & set(params))


def verify_complete_response(
    api_name: str,
    policy,
    params: dict[str, Any],
    fetched_rows: int,
) -> dict[str, Any]:
    """Prove that a non-offset response represents one complete request scope.

    This verifier is shared by raw and specialized collectors.  It deliberately
    fails closed when a specialized implementation would otherwise accept a
    capped response as complete.
    """
    if policy.pagination_mode == "offset":
        raise IncompleteCollectionError(
            f"{api_name} declares offset pagination; a single specialized "
            "request cannot prove completeness"
        )
    bounded = collection_partition_supplied(policy.parameter_strategy, params)
    if not bounded:
        raise IncompleteCollectionError(
            f"{api_name} requires a {policy.parameter_strategy} partition "
            "for complete collection"
        )
    limit = policy.documented_row_limit
    if limit and fetched_rows >= limit:
        raise IncompleteCollectionError(
            f"{api_name} returned the documented cap ({limit}); "
            "a narrower partition is required"
        )
    if not limit and fetched_rows in _SUSPICIOUS_RESPONSE_CAPS:
        raise IncompleteCollectionError(
            f"{api_name} returned a suspicious round cap ({fetched_rows}) "
            "without documented pagination; completeness cannot be proven"
        )
    return {
        "verified": True,
        "verification_type": "bounded_policy_scope",
        "mode": policy.pagination_mode,
        "parameter_strategy": policy.parameter_strategy,
        "documented_row_limit": limit,
        "bounded_partition": bounded,
        "rows_fetched": fetched_rows,
    }


def _json_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if hasattr(value, "item"):
        return _json_value(value.item())
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    if isinstance(value, str):
        return sanitize_postgres_value(value)[0]
    return value


def _canonical_json(value: Any) -> str:
    return json.dumps(
        _json_value(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


class CatalogRawCollector(BaseCollector):
    """Collect any catalog-authorized, read-only interface into raw JSON."""

    table_name = "tushare_raw_record"
    pk_columns = ["api_name", "request_hash", "record_hash"]
    supports_range_query = False
    write_mode = WriteMode.RAW_UPSERT
    pagination_mode = PaginationMode.PARTITIONED
    empty_policy = EmptyPolicy.REQUIRES_VERIFICATION
    resource_class = ResourceClass.GENERIC
    def __init__(self, api_name: str):
        self.contract = TushareInterfaceCatalog().require_collectable(api_name)
        self.policy = TusharePolicyRegistry().get(api_name)
        self.API_NAME = api_name
        self._request_parameters: dict[str, Any] = {}
        self._last_fetch_count = 0
        self._last_page_hash = ""
        self.completion_evidence: dict[str, Any] = {}
        self.normalization_evidence: dict[str, Any] = {
            "raw_rows": 0,
            "normalized_rows": 0,
            "quarantined_rows": 0,
            "unknown_fields": [],
            "missing_fields": [],
            "complete": True,
        }
        self.normalizer = TushareNormalizer()
        super().__init__()

    def _completion_evidence(self, **values: Any) -> dict[str, Any]:
        return {
            **values,
            "normalization": dict(self.normalization_evidence),
            "sanitization": self._sanitization_evidence(),
        }

    def _merge_normalization_evidence(self, evidence: dict[str, Any]) -> None:
        current = self.normalization_evidence
        for name in ("raw_rows", "normalized_rows", "quarantined_rows"):
            current[name] = int(current.get(name, 0)) + int(evidence.get(name, 0))
        for name in ("unknown_fields", "missing_fields"):
            current[name] = sorted(
                set(current.get(name, ())) | set(evidence.get(name, ()))
            )
        current["complete"] = int(current["quarantined_rows"]) == 0
        current["schema_version"] = evidence.get("schema_version")

    def fetch(self, **params) -> pd.DataFrame:
        if not getattr(self, "_distributed_rate_limit_installed", False):
            self._wait_for_rate_slot()
        # Pagination controls are transport details, not the logical request
        # identity. Keeping them out prevents duplicate raw records when page
        # size changes or the same row moves between pages.
        self._request_parameters = _json_value(
            {key: value for key, value in params.items() if key not in {"limit", "offset"}}
        )
        # query() is the stable SDK transport for dynamically selected api_name.
        frame = self.pro.query(self.API_NAME, **params)
        self._last_fetch_count = 0 if frame is None else len(frame)
        records = [] if frame is None else frame.to_dict(orient="records")
        self._last_page_hash = _sha256(records) if records else ""
        return frame

    def _wait_for_rate_slot(self) -> None:
        reserve_tushare_request(
            self.API_NAME,
            interface_interval=self.policy.min_interval_seconds,
        )

    @contextmanager
    def _scope_lock(self, scope_hash: str):
        """Hold one PostgreSQL session lock for the full pagination run."""
        connection = get_db_conn()
        acquired = False
        lock_name = f"tushare:{self.API_NAME}:{scope_hash}"
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT pg_try_advisory_lock(hashtextextended(%s, 0))",
                    (lock_name,),
                )
                acquired = bool(cursor.fetchone()[0])
            if not acquired:
                raise CollectionScopeBusyError(
                    f"{self.API_NAME} scope {scope_hash[:12]} is already running"
                )
            yield
        finally:
            if acquired:
                try:
                    with connection.cursor() as cursor:
                        cursor.execute(
                            "SELECT pg_advisory_unlock(hashtextextended(%s, 0))",
                            (lock_name,),
                        )
                finally:
                    connection.close()
            else:
                connection.close()

    def collect_complete(self, **params) -> int:
        """Collect one demonstrably complete request scope.

        Offset-capable interfaces are exhausted page by page. Partitioned
        interfaces must receive a date/month/security partition; an unbounded
        request is rejected because its completeness cannot be proven.
        """
        if self.policy.pagination_mode == "offset":
            return self.collect_paginated(**params)
        if not collection_partition_supplied(
            self.policy.parameter_strategy,
            params,
        ):
            raise IncompleteCollectionError(
                f"{self.API_NAME} requires a {self.policy.parameter_strategy} "
                "partition for complete collection"
            )
        rows = self.collect(**params)
        scope_evidence = verify_complete_response(
            self.API_NAME,
            self.policy,
            params,
            self._last_fetch_count,
        )
        self.completion_evidence = self._completion_evidence(
            **scope_evidence,
            request_hash=_sha256(_json_value(params)),
            rows_stored=rows,
        )
        return rows

    def collect_paginated(
        self,
        *,
        page_size: int | None = None,
        max_pages: int | None = None,
        resume: bool = True,
        **params,
    ) -> int:
        """Exhaust an offset interface with durable, idempotent checkpoints."""
        if self.policy.pagination_mode != "offset":
            raise IncompleteCollectionError(
                f"{self.API_NAME} does not declare offset pagination; "
                "use collect_complete with a bounded partition"
            )
        requested_size = page_size or self.policy.page_size
        requested_pages = max_pages or self.policy.max_pages
        if requested_size < 1 or requested_size > 10_000:
            raise ValueError("page_size must be between 1 and 10000")
        if requested_pages < 1 or requested_pages > 1_000:
            raise ValueError("max_pages must be between 1 and 1000")
        if "limit" in params or "offset" in params:
            raise ValueError("limit and offset are managed by collect_paginated")

        base_params = _json_value(params)
        scope_hash = _sha256(base_params)
        with self._scope_lock(scope_hash):
            return self._collect_paginated_scope(
                base_params,
                scope_hash,
                requested_size,
                requested_pages,
                resume=resume,
            )

    def _collect_paginated_scope(
        self,
        base_params: dict[str, Any],
        scope_hash: str,
        requested_size: int,
        requested_pages: int,
        *,
        resume: bool,
    ) -> int:
        checkpoint = self._begin_checkpoint(
            scope_hash,
            base_params,
            requested_size,
            resume=resume,
        )
        offset = int(checkpoint["next_offset"])
        pages = int(checkpoint["pages_completed"])
        fetched_total = int(checkpoint["rows_fetched"])
        stored_total = int(checkpoint["rows_stored"])
        previous_hash = checkpoint.get("last_page_hash") or ""
        seen_hashes = {previous_hash} if previous_hash else set()

        try:
            while pages < requested_pages:
                request = {**base_params, "limit": requested_size, "offset": offset}
                stored = self.collect(**request)
                fetched = self._last_fetch_count
                signature = self._last_page_hash
                if fetched == 0:
                    self.completion_evidence = self._completion_evidence(
                        verified=True,
                        mode="offset",
                        scope_hash=scope_hash,
                        page_size=requested_size,
                        pages_completed=pages,
                        rows_fetched=fetched_total,
                        rows_stored=stored_total,
                        exhausted=True,
                    )
                    self._finish_checkpoint(
                        scope_hash,
                        "success",
                        offset,
                        pages,
                        fetched_total,
                        stored_total,
                        previous_hash,
                    )
                    return stored_total
                if signature in seen_hashes:
                    raise PaginationStalledError(
                        f"{self.API_NAME} repeated earlier page content at offset {offset}; "
                        "the endpoint may ignore offset"
                    )

                offset += fetched
                pages += 1
                fetched_total += fetched
                stored_total += stored
                previous_hash = signature
                seen_hashes.add(signature)
                self._save_checkpoint(
                    scope_hash,
                    "running",
                    offset,
                    pages,
                    fetched_total,
                    stored_total,
                    previous_hash,
                )
                if fetched < requested_size:
                    self.completion_evidence = self._completion_evidence(
                        verified=True,
                        mode="offset",
                        scope_hash=scope_hash,
                        page_size=requested_size,
                        pages_completed=pages,
                        rows_fetched=fetched_total,
                        rows_stored=stored_total,
                        exhausted=True,
                    )
                    self._finish_checkpoint(
                        scope_hash,
                        "success",
                        offset,
                        pages,
                        fetched_total,
                        stored_total,
                        previous_hash,
                    )
                    return stored_total
            raise IncompleteCollectionError(
                f"{self.API_NAME} reached max_pages={requested_pages} before exhaustion"
            )
        except Exception as exc:
            self.completion_evidence = self._completion_evidence(
                verified=False,
                mode="offset",
                scope_hash=scope_hash,
                page_size=requested_size,
                pages_completed=pages,
                rows_fetched=fetched_total,
                rows_stored=stored_total,
                exhausted=False,
                error=str(exc),
            )
            exc.rows_inserted = stored_total
            exc.rows_fetched = fetched_total
            exc.completion_evidence = dict(self.completion_evidence)
            status = "partial" if isinstance(exc, IncompleteCollectionError) else "failed"
            self._save_checkpoint(
                scope_hash,
                status,
                offset,
                pages,
                fetched_total,
                stored_total,
                previous_hash,
                error=str(exc),
            )
            raise

    def _begin_checkpoint(
        self,
        scope_hash: str,
        base_params: dict[str, Any],
        page_size: int,
        *,
        resume: bool,
    ) -> dict[str, Any]:
        connection = get_db_conn()
        try:
            with connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                cursor.execute(
                    """
                    SELECT * FROM sys_tushare_collection_checkpoint
                    WHERE api_name = %s AND scope_hash = %s
                    FOR UPDATE
                    """,
                    (self.API_NAME, scope_hash),
                )
                row = cursor.fetchone()
                can_resume = bool(
                    resume
                    and row
                    and row["status"] in {"running", "partial", "failed"}
                    and row["page_size"] == page_size
                )
                if can_resume:
                    cursor.execute(
                        """
                        UPDATE sys_tushare_collection_checkpoint
                        SET status = 'running', last_error = NULL, updated_at = NOW()
                        WHERE api_name = %s AND scope_hash = %s
                        """,
                        (self.API_NAME, scope_hash),
                    )
                    result = dict(row)
                else:
                    cursor.execute(
                        """
                        INSERT INTO sys_tushare_collection_checkpoint (
                            api_name, scope_hash, base_params, status, page_size
                        ) VALUES (%s, %s, %s, 'running', %s)
                        ON CONFLICT (api_name, scope_hash) DO UPDATE SET
                            base_params = EXCLUDED.base_params,
                            status = 'running', next_offset = 0,
                            page_size = EXCLUDED.page_size, pages_completed = 0,
                            rows_fetched = 0, rows_stored = 0,
                            last_page_hash = NULL, last_error = NULL,
                            started_at = NOW(), updated_at = NOW(), completed_at = NULL
                        """,
                        (
                            self.API_NAME,
                            scope_hash,
                            psycopg2.extras.Json(base_params, dumps=_canonical_json),
                            page_size,
                        ),
                    )
                    result = {
                        "next_offset": 0,
                        "pages_completed": 0,
                        "rows_fetched": 0,
                        "rows_stored": 0,
                        "last_page_hash": None,
                    }
            connection.commit()
            return result
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _save_checkpoint(
        self,
        scope_hash: str,
        status: str,
        offset: int,
        pages: int,
        fetched: int,
        stored: int,
        page_hash: str,
        *,
        error: str | None = None,
    ) -> None:
        connection = get_db_conn()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE sys_tushare_collection_checkpoint
                    SET status = %s, next_offset = %s, pages_completed = %s,
                        rows_fetched = %s, rows_stored = %s,
                        last_page_hash = NULLIF(%s, ''), last_error = %s,
                        updated_at = NOW()
                    WHERE api_name = %s AND scope_hash = %s
                    """,
                    (
                        status,
                        offset,
                        pages,
                        fetched,
                        stored,
                        page_hash,
                        error,
                        self.API_NAME,
                        scope_hash,
                    ),
                )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _finish_checkpoint(self, scope_hash: str, *values: Any) -> None:
        self._save_checkpoint(scope_hash, *values)
        connection = get_db_conn()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE sys_tushare_collection_checkpoint
                    SET completed_at = NOW(), updated_at = NOW()
                    WHERE api_name = %s AND scope_hash = %s
                    """,
                    (self.API_NAME, scope_hash),
                )
            connection.commit()
        finally:
            connection.close()

    def store(self, df: pd.DataFrame) -> int:
        request_hash = _sha256(self._request_parameters)
        unique_rows: dict[str, dict[str, Any]] = {}
        for raw_record in df.to_dict(orient="records"):
            payload = _json_value(
                self._database_safe_value(raw_record, "payload")
            )
            unique_rows[_sha256(payload)] = payload
        if not unique_rows:
            return 0

        values = [
            (
                self.API_NAME,
                request_hash,
                record_hash,
                psycopg2.extras.Json(self._request_parameters, dumps=_canonical_json),
                psycopg2.extras.Json(payload, dumps=_canonical_json),
                self.contract.source_doc_id,
            )
            for record_hash, payload in unique_rows.items()
        ]
        connection = get_db_conn()
        try:
            with connection.cursor() as cursor:
                psycopg2.extras.execute_values(
                    cursor,
                    """
                    INSERT INTO tushare_raw_record (
                        api_name,
                        request_hash,
                        record_hash,
                        request_params,
                        payload,
                        source_doc_id
                    ) VALUES %s
                    ON CONFLICT (api_name, request_hash, record_hash)
                    DO UPDATE SET
                        payload = EXCLUDED.payload,
                        source_doc_id = EXCLUDED.source_doc_id,
                        collected_at = NOW(),
                        last_seen_at = NOW()
                    """,
                    values,
                    page_size=1000,
                )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

        self._normalize_stored_rows(
            request_hash,
            list(unique_rows.items()),
        )
        return len(values)

    def _normalize_stored_rows(
        self,
        request_hash: str,
        records: list[tuple[str, dict[str, Any]]],
    ) -> None:
        # Specialized interfaces own their existing domain tables. This
        # standardizer only materializes contracts explicitly classified as
        # generic_raw, preventing two writers from competing for one table.
        if self.contract.implementation.get("mode") != "generic_raw":
            return
        result = self.normalizer.normalize(
            self.API_NAME,
            request_hash,
            records,
            source_doc_id=self.contract.source_doc_id,
            strict_contract="fields" in self._request_parameters,
        )
        self._merge_normalization_evidence(result.as_evidence())
        if not result.complete:
            raise NormalizationIncompleteError(result)
        if "fields" in self._request_parameters:
            resolved = self.normalizer.resolve_superseded_scope(
                self.API_NAME,
                self._request_parameters,
            )
            self.normalization_evidence["resolved_legacy_errors"] = resolved
