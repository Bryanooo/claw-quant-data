"""Provider-neutral, lossless acquisition evidence storage."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
import hashlib
import json
import math
from typing import Any, Callable, Iterable, Mapping

import pandas as pd
import psycopg2
import psycopg2.extras

from service.config import DB_CONFIG
from service.source_connectors.contracts import AcquisitionMode


_SENSITIVE_PARAMETER_NAMES = {
    "token", "access_token", "api_token", "password", "passwd", "secret", "api_key",
}


def json_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if hasattr(value, "item"):
        return json_value(value.item())
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    if isinstance(value, dict):
        return {str(key): json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_value(item) for item in value]
    if isinstance(value, str):
        return value.replace("\x00", "")
    return value


def canonical_json(value: Any) -> str:
    return json.dumps(
        json_value(value), ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    )


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def safe_parameters(parameters: Mapping[str, Any]) -> dict[str, Any]:
    def sensitive(name: str) -> bool:
        normalized = name.lower()
        return (
            normalized in _SENSITIVE_PARAMETER_NAMES
            or normalized.endswith(("_token", "_password", "_secret", "_key"))
            or normalized.startswith(("token_", "password_", "secret_"))
        )

    return {
        str(name): "[REDACTED]" if sensitive(str(name)) else json_value(value)
        for name, value in parameters.items()
    }


class SourceRawArchive:
    """Persist request, record and artifact evidence with source lineage."""

    def __init__(
        self,
        *,
        source_id: str,
        acquisition_mode: AcquisitionMode,
        source_doc_resolver: Callable[[str], int | None] | None = None,
        connection_factory: Callable[[], Any] | None = None,
        legacy_tushare: bool = False,
    ):
        self.source_id = source_id
        self.acquisition_mode = acquisition_mode
        self._source_doc_resolver = source_doc_resolver or (lambda _endpoint: None)
        self._legacy_tushare = legacy_tushare
        self._connection_factory = connection_factory or (
            lambda: psycopg2.connect(**DB_CONFIG)
        )

    @staticmethod
    def _records(
        frame: pd.DataFrame | None,
        records: Iterable[Mapping[str, Any]] | None,
    ) -> list[dict[str, Any]]:
        if frame is not None and records is not None:
            raise ValueError("provide either frame or records, not both")
        values = frame.to_dict(orient="records") if frame is not None else (records or ())
        return [json_value(dict(record)) for record in values]

    def archive_response(
        self,
        *,
        endpoint_key: str,
        parameters: Mapping[str, Any],
        collector_name: str,
        frame: pd.DataFrame | None = None,
        records: Iterable[Mapping[str, Any]] | None = None,
        persist_records: bool = True,
        requested_at: datetime | None = None,
    ) -> dict[str, Any]:
        safe = safe_parameters(parameters)
        logical = {key: value for key, value in safe.items() if key not in {"limit", "offset"}}
        request_hash = sha256_json(safe)
        logical_hash = sha256_json(logical)
        values = self._records(frame, records)
        response_hash = sha256_json(values)
        unique_records = {sha256_json(record): record for record in values}
        status = "empty" if not values else "success"
        source_doc_id = self._source_doc_resolver(endpoint_key)
        connection = self._connection_factory()
        try:
            with connection.cursor() as cursor:
                if self._legacy_tushare:
                    request_statement = """
                    INSERT INTO tushare_raw_request (
                        api_name, request_hash, logical_request_hash,
                        request_params, logical_request_params, collector_name,
                        status, row_count, response_hash, source_doc_id,
                        requested_at, completed_at
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW()
                    ) RETURNING request_id
                    """
                    request_values = (
                        endpoint_key, request_hash, logical_hash,
                        psycopg2.extras.Json(safe, dumps=canonical_json),
                        psycopg2.extras.Json(logical, dumps=canonical_json),
                        collector_name, status, len(values), response_hash,
                        source_doc_id, requested_at or datetime.now().astimezone(),
                    )
                else:
                    request_statement = """
                    INSERT INTO source_raw_request_store (
                        source_id, acquisition_mode, endpoint_key, request_hash,
                        logical_request_hash, request_params,
                        logical_request_params, collector_name, status,
                        row_count, response_hash, source_doc_id,
                        requested_at, completed_at
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, NOW()
                    ) RETURNING request_id
                    """
                    request_values = (
                        self.source_id, self.acquisition_mode.value, endpoint_key,
                        request_hash, logical_hash,
                        psycopg2.extras.Json(safe, dumps=canonical_json),
                        psycopg2.extras.Json(logical, dumps=canonical_json),
                        collector_name, status, len(values), response_hash,
                        source_doc_id, requested_at or datetime.now().astimezone(),
                    )
                cursor.execute(request_statement, request_values)
                request_id = int(cursor.fetchone()[0])
                if persist_records and unique_records:
                    rows, record_statement = self._record_insert(
                        endpoint_key=endpoint_key,
                        logical_hash=logical_hash,
                        logical_parameters=logical,
                        unique_records=unique_records,
                        source_doc_id=source_doc_id,
                    )
                    psycopg2.extras.execute_values(
                        cursor,
                        record_statement,
                        rows,
                        page_size=1000,
                    )
            connection.commit()
            return {
                "source_id": self.source_id,
                "endpoint_key": endpoint_key,
                "acquisition_mode": self.acquisition_mode.value,
                "request_id": request_id,
                "request_hash": request_hash,
                "logical_request_hash": logical_hash,
                "status": status,
                "row_count": len(values),
                "unique_record_count": len(unique_records),
                "records_persisted": bool(persist_records and unique_records),
                "response_hash": response_hash,
            }
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def archive_records(
        self,
        *,
        endpoint_key: str,
        parameters: Mapping[str, Any],
        frame: pd.DataFrame | None = None,
        records: Iterable[Mapping[str, Any]] | None = None,
    ) -> int:
        """Persist row payloads without manufacturing another provider request.

        Request-level evidence is written when the provider call completes.  In
        ``anomalies_only`` mode this method is invoked only if downstream
        validation or persistence fails, so the payload needed for diagnosis is
        retained without duplicating every successful business row forever.
        """
        safe = safe_parameters(parameters)
        logical = {
            key: value for key, value in safe.items() if key not in {"limit", "offset"}
        }
        values = self._records(frame, records)
        unique_records = {sha256_json(record): record for record in values}
        if not unique_records:
            return 0
        rows, statement = self._record_insert(
            endpoint_key=endpoint_key,
            logical_hash=sha256_json(logical),
            logical_parameters=logical,
            unique_records=unique_records,
            source_doc_id=self._source_doc_resolver(endpoint_key),
        )
        connection = self._connection_factory()
        try:
            with connection.cursor() as cursor:
                psycopg2.extras.execute_values(
                    cursor,
                    statement,
                    rows,
                    page_size=1000,
                )
            connection.commit()
            return len(rows)
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def resolve_records(
        self,
        *,
        endpoint_key: str,
        parameters: Mapping[str, Any],
    ) -> int:
        """Remove a quarantined payload after the same scope stores cleanly.

        Request-level lineage remains immutable. Only diagnostic row payloads
        are deleted, so ``anomalies_only`` describes unresolved anomalies
        instead of accumulating every transient failure forever.
        """
        safe = safe_parameters(parameters)
        logical = {
            key: value for key, value in safe.items() if key not in {"limit", "offset"}
        }
        request_hash = sha256_json(logical)
        connection = self._connection_factory()
        try:
            with connection.cursor() as cursor:
                if self._legacy_tushare:
                    cursor.execute(
                        "DELETE FROM tushare_raw_record "
                        "WHERE api_name=%s AND request_hash=%s",
                        (endpoint_key, request_hash),
                    )
                else:
                    cursor.execute(
                        "DELETE FROM source_raw_record_store "
                        "WHERE source_id=%s AND endpoint_key=%s "
                        "AND request_hash=%s",
                        (self.source_id, endpoint_key, request_hash),
                    )
                deleted = int(cursor.rowcount)
            connection.commit()
            return deleted
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _record_insert(
        self,
        *,
        endpoint_key: str,
        logical_hash: str,
        logical_parameters: Mapping[str, Any],
        unique_records: Mapping[str, Mapping[str, Any]],
        source_doc_id: int | None,
    ) -> tuple[list[tuple], str]:
        if self._legacy_tushare:
            rows = [
                (
                    endpoint_key,
                    logical_hash,
                    record_hash,
                    psycopg2.extras.Json(logical_parameters, dumps=canonical_json),
                    psycopg2.extras.Json(payload, dumps=canonical_json),
                    source_doc_id,
                )
                for record_hash, payload in unique_records.items()
            ]
            statement = """
                INSERT INTO tushare_raw_record (
                    api_name, request_hash, record_hash,
                    request_params, payload, source_doc_id
                ) VALUES %s
                ON CONFLICT (api_name, request_hash, record_hash)
                DO UPDATE SET payload=EXCLUDED.payload,
                    source_doc_id=EXCLUDED.source_doc_id,
                    collected_at=NOW(), last_seen_at=NOW()
            """
            return rows, statement
        rows = [
            (
                self.source_id,
                endpoint_key,
                logical_hash,
                record_hash,
                psycopg2.extras.Json(logical_parameters, dumps=canonical_json),
                psycopg2.extras.Json(payload, dumps=canonical_json),
                source_doc_id,
            )
            for record_hash, payload in unique_records.items()
        ]
        statement = """
            INSERT INTO source_raw_record_store (
                source_id, endpoint_key, request_hash, record_hash,
                request_params, payload, source_doc_id
            ) VALUES %s
            ON CONFLICT (source_id, endpoint_key, request_hash, record_hash)
            DO UPDATE SET payload=EXCLUDED.payload,
                source_doc_id=EXCLUDED.source_doc_id,
                collected_at=NOW(), last_seen_at=NOW()
        """
        return rows, statement

    def archive_failure(
        self,
        *,
        endpoint_key: str,
        parameters: Mapping[str, Any],
        collector_name: str,
        error: Exception,
        requested_at: datetime | None = None,
    ) -> None:
        safe = safe_parameters(parameters)
        logical = {key: value for key, value in safe.items() if key not in {"limit", "offset"}}
        connection = self._connection_factory()
        try:
            with connection.cursor() as cursor:
                if self._legacy_tushare:
                    statement = """
                    INSERT INTO tushare_raw_request (
                        api_name, request_hash, logical_request_hash,
                        request_params, logical_request_params, collector_name,
                        status, row_count, source_doc_id, error_message,
                        requested_at, completed_at
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, 'failed', 0, %s, %s, %s, NOW()
                    )
                    """
                    values = (
                        endpoint_key, sha256_json(safe), sha256_json(logical),
                        psycopg2.extras.Json(safe, dumps=canonical_json),
                        psycopg2.extras.Json(logical, dumps=canonical_json),
                        collector_name, self._source_doc_resolver(endpoint_key),
                        str(error)[:4000], requested_at or datetime.now().astimezone(),
                    )
                else:
                    statement = """
                    INSERT INTO source_raw_request_store (
                        source_id, acquisition_mode, endpoint_key, request_hash,
                        logical_request_hash, request_params,
                        logical_request_params, collector_name, status,
                        row_count, source_doc_id, error_message,
                        requested_at, completed_at
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, 'failed', 0,
                        %s, %s, %s, NOW()
                    )
                    """
                    values = (
                        self.source_id, self.acquisition_mode.value, endpoint_key,
                        sha256_json(safe), sha256_json(logical),
                        psycopg2.extras.Json(safe, dumps=canonical_json),
                        psycopg2.extras.Json(logical, dumps=canonical_json),
                        collector_name, self._source_doc_resolver(endpoint_key),
                        str(error)[:4000], requested_at or datetime.now().astimezone(),
                    )
                cursor.execute(statement, values)
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def archive_artifact(
        self,
        *,
        endpoint_key: str,
        content_type: str,
        content: bytes | None = None,
        storage_uri: str | None = None,
        source_url: str | None = None,
        http_status: int | None = None,
        response_headers: Mapping[str, Any] | None = None,
        parser_name: str | None = None,
        parser_version: str | None = None,
        request_id: int | None = None,
        fetched_at: datetime | None = None,
    ) -> dict[str, Any]:
        if content is None and storage_uri is None:
            raise ValueError("artifact content or storage_uri is required")
        digest_input = content if content is not None else storage_uri.encode("utf-8")
        digest = hashlib.sha256(digest_input).hexdigest()
        connection = self._connection_factory()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO source_raw_artifact (
                        source_id, endpoint_key, request_id, source_url,
                        content_type, content_hash, storage_uri, inline_content,
                        http_status, response_headers, parser_name,
                        parser_version, fetched_at
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                    ) ON CONFLICT (source_id, endpoint_key, content_hash)
                    DO UPDATE SET last_seen_at=NOW(),
                        response_headers=EXCLUDED.response_headers
                    RETURNING artifact_id
                    """,
                    (
                        self.source_id, endpoint_key, request_id, source_url,
                        content_type, digest, storage_uri, content, http_status,
                        psycopg2.extras.Json(
                            json_value(dict(response_headers or {})), dumps=canonical_json,
                        ),
                        parser_name, parser_version,
                        fetched_at or datetime.now().astimezone(),
                    ),
                )
                artifact_id = int(cursor.fetchone()[0])
            connection.commit()
            return {"artifact_id": artifact_id, "content_hash": digest}
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
