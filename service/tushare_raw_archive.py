"""Lossless audit storage for every Tushare transport response.

The archive lives at the SDK ``query`` boundary.  This is intentionally before
collector transformation and business-table writes: malformed upstream rows
must remain inspectable even when the normalized collection attempt fails.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from functools import lru_cache
import hashlib
import json
import math
from typing import Any, Callable

import pandas as pd
import psycopg2
import psycopg2.extras

from service.config import DB_CONFIG
from service.tushare_catalog import InterfaceNotFoundError, TushareInterfaceCatalog


_SENSITIVE_PARAMETER_NAMES = {
    "token",
    "access_token",
    "api_token",
    "password",
    "passwd",
    "secret",
    "api_key",
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
        # PostgreSQL text/jsonb cannot contain NUL characters.
        return value.replace("\x00", "")
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


def _safe_parameters(parameters: dict[str, Any]) -> dict[str, Any]:
    def sensitive(name: str) -> bool:
        normalized = name.lower()
        return (
            normalized in _SENSITIVE_PARAMETER_NAMES
            or normalized.endswith(("_token", "_password", "_secret", "_key"))
            or normalized.startswith(("token_", "password_", "secret_"))
        )

    return {
        str(name): (
            "[REDACTED]"
            if sensitive(str(name))
            else _json_value(value)
        )
        for name, value in parameters.items()
    }


@lru_cache(maxsize=256)
def _source_doc_id(api_name: str) -> int | None:
    try:
        return TushareInterfaceCatalog().get(api_name).source_doc_id
    except InterfaceNotFoundError:
        return None


class TushareRawArchive:
    """Persist request evidence and deduplicated upstream records atomically."""

    def __init__(self, connection_factory: Callable[[], Any] | None = None):
        self._connection_factory = connection_factory or (
            lambda: psycopg2.connect(**DB_CONFIG)
        )

    def archive_response(
        self,
        *,
        api_name: str,
        parameters: dict[str, Any],
        frame: pd.DataFrame | None,
        collector_name: str,
        persist_records: bool = True,
        requested_at: datetime | None = None,
    ) -> dict[str, Any]:
        safe_parameters = _safe_parameters(parameters)
        logical_parameters = {
            key: value
            for key, value in safe_parameters.items()
            if key not in {"limit", "offset"}
        }
        request_hash = _sha256(safe_parameters)
        logical_request_hash = _sha256(logical_parameters)
        records = [] if frame is None else [
            _json_value(record) for record in frame.to_dict(orient="records")
        ]
        response_hash = _sha256(records)
        unique_records = {_sha256(record): record for record in records}
        status = "empty" if not records else "success"
        source_doc_id = _source_doc_id(api_name)

        connection = self._connection_factory()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO tushare_raw_request (
                        api_name, request_hash, logical_request_hash,
                        request_params, logical_request_params, collector_name,
                        status, row_count, response_hash, source_doc_id,
                        requested_at, completed_at
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW()
                    )
                    RETURNING request_id
                    """,
                    (
                        api_name,
                        request_hash,
                        logical_request_hash,
                        psycopg2.extras.Json(safe_parameters, dumps=_canonical_json),
                        psycopg2.extras.Json(logical_parameters, dumps=_canonical_json),
                        collector_name,
                        status,
                        len(records),
                        response_hash,
                        source_doc_id,
                        requested_at or datetime.now().astimezone(),
                    ),
                )
                request_id = int(cursor.fetchone()[0])
                if persist_records and unique_records:
                    values = [
                        (
                            api_name,
                            logical_request_hash,
                            record_hash,
                            psycopg2.extras.Json(
                                logical_parameters, dumps=_canonical_json
                            ),
                            psycopg2.extras.Json(payload, dumps=_canonical_json),
                            source_doc_id,
                        )
                        for record_hash, payload in unique_records.items()
                    ]
                    psycopg2.extras.execute_values(
                        cursor,
                        """
                        INSERT INTO tushare_raw_record (
                            api_name, request_hash, record_hash, request_params,
                            payload, source_doc_id
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
            return {
                "request_id": request_id,
                "request_hash": request_hash,
                "logical_request_hash": logical_request_hash,
                "status": status,
                "row_count": len(records),
                "unique_record_count": len(unique_records),
                "response_hash": response_hash,
            }
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def archive_failure(
        self,
        *,
        api_name: str,
        parameters: dict[str, Any],
        collector_name: str,
        error: Exception,
        requested_at: datetime | None = None,
    ) -> None:
        safe_parameters = _safe_parameters(parameters)
        logical_parameters = {
            key: value
            for key, value in safe_parameters.items()
            if key not in {"limit", "offset"}
        }
        connection = self._connection_factory()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO tushare_raw_request (
                        api_name, request_hash, logical_request_hash,
                        request_params, logical_request_params, collector_name,
                        status, row_count, source_doc_id, error_message,
                        requested_at, completed_at
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, 'failed', 0, %s, %s, %s, NOW()
                    )
                    """,
                    (
                        api_name,
                        _sha256(safe_parameters),
                        _sha256(logical_parameters),
                        psycopg2.extras.Json(safe_parameters, dumps=_canonical_json),
                        psycopg2.extras.Json(logical_parameters, dumps=_canonical_json),
                        collector_name,
                        _source_doc_id(api_name),
                        str(error)[:4000],
                        requested_at or datetime.now().astimezone(),
                    ),
                )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
