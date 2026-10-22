"""Official ChinaBond (CCDC) connector for the yield curve scheduled pull.

Query-through reads stay on the shared public-web path (the chinabond
endpoint remains registered in ``public_catalog``), while this connector
implements the allow-listed ``SCHEDULED_PULL`` acquisition that persists
one row per (curve_date, curve_name) into
``public_norm_chinabond_yield_curve``.
"""

from __future__ import annotations

import math
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, Callable
from urllib.parse import urlencode

import psycopg2
import psycopg2.extras

from service.config import DB_CONFIG
from service.source_connectors.contracts import (
    AcquisitionMode,
    ConnectorRequest,
    ConnectorResult,
)
from service.source_connectors.raw_archive import SourceRawArchive, sha256_json
from service.source_connectors.registry import CHINABOND_SOURCE


_TENOR_COLUMNS = {
    "3m": "yield_3m",
    "6m": "yield_6m",
    "1y": "yield_1y",
    "3y": "yield_3y",
    "5y": "yield_5y",
    "7y": "yield_7y",
    "10y": "yield_10y",
    "30y": "yield_30y",
}

# One rolling window per scheduled run: wide enough to bridge long weekends
# and brief outages, narrow enough to stay inside the upstream 360-day cap.
_DEFAULT_WINDOW_DAYS = 14
_MAX_WINDOW_DAYS = 360


def _as_date(value: Any, name: str) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must use YYYY-MM-DD") from exc


