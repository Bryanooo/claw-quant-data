"""Official ChinaMoney connector for authoritative LPR history."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
import json
from typing import Any, Callable, Mapping
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import psycopg2
import psycopg2.extras

from service.config import DB_CONFIG
from service.source_connectors.contracts import (
    AcquisitionMode,
    ConnectorRequest,
    ConnectorResult,
)
from service.source_connectors.raw_archive import SourceRawArchive, sha256_json
from service.source_connectors.registry import CHINAMONEY_SOURCE


_ENDPOINT_URL = (
    "https://www.chinamoney.com.cn/ags/ms/"
    "cm-u-bk-currency/LprHis"
)
_OFFICIAL_PAGE = "https://www.chinamoney.com.cn/chinese/bklpr/"


def _as_date(value: Any, name: str) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must use YYYY-MM-DD") from exc


def parse_lpr_payload(content: bytes) -> tuple[dict[str, Any], ...]:
    try:
        payload = json.loads(content.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("ChinaMoney LPR response is not valid UTF-8 JSON") from exc
    head = payload.get("head") or {}
    if str(head.get("rep_code")) != "200":
        raise ValueError(
            "ChinaMoney LPR request failed: "
            f"{head.get('rep_code')} {head.get('rep_message', '')}".strip()
        )
    records = payload.get("records")
    if not isinstance(records, list):
        raise ValueError("ChinaMoney LPR response has no records array")

    parsed = []
    for raw in records:
        if not isinstance(raw, Mapping):
            raise ValueError("ChinaMoney LPR record is not an object")
        missing = [name for name in ("showDateCN", "1Y", "5Y") if not raw.get(name)]
        if missing:
            raise ValueError(
                "ChinaMoney LPR record is missing fields: " + ", ".join(missing)
            )
        try:
            published = date.fromisoformat(str(raw["showDateCN"]))
            one_year = Decimal(str(raw["1Y"]))
            five_year = Decimal(str(raw["5Y"]))
        except (ValueError, InvalidOperation) as exc:
            raise ValueError("ChinaMoney LPR record has invalid values") from exc
        parsed.append({
            "publication_date": published,
            "one_year": one_year,
            "five_year": five_year,
            "raw": dict(raw),
        })
    return tuple(parsed)


class ChinaMoneyConnector:
    source = CHINAMONEY_SOURCE

    def __init__(
        self,
        *,
        fetcher: Callable[[date, date], tuple[bytes, str]] | None = None,
        archive: SourceRawArchive | None = None,
        store: Callable[[tuple[dict[str, Any], ...], dict[str, Any]], int] | None = None,
    ):
        self._fetcher = fetcher or self._fetch
        self._archive = archive or SourceRawArchive(
            source_id=self.source.source_id,
            acquisition_mode=AcquisitionMode.SCHEDULED_PULL,
        )
        self._store = store or self._store_records

    @staticmethod
    def _fetch(start: date, end: date) -> tuple[bytes, str]:
        query = urlencode({
            "lang": "CN",
            "strStartDate": start.isoformat(),
            "strEndDate": end.isoformat(),
        })
        url = f"{_ENDPOINT_URL}?{query}"
        request = Request(
            url,
            data=b"",
            method="POST",
            headers={
                "Accept": "application/json",
                "Referer": _OFFICIAL_PAGE,
                "User-Agent": "claw-quant-data/1.0",
            },
        )
        with urlopen(request, timeout=20) as response:
            status = int(response.status)
            content = response.read()
        if status < 200 or status >= 300:
            raise RuntimeError(f"ChinaMoney LPR endpoint returned HTTP {status}")
        if not content:
            raise RuntimeError("ChinaMoney LPR endpoint returned an empty response")
        return content, url

    @staticmethod
    def _store_records(
        records: tuple[dict[str, Any], ...], evidence: dict[str, Any]
    ) -> int:
        if not records:
            return 0
        rows = []
        for record in records:
            identity = {
                "source_id": "chinamoney",
                "publication_date": record["publication_date"],
            }
            rows.append((
                sha256_json(identity),
                evidence["request_hash"],
                evidence["request_id"],
                record["publication_date"],
                record["one_year"],
                record["five_year"],
                evidence["source_url"],
                psycopg2.extras.Json(record["raw"]),
            ))
        connection = psycopg2.connect(**DB_CONFIG)
        try:
            with connection.cursor() as cursor:
                psycopg2.extras.execute_values(
                    cursor,
                    """
                    INSERT INTO official_lpr (
                        record_hash, request_hash, source_request_id,
                        publication_date, one_year, five_year,
                        source_url, raw_payload
                    ) VALUES %s
                    ON CONFLICT (publication_date) DO UPDATE SET
                        record_hash=EXCLUDED.record_hash,
                        request_hash=EXCLUDED.request_hash,
                        source_request_id=EXCLUDED.source_request_id,
                        one_year=EXCLUDED.one_year,
                        five_year=EXCLUDED.five_year,
                        source_url=EXCLUDED.source_url,
                        raw_payload=EXCLUDED.raw_payload,
                        collected_at=NOW(),
                        last_seen_at=NOW()
                    """,
                    rows,
                )
            connection.commit()
        finally:
            connection.close()
        return len(rows)

    def execute(self, request: ConnectorRequest) -> ConnectorResult:
        if request.source_id != self.source.source_id:
            raise ValueError("request source does not match ChinaMoney connector")
        if request.endpoint_key != "lpr_history":
            raise ValueError("unsupported ChinaMoney endpoint")
        if request.acquisition_mode != AcquisitionMode.SCHEDULED_PULL:
            raise ValueError("ChinaMoney connector requires scheduled_pull mode")
        # Provider-neutral jobs carry endpoint arguments below ``parameters``
        # and execution controls (fields, pagination, resume) alongside it.
        # Keep accepting the flat shape for direct connector callers, while
        # treating the persisted job contract as the canonical shape.
        options = dict(request.parameters)
        endpoint_parameters = dict(options.get("parameters") or options)
        start = _as_date(endpoint_parameters.get("start_date"), "start_date")
        end = _as_date(endpoint_parameters.get("end_date"), "end_date")
        if start > end:
            raise ValueError("start_date must not be after end_date")

        content, source_url = self._fetcher(start, end)
        records = parse_lpr_payload(content)
        archive_records = [
            {
                "publication_date": item["publication_date"],
                "one_year": item["one_year"],
                "five_year": item["five_year"],
                "raw": item["raw"],
            }
            for item in records
        ]
        archived = self._archive.archive_response(
            endpoint_key=request.endpoint_key,
            parameters={
                "start_date": start,
                "end_date": end,
                "source_url": source_url,
            },
            collector_name=type(self).__name__,
            records=archive_records,
        )
        evidence = {
            **archived,
            "verified": True,
            "verification_type": "official_monthly_history_response",
            "source_url": source_url,
            "official_page": _OFFICIAL_PAGE,
            "parser_name": "chinamoney_lpr_json",
            "parser_version": "1",
            "requested_start": start.isoformat(),
            "requested_end": end.isoformat(),
        }
        stored = self._store(records, evidence)
        return ConnectorResult(
            source_id=request.source_id,
            endpoint_key=request.endpoint_key,
            acquisition_mode=request.acquisition_mode,
            records=archive_records,
            fetched_rows=len(records),
            stored_rows=stored,
            status="complete" if records else "empty",
            evidence=evidence,
        )
