"""Read-through connector for the 蚂蚁数据源 Query unified API.

The provider exposes one authenticated HTTP endpoint.  The business URLs
returned by tool recall are nested request data, not independently callable
hosts.  Keeping that distinction in one connector prevents callers from
bypassing the allow-list, timeout, cache and circuit-breaker boundary.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable, Mapping

import requests

from service.config import (
    FINANCIAL_DATA_API_KEY,
    FINANCIAL_DATA_API_VERSION,
    FINANCIAL_DATA_BASE_URL,
    FINANCIAL_DATA_CONNECT_TIMEOUT_SECONDS,
    FINANCIAL_DATA_READ_TIMEOUT_SECONDS,
)
from service.source_connectors.contracts import (
    AcquisitionMode,
    ConnectorRequest,
    ConnectorResult,
)
from service.source_connectors.financial_data_catalog import FINANCIAL_DATA_ROUTES
from service.source_connectors.raw_archive import SourceRawArchive
from service.source_connectors.registry import FINANCIAL_DATA_SOURCE

_MODES = frozenset({
    "data",
    "tool_recall",
    "entity_recognition",
    "macro_recall",
    "macro_query",
    "onecode_recall",
    "onecode_query",
})
_QUERY_MODES = frozenset({"data", "macro_query", "onecode_query"})


class FinancialDataConfigurationError(RuntimeError):
    """The connector cannot authenticate because its local secret is absent."""


class FinancialDataProtocolError(RuntimeError):
    """The upstream response violates the documented common-query protocol."""


def validate_common_query(payload: Mapping[str, Any]) -> dict[str, Any]:
    mode = payload.get("mode")
    requests_payload = payload.get("requests")
    if mode not in _MODES:
        raise ValueError(f"unsupported financial-data mode: {mode!r}")
    if not isinstance(requests_payload, list) or not requests_payload:
        raise ValueError("financial-data requests must be a non-empty list")
    maximum = 30 if mode in {
        "macro_recall", "macro_query", "onecode_recall", "onecode_query"
    } else 1 if mode in {"tool_recall", "entity_recognition"} else 100
    if len(requests_payload) > maximum:
        raise ValueError(
            f"financial-data mode {mode} accepts at most {maximum} requests"
        )
    normalized: list[dict[str, Any]] = []
    for item in requests_payload:
        if not isinstance(item, Mapping):
            raise ValueError("each financial-data request must be an object")
        candidate = dict(item)
        parameters = candidate.get("params")
        if not isinstance(parameters, Mapping):
            raise ValueError("each financial-data request requires params")
        if mode == "data":
            url = candidate.get("url")
            if not isinstance(url, str) or url not in FINANCIAL_DATA_ROUTES:
                raise ValueError("data mode requires a route in the audited catalog")
            normalized.append({"url": url, "params": dict(parameters)})
        else:
            if set(candidate) != {"params"}:
                raise ValueError(f"mode {mode} accepts only a params object")
            normalized.append({"params": dict(parameters)})
    return {"mode": mode, "requests": normalized}


class FinancialDataConnector:
    source = FINANCIAL_DATA_SOURCE

    def __init__(
        self,
        *,
        api_key: str | None = None,
        transport: Callable[[dict[str, Any]], Mapping[str, Any]] | None = None,
        archive: SourceRawArchive | None = None,
    ):
        self._api_key = api_key if api_key is not None else FINANCIAL_DATA_API_KEY
        self._transport = transport or self._post
        self._archive = archive

    def _post(self, payload: dict[str, Any]) -> Mapping[str, Any]:
        if not self._api_key:
            raise FinancialDataConfigurationError(
                "ANT_DATA_API_KEY is not configured (legacy FINANCIAL_DATA_API_KEY is also supported)"
            )
        response = requests.post(
            FINANCIAL_DATA_BASE_URL,
            json=payload,
            headers={
                "X-API-Key": self._api_key,
                "X-API-Version": FINANCIAL_DATA_API_VERSION,
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "claw-quant-data/2",
            },
            timeout=(
                FINANCIAL_DATA_CONNECT_TIMEOUT_SECONDS,
                FINANCIAL_DATA_READ_TIMEOUT_SECONDS,
            ),
            allow_redirects=False,
        )
        response.raise_for_status()
        try:
            value = response.json()
        except ValueError as exc:
            raise FinancialDataProtocolError(
                "financial-data response is not valid JSON"
            ) from exc
        if not isinstance(value, Mapping):
            raise FinancialDataProtocolError(
                "financial-data response must be a JSON object"
            )
        return value

    def execute(self, request: ConnectorRequest) -> ConnectorResult:
        """Scheduled-pull path for the reviewed ant_norm_* route allow-list.

        Kept separate from ``query()`` on purpose: query-through stays
        bounded, unauthenticated-read shaped and never persists business
        rows, while the scheduled path enumerates partitions and writes the
        standard tables.  Imported lazily to avoid the protocol-helper
        import cycle.
        """
        if request.source_id != self.source.source_id:
            raise ValueError("request source does not match financial-data connector")
        if request.acquisition_mode != AcquisitionMode.SCHEDULED_PULL:
            raise ValueError(
                "financial-data scheduled execution requires scheduled_pull mode"
            )
        from service.source_connectors.ant_scheduled import (
            SCHEDULED_ROUTES,
            run_scheduled_pull,
        )

        spec = SCHEDULED_ROUTES.get(request.endpoint_key)
        if spec is None:
            raise ValueError(
                f"financial-data route {request.endpoint_key!r} is not on the "
                "scheduled-pull allow-list"
            )
        try:
            rows, evidence = run_scheduled_pull(spec, self._transport)
        except Exception as exc:
            if self._archive is not None:
                try:
                    self._archive.archive_failure(
                        endpoint_key=request.endpoint_key,
                        parameters={"route": spec.route},
                        collector_name="financial_data_scheduled_pull",
                        error=exc,
                    )
                except Exception:
                    pass
            raise
        return ConnectorResult(
            source_id=request.source_id,
            endpoint_key=request.endpoint_key,
            acquisition_mode=request.acquisition_mode,
            records=rows,
            fetched_rows=evidence["fetched_rows"],
            stored_rows=evidence["stored_rows"],
            status="complete" if evidence["fetched_rows"] else "empty",
            evidence=evidence,
        )

    def query(self, request: ConnectorRequest) -> ConnectorResult:
        if request.source_id != self.source.source_id:
            raise ValueError("request source does not match financial-data connector")
        if request.endpoint_key != "common_query":
            raise ValueError("unsupported financial-data endpoint")
        if request.acquisition_mode != AcquisitionMode.QUERY_THROUGH:
            raise ValueError("financial-data connector requires query_through mode")

        payload = validate_common_query(request.parameters)
        requested_at = datetime.now(timezone.utc)
        try:
            response = dict(self._transport(payload))
        except Exception as exc:
            if self._archive is not None:
                try:
                    self._archive.archive_failure(
                        endpoint_key="common_query",
                        parameters=payload,
                        collector_name="financial_data_query_through",
                        error=exc,
                        requested_at=requested_at,
                    )
                except Exception:
                    # Provider availability must not depend on audit-storage
                    # availability. The original provider error remains the
                    # actionable failure.
                    pass
            raise
        status = response.get("status")
        if status not in {"SUCCESS", "FAILED"}:
            raise FinancialDataProtocolError(
                "financial-data response has an invalid status"
            )
        fetched_rows = _result_row_count(payload["mode"], response)
        audit_warning = None
        if self._archive is not None:
            try:
                if status == "FAILED":
                    self._archive.archive_failure(
                        endpoint_key="common_query",
                        parameters=payload,
                        collector_name="financial_data_query_through",
                        error=FinancialDataProtocolError(
                            "provider reported FAILED"
                        ),
                        requested_at=requested_at,
                    )
                else:
                    self._archive.archive_response(
                        endpoint_key="common_query",
                        parameters=payload,
                        collector_name="financial_data_query_through",
                        records=(response,),
                        persist_records=False,
                        row_count_override=fetched_rows,
                        requested_at=requested_at,
                    )
            except Exception as exc:
                audit_warning = f"query audit unavailable: {type(exc).__name__}"
        return ConnectorResult(
            source_id=request.source_id,
            endpoint_key=request.endpoint_key,
            acquisition_mode=request.acquisition_mode,
            records=(response,),
            fetched_rows=fetched_rows,
            status="complete" if status == "SUCCESS" else "upstream_failed",
            evidence={
                "verified": True,
                "verification_type": "financial_data_common_query_protocol",
                "provider_status": status,
                "mode": payload["mode"],
                "request_count": len(payload["requests"]),
                "api_version": FINANCIAL_DATA_API_VERSION,
                "fetched_at": datetime.now(timezone.utc).isoformat(),
            },
            warnings=tuple(
                str(item.get("message") or item.get("code") or item)
                for item in response.get("issues", ())
                if isinstance(item, Mapping)
            ) + ((audit_warning,) if audit_warning else ()),
        )


def _result_row_count(mode: str, response: Mapping[str, Any]) -> int:
    if mode == "tool_recall":
        return len(response.get("tools") or ())
    if mode == "entity_recognition":
        return sum(len(item.get("data") or ()) for item in response.get("items") or ())
    return sum(len(item.get("data") or ()) for item in response.get("results") or ())
