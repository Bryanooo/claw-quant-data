"""Provider-neutral source discovery and bounded query-through API."""

from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field
from service.source_connectors.public_catalog import PARAMETER_MODELS

from service.source_connectors.contracts import AcquisitionMode
from service.source_connectors.registry import SOURCE_REGISTRY
from service.source_connectors.contracts import ConnectorRequest
from service.source_connectors.financial_data import validate_common_query
from service.source_connectors.query_broker import QueryCircuitOpenError
from service.source_connectors.query_runtime import QUERY_BROKER
from service.research.external_provider import (
    FUNDAMENTAL_ROUTES,
    REALTIME_ROUTES,
    TECHNICAL_ROUTES,
)


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
        "capabilities": dict(endpoint.capabilities),
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


@router.post("/ant_data/query")
@router.post("/financial_data/query", deprecated=True)
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


@router.get("/ant_data/usage")
@router.get("/financial_data/usage", deprecated=True)
def financial_data_usage(
    request: Request,
    limit: int = Query(default=20, ge=1, le=100),
) -> dict:
    """Expose metadata-only provider usage; response payloads are never stored."""

    database = request.app.state.database
    summary = database.fetch_one(
        """
        SELECT count(*)::bigint AS requests,
               count(*) FILTER (WHERE status='success')::bigint AS successful,
               count(*) FILTER (WHERE status='empty')::bigint AS empty,
               count(*) FILTER (WHERE status='failed')::bigint AS failed,
               count(*) FILTER (
                   WHERE status='failed'
                     AND requested_at >= NOW() - INTERVAL '24 hours'
               )::bigint AS failed_last_24h,
               COALESCE(sum(row_count), 0)::bigint AS rows,
               min(requested_at) AS first_requested_at,
               max(requested_at) AS last_requested_at,
               (
                   SELECT latest.status
                   FROM source_raw_request_store AS latest
                   WHERE latest.source_id='financial_data'
                   ORDER BY latest.requested_at DESC, latest.request_id DESC
                   LIMIT 1
               ) AS latest_status
        FROM source_raw_request_store
        WHERE source_id='financial_data'
        """
    ) or {}
    routes = database.fetch_all(
        """
        SELECT item->>'url' AS route,
               count(*)::bigint AS batches,
               count(*) FILTER (WHERE audit.status IN ('success', 'empty'))::bigint
                   AS completed_batches,
               count(*) FILTER (WHERE audit.status='failed')::bigint AS failed_batches,
               max(audit.requested_at) AS last_requested_at
        FROM source_raw_request_store AS audit
        CROSS JOIN LATERAL jsonb_array_elements(
            COALESCE(audit.request_params->'requests', '[]'::jsonb)
        ) AS item
        WHERE audit.source_id='financial_data'
          AND item ? 'url'
        GROUP BY item->>'url'
        ORDER BY last_requested_at DESC, route
        LIMIT %s
        """,
        (limit,),
    )
    research_routes = sorted({
        *FUNDAMENTAL_ROUTES.values(),
        *TECHNICAL_ROUTES.values(),
        *REALTIME_ROUTES.values(),
    })
    return {
        "source_id": "financial_data",
        "persistence": "request_metadata_only",
        "status_scope": (
            "batch; individual routes may legitimately return no rows inside "
            "a successful batch"
        ),
        "summary": summary,
        "routes": routes,
        "research_integration": {
            "route_count": len(research_routes),
            "routes": research_routes,
            "contracts": [
                "/api/v1/research/stocks/{ts_code}/fundamentals",
                "/api/v1/research/stocks/{ts_code}/technicals",
                "/api/v1/research/stocks/{ts_code}/research-pack",
            ],
        },
    }




class PublicQueryPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    parameters: dict[str, Any] = Field(default_factory=dict)
    required_fields: list[str] = Field(default_factory=list, max_length=100)
    require_point_in_time: bool = False
    allow_stale: bool = False


@router.post("/{source_id}/endpoints/{endpoint_key}/query")
def query_public_source(source_id: str, endpoint_key: str, payload: PublicQueryPayload) -> dict:
    """Read an explicitly selected public endpoint, without equivalent-source fallback."""
    if (source_id, endpoint_key) not in PARAMETER_MODELS:
        raise HTTPException(status_code=404, detail="unknown public query endpoint")
    try:
        result = _QUERY_BROKER.query(
            ConnectorRequest(source_id=source_id, endpoint_key=endpoint_key,
                             acquisition_mode=AcquisitionMode.QUERY_THROUGH,
                             parameters=payload.parameters),
            required_fields=tuple(payload.required_fields),
            require_point_in_time=payload.require_point_in_time,
            allow_stale=payload.allow_stale,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except QueryCircuitOpenError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"public upstream query failed: {type(exc).__name__}") from exc
    return {"data": [dict(row) for row in result.records], "meta": {
        "source_id": result.source_id, "endpoint_key": result.endpoint_key,
        "status": result.status, "fetched_rows": result.fetched_rows,
        "evidence": dict(result.evidence), "warnings": list(result.warnings),
    }}


@router.get("/ant_data/route-contracts")
def ant_route_contracts(route: str | None = None) -> dict:
    """Discovered Ant route request/response contracts, independent of readiness."""
    import json
    from service.config import PROJECT_ROOT
    catalog = json.loads((PROJECT_ROOT / "docs/ant_data/route-contracts.json").read_text())
    if route is not None:
        catalog["routes"] = [item for item in catalog["routes"] if item["url"] == route]
    return {**catalog, "total": len(catalog["routes"])}
