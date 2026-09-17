"""Read-only service for the lossless Tushare audit layer."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from service.data_service.models import InterfaceDataNotFoundError, InvalidQueryError
from service.tushare_catalog import InterfaceNotFoundError, TushareInterfaceCatalog


class RawArchiveRepository:
    def __init__(self, database):
        self._database = database

    def interface_stats(self, api_names: list[str]) -> list[dict]:
        return self._database.fetch_all(
            """
            WITH requested(api_name) AS (
                SELECT unnest(%s::text[])
            ), request_stats AS (
                SELECT api_name,
                       count(*)::bigint AS request_count,
                       count(*) FILTER (WHERE status='success')::bigint
                           AS successful_requests,
                       count(*) FILTER (WHERE status='empty')::bigint
                           AS empty_requests,
                       count(*) FILTER (WHERE status='failed')::bigint
                           AS failed_requests,
                       max(requested_at) AS latest_request_at
                FROM tushare_raw_request
                WHERE api_name = ANY(%s::text[])
                GROUP BY api_name
            )
            SELECT requested.api_name,
                   COALESCE(stats.request_count, 0) AS request_count,
                   COALESCE(stats.successful_requests, 0) AS successful_requests,
                   COALESCE(stats.empty_requests, 0) AS empty_requests,
                   COALESCE(stats.failed_requests, 0) AS failed_requests,
                   stats.latest_request_at,
                   EXISTS (
                       SELECT 1 FROM tushare_raw_record AS record
                       WHERE record.api_name=requested.api_name
                   ) AS has_records
            FROM requested
            LEFT JOIN request_stats AS stats USING (api_name)
            ORDER BY requested.api_name
            """,
            (api_names, api_names),
        )

    def requests(
        self,
        api_name: str,
        *,
        status: str | None,
        start_time: datetime | None,
        end_time: datetime | None,
        limit: int,
        offset: int,
    ) -> tuple[list[dict], int]:
        conditions = ["api_name=%s"]
        params: list[Any] = [api_name]
        if status:
            conditions.append("status=%s")
            params.append(status)
        if start_time:
            conditions.append("requested_at >= %s")
            params.append(start_time)
        if end_time:
            conditions.append("requested_at <= %s")
            params.append(end_time)
        where = " AND ".join(conditions)
        rows = self._database.fetch_all(
            f"""
            SELECT request_id, api_name, request_hash, logical_request_hash,
                   request_params, logical_request_params, collector_name,
                   status, row_count, response_hash, source_doc_id,
                   error_message, requested_at, completed_at
            FROM tushare_raw_request
            WHERE {where}
            ORDER BY requested_at DESC, request_id DESC
            LIMIT %s OFFSET %s
            """,
            (*params, limit, offset),
        )
        total_row = self._database.fetch_one(
            f"SELECT count(*)::bigint AS total FROM tushare_raw_request WHERE {where}",
            tuple(params),
        )
        return rows, int(total_row["total"] if total_row else 0)

    def records(
        self,
        api_name: str,
        *,
        request_hash: str | None,
        record_hash: str | None,
        start_time: datetime | None,
        end_time: datetime | None,
        limit: int,
        offset: int,
        include_total: bool,
    ) -> tuple[list[dict], int | None]:
        conditions = ["api_name=%s"]
        params: list[Any] = [api_name]
        if request_hash:
            conditions.append("request_hash=%s")
            params.append(request_hash)
        if record_hash:
            conditions.append("record_hash=%s")
            params.append(record_hash)
        if start_time:
            conditions.append("last_seen_at >= %s")
            params.append(start_time)
        if end_time:
            conditions.append("last_seen_at <= %s")
            params.append(end_time)
        where = " AND ".join(conditions)
        rows = self._database.fetch_all(
            f"""
            SELECT api_name, request_hash, record_hash, request_params,
                   payload, source_doc_id, collected_at, first_seen_at,
                   last_seen_at
            FROM tushare_raw_record
            WHERE {where}
            ORDER BY last_seen_at DESC, record_hash
            LIMIT %s OFFSET %s
            """,
            (*params, limit, offset),
        )
        total = None
        if include_total:
            total_row = self._database.fetch_one(
                f"SELECT count(*)::bigint AS total FROM tushare_raw_record WHERE {where}",
                tuple(params),
            )
            total = int(total_row["total"] if total_row else 0)
        return rows, total

    def coverage(self, api_name: str) -> dict:
        return self._database.fetch_one(
            """
            SELECT %s AS api_name,
                   (SELECT count(*)::bigint FROM tushare_raw_request
                    WHERE api_name=%s) AS request_count,
                   (SELECT count(*)::bigint FROM tushare_raw_request
                    WHERE api_name=%s AND status='success') AS successful_requests,
                   (SELECT count(*)::bigint FROM tushare_raw_request
                    WHERE api_name=%s AND status='empty') AS empty_requests,
                   (SELECT count(*)::bigint FROM tushare_raw_request
                    WHERE api_name=%s AND status='failed') AS failed_requests,
                   (SELECT count(*)::bigint FROM tushare_raw_record
                    WHERE api_name=%s) AS record_count,
                   (SELECT count(DISTINCT request_hash)::bigint
                    FROM tushare_raw_record WHERE api_name=%s)
                       AS logical_request_count,
                   (SELECT min(first_seen_at) FROM tushare_raw_record
                    WHERE api_name=%s) AS first_seen_at,
                   (SELECT max(last_seen_at) FROM tushare_raw_record
                    WHERE api_name=%s) AS last_seen_at,
                   (SELECT max(requested_at) FROM tushare_raw_request
                    WHERE api_name=%s) AS latest_request_at
            """,
            (api_name,) * 10,
        ) or {"api_name": api_name}

    def requests_for_logical_hashes(
        self,
        api_name: str,
        logical_hashes: list[str],
        *,
        limit: int,
    ) -> list[dict]:
        if not logical_hashes:
            return []
        return self._database.fetch_all(
            """
            SELECT request_id, api_name, request_hash, logical_request_hash,
                   request_params, logical_request_params, collector_name,
                   status, row_count, response_hash, source_doc_id,
                   error_message, requested_at, completed_at
            FROM tushare_raw_request
            WHERE api_name=%s AND logical_request_hash=ANY(%s::text[])
            ORDER BY requested_at DESC, request_id DESC
            LIMIT %s
            """,
            (api_name, logical_hashes, limit),
        )


class RawArchiveService:
    VALID_STATUSES = {"success", "empty", "failed"}

    def __init__(
        self,
        repository: RawArchiveRepository,
        catalog: TushareInterfaceCatalog | None = None,
    ):
        self._repository = repository
        self._catalog = catalog or TushareInterfaceCatalog()

    def list_interfaces(self) -> list[dict]:
        contracts = [item for item in self._catalog.list() if item.collectable]
        stats = {
            item["api_name"]: item
            for item in self._repository.interface_stats(
                [item.api_name for item in contracts]
            )
        }
        return [
            {
                "api_name": contract.api_name,
                "title": contract.title,
                "implementation_mode": contract.implementation.get("mode", "unknown"),
                "document_urls": [
                    f"https://tushare.pro/document/2?doc_id={doc_id}"
                    for doc_id in contract.document_ids
                ],
                **stats.get(
                    contract.api_name,
                    {
                        "request_count": 0,
                        "successful_requests": 0,
                        "empty_requests": 0,
                        "failed_requests": 0,
                        "latest_request_at": None,
                        "has_records": False,
                    },
                ),
            }
            for contract in contracts
        ]

    def list_requests(self, api_name: str, **query: Any) -> dict:
        self._require_collectable(api_name)
        status = query.get("status")
        if status and status not in self.VALID_STATUSES:
            raise InvalidQueryError(
                "raw request status must be success, empty, or failed"
            )
        rows, total = self._repository.requests(api_name, **query)
        return self._page(api_name, rows, query["limit"], query["offset"], total)

    def list_records(self, api_name: str, **query: Any) -> dict:
        self._require_collectable(api_name)
        for field in ("request_hash", "record_hash"):
            value = query.get(field)
            if value and (len(value) != 64 or any(ch not in "0123456789abcdef" for ch in value)):
                raise InvalidQueryError(f"{field} must be a lowercase SHA-256 hash")
        rows, total = self._repository.records(api_name, **query)
        return self._page(api_name, rows, query["limit"], query["offset"], total)

    def coverage(self, api_name: str) -> dict:
        contract = self._require_collectable(api_name)
        return {
            **self._repository.coverage(api_name),
            "implementation_mode": contract.implementation.get("mode", "unknown"),
            "document_urls": [
                f"https://tushare.pro/document/2?doc_id={doc_id}"
                for doc_id in contract.document_ids
            ],
        }

    def lineage(self, api_name: str, record_hash: str, *, limit: int = 100) -> dict:
        result = self.list_records(
            api_name,
            request_hash=None,
            record_hash=record_hash,
            start_time=None,
            end_time=None,
            limit=limit,
            offset=0,
            include_total=True,
        )
        logical_hashes = sorted({item["request_hash"] for item in result["data"]})
        requests = self._repository.requests_for_logical_hashes(
            api_name,
            logical_hashes,
            limit=limit,
        )
        return {
            "api_name": api_name,
            "record_hash": record_hash,
            "records": result["data"],
            "requests": requests,
        }

    def _require_collectable(self, api_name: str):
        try:
            contract = self._catalog.get(api_name)
        except InterfaceNotFoundError as exc:
            raise InterfaceDataNotFoundError(str(exc)) from exc
        if not contract.collectable:
            raise InvalidQueryError(f"interface {api_name} is not collectable")
        return contract

    @staticmethod
    def _page(
        api_name: str,
        rows: list[dict],
        limit: int,
        offset: int,
        total: int | None,
    ) -> dict:
        return {
            "data": rows,
            "meta": {"interface": api_name, "returned": len(rows)},
            "page": {
                "limit": limit,
                "offset": offset,
                "total": total,
                "has_more": (
                    offset + len(rows) < total
                    if total is not None
                    else len(rows) == limit
                ),
            },
        }