def _store_records(
    records: tuple[dict[str, Any], ...], evidence: dict[str, Any]
) -> int:
    if not records:
        return 0
    rows = []
    for record in records:
        identity = {
            "curve_date": record["curve_date"],
            "curve_name": record["curve_name"],
        }
        rows.append((
            sha256_json(identity),
            evidence["request_hash"],
            evidence["request_id"],
            record["curve_date"],
            record["curve_name"],
            record["yield_3m"],
            record["yield_6m"],
            record["yield_1y"],
            record["yield_3y"],
            record["yield_5y"],
            record["yield_7y"],
            record["yield_10y"],
            record["yield_30y"],
            evidence["source_url"],
            psycopg2.extras.Json(record["raw"]),
        ))
    connection = psycopg2.connect(**DB_CONFIG)
    try:
        with connection.cursor() as cursor:
            psycopg2.extras.execute_values(
                cursor,
                """
                INSERT INTO public_norm_chinabond_yield_curve (
                    record_hash, request_hash, source_request_id,
                    curve_date, curve_name,
                    yield_3m, yield_6m, yield_1y, yield_3y,
                    yield_5y, yield_7y, yield_10y, yield_30y,
                    source_url, raw_payload
                ) VALUES %s
                ON CONFLICT (curve_date, curve_name) DO UPDATE SET
                    record_hash=EXCLUDED.record_hash,
                    request_hash=EXCLUDED.request_hash,
                    source_request_id=EXCLUDED.source_request_id,
                    yield_3m=EXCLUDED.yield_3m,
                    yield_6m=EXCLUDED.yield_6m,
                    yield_1y=EXCLUDED.yield_1y,
                    yield_3y=EXCLUDED.yield_3y,
                    yield_5y=EXCLUDED.yield_5y,
                    yield_7y=EXCLUDED.yield_7y,
                    yield_10y=EXCLUDED.yield_10y,
                    yield_30y=EXCLUDED.yield_30y,
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


class ChinaBondConnector:
    source = CHINABOND_SOURCE

    def __init__(
        self,
        *,
        fetcher: Callable[[date, date], list[dict[str, Any]]] | None = None,
        archive: SourceRawArchive | None = None,
        store: Callable[[tuple[dict[str, Any], ...], dict[str, Any]], int] | None = None,
    ):
        self._fetcher = fetcher or self._fetch
        self._archive = archive or SourceRawArchive(
            source_id=self.source.source_id,
            acquisition_mode=AcquisitionMode.SCHEDULED_PULL,
        )
        self._store = store or _store_records

    @staticmethod
    def _fetch(start: date, end: date) -> list[dict[str, Any]]:
        from service.source_connectors import public_parsers
        from service.source_connectors.public_web import BoundedTransport
        from service.source_connectors.public_parsers import chinabond_yield_curve

        token = public_parsers.TRANSPORT.set(BoundedTransport())
        try:
            frame = chinabond_yield_curve(
                start.isoformat(), end.isoformat(), curve="all"
            )
        finally:
            public_parsers.TRANSPORT.reset(token)
        return frame.to_dict("records")

    def query(self, request: ConnectorRequest) -> ConnectorResult:
        from service.source_connectors.public_web import PublicWebConnector

        return PublicWebConnector(self.source, archive=SourceRawArchive(
            source_id=self.source.source_id,
            acquisition_mode=AcquisitionMode.QUERY_THROUGH,
        )).query(request)

    def execute(self, request: ConnectorRequest) -> ConnectorResult:
        if request.source_id != self.source.source_id:
            raise ValueError("request source does not match ChinaBond connector")
        if request.endpoint_key != "yield_curve_history":
            raise ValueError("unsupported ChinaBond endpoint")
        if request.acquisition_mode != AcquisitionMode.SCHEDULED_PULL:
            raise ValueError("ChinaBond connector requires scheduled_pull mode")
        options = dict(request.parameters)
        endpoint_parameters = dict(options.get("parameters") or options)
        today = date.today()
        end = (
            _as_date(endpoint_parameters["end_date"], "end_date")
            if endpoint_parameters.get("end_date") else today
        )
        start = (
            _as_date(endpoint_parameters["start_date"], "start_date")
            if endpoint_parameters.get("start_date")
            else end - timedelta(days=_DEFAULT_WINDOW_DAYS)
        )
        if start > end:
            raise ValueError("start_date must not be after end_date")
        if (end - start).days > _MAX_WINDOW_DAYS:
            raise ValueError(
                f"ChinaBond window exceeds {_MAX_WINDOW_DAYS} days; split the range"
            )
        if end > today:
            raise ValueError("ChinaBond scheduled pull cannot request future dates")

        records = self._fetcher(start, end)
        normalized = []
        for item in records:
            def _finite(value: Any) -> Any:
                if isinstance(value, float) and not math.isfinite(value):
                    return None
                return value

            row = {
                "curve_date": _as_date(item["date"], "date"),
                "curve_name": str(item["curve"]),
                "raw": {
                    key: (
                        str(value)
                        if isinstance(value, Decimal)
                        else value.isoformat() if isinstance(value, date) else value
                    )
                    for key, value in item.items()
                },
            }
            for key, value in list(row["raw"].items()):
                if isinstance(value, float) and not math.isfinite(value):
                    row["raw"][key] = None
            for tenor, column in _TENOR_COLUMNS.items():
                value = _finite(item.get(tenor))
                row[column] = (
                    None if value is None else Decimal(str(value))
                )
            normalized.append(row)

        source_url = (
            f"https://yield.chinabond.com.cn/cbweb-pbc-web/pbc/historyQuery?"
            + urlencode({
                "startDate": start.isoformat(),
                "endDate": end.isoformat(),
                "gjqx": 0,
                "qxId": "ycqx",
                "locale": "cn_ZH",
            })
        )
        archived = self._archive.archive_response(
            endpoint_key=request.endpoint_key,
            parameters={
                "start_date": start,
                "end_date": end,
                "source_url": source_url,
            },
            collector_name=type(self).__name__,
            records=[
                {
                    "curve_date": row["curve_date"].isoformat(),
                    "curve_name": row["curve_name"],
                    "raw": row["raw"],
                }
                for row in normalized
            ],
        )
        evidence = {
            **archived,
            "verified": True,
            "verification_type": "official_history_response",
            "source_url": source_url,
            "official_page": "https://yield.chinabond.com.cn",
            "parser_name": "chinabond_yield_curve",
            "parser_version": "1",
            "rows_stored": self._store(tuple(normalized), {
                **archived,
                "source_url": source_url,
            }),
            "window": {"start_date": start.isoformat(), "end_date": end.isoformat()},
        }
        fetched = len(normalized)
        return ConnectorResult(
            source_id=request.source_id,
            endpoint_key=request.endpoint_key,
            acquisition_mode=AcquisitionMode.SCHEDULED_PULL,
            status="complete" if fetched else "empty",
            records=(),
            stored_rows=int(evidence["rows_stored"]),
            fetched_rows=fetched,
            evidence=evidence,
            warnings=[],
        )
