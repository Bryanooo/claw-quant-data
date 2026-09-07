"""Typed standardization health, schema drift and quarantine endpoints."""

from fastapi import APIRouter, Query

from service.api.dependencies import NormalizationMonitorDependency
from service.api.schemas import (
    NormalizationDriftItem,
    NormalizationErrorItem,
    NormalizationOverview,
)


router = APIRouter(prefix="/v1/normalization", tags=["normalization"])


@router.get("", response_model=NormalizationOverview)
def overview(service: NormalizationMonitorDependency) -> dict:
    return service.overview()


@router.get("/drift", response_model=list[NormalizationDriftItem])
def drift(
    service: NormalizationMonitorDependency,
    api_name: str | None = None,
    unresolved_only: bool = True,
    limit: int = Query(default=100, ge=1, le=1000),
) -> list[dict]:
    return service.drift(
        api_name=api_name,
        unresolved_only=unresolved_only,
        limit=limit,
    )


@router.get("/errors", response_model=list[NormalizationErrorItem])
def errors(
    service: NormalizationMonitorDependency,
    api_name: str | None = None,
    unresolved_only: bool = True,
    limit: int = Query(default=100, ge=1, le=1000),
) -> list[dict]:
    return service.errors(
        api_name=api_name,
        unresolved_only=unresolved_only,
        limit=limit,
    )
