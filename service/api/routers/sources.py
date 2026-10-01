"""Provider-neutral source discovery and bounded query-through API."""

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from service.source_connectors.contracts import AcquisitionMode
from service.source_connectors.registry import SOURCE_REGISTRY
from service.source_connectors.contracts import ConnectorRequest
from service.source_connectors.financial_data import validate_common_query
from service.source_connectors.query_broker import QueryCircuitOpenError
from service.source_connectors.query_runtime import QUERY_BROKER


router = APIRouter(prefix="/v1/data/sources", tags=["data: sources"])
# Compatibility alias retained for tests and controlled dependency replacement.
_QUERY_BROKER = QUERY_BROKER


def _source_dict(source) -> dict:
    endpoints = SOURCE_REGISTRY.list_endpoints(source.source_id)
    return {
        "source_id": source.source_id,
        "display_name": source.display_name,
        "source_kind": source.kind.value,
        "acquisition_modes": [mode.value for mode in source.acquisition_modes],
        "base_url": source.base_url,
        "timezone": source.timezone,
        "credential_required": source.credential_ref is not None,
        "license_policy": dict(source.license_policy),
        "configuration": dict(source.configuration),
        "endpoint_count": len(endpoints),
    }


def _endpoint_dict(endpoint) -> dict:
    return {
        "source_id": endpoint.source_id,
        "endpoint_key": endpoint.endpoint_key,
        "title": endpoint.title,
        "acquisition_mode": endpoint.acquisition_mode.value,
        "resource_class": endpoint.resource_class,
        "cadence": endpoint.cadence,
        "parser_name": endpoint.parser_name,
        "parser_version": endpoint.parser_version,
        "cache_ttl_seconds": endpoint.cache_ttl_seconds,
        "request_contract": dict(endpoint.request_contract),
        "completeness_policy": dict(endpoint.completeness_policy),
    }


@router.get("")
def list_sources() -> dict:
    items = [_source_dict(item) for item in SOURCE_REGISTRY.list_sources()]
    return {"items": items, "total": len(items)}


@router.get("/{source_id}")
def describe_source(source_id: str) -> dict:
    return _source_dict(SOURCE_REGISTRY.get_source(source_id))


@router.get("/{source_id}/endpoints")
def list_source_endpoints(
    source_id: str,
    acquisition_mode: AcquisitionMode | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> dict:
    items = list(SOURCE_REGISTRY.list_endpoints(source_id))
    if acquisition_mode:
        items = [
            item for item in items
            if item.acquisition_mode == acquisition_mode
        ]
    total = len(items)
    return {
        "items": [_endpoint_dict(item) for item in items[offset:offset + limit]],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/{source_id}/endpoints/{endpoint_key}")
def describe_source_endpoint(source_id: str, endpoint_key: str) -> dict:
    return _endpoint_dict(SOURCE_REGISTRY.get_endpoint(source_id, endpoint_key))


@router.post("/financial_data/query")
def query_financial_data(payload: dict[str, Any]) -> dict:
    """Query the authenticated provider without exposing its credential."""
    try:
        # Validate locally before consulting the upstream circuit breaker.
        # A malformed or uncatalogued request is always a deterministic 422,
        # even while a prior upstream failure has the circuit open.
        normalized_payload = validate_common_query(payload)
        result = _QUERY_BROKER.query(ConnectorRequest(
            source_id="financial_data",
            endpoint_key="common_query",
            acquisition_mode=AcquisitionMode.QUERY_THROUGH,
            parameters=normalized_payload,
        ))
    except QueryCircuitOpenError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"financial-data upstream query failed: {type(exc).__name__}",
        ) from exc
    return {
        "data": dict(result.records[0]) if result.records else {},
        "meta": {
            "source_id": result.source_id,
            "status": result.status,
            "fetched_rows": result.fetched_rows,
            "evidence": dict(result.evidence),
            "warnings": list(result.warnings),
        },
    }
