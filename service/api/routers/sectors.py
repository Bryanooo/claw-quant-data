"""High-level sector discovery and research endpoints."""

from datetime import date

from fastapi import APIRouter, Query

from service.api.dependencies import DataServiceDependency
from service.api.schemas import (
    SectorListResponse,
    SectorMembersResponse,
    SectorResearchPackResponse,
    SectorSnapshotResponse,
)


router = APIRouter(prefix="/v1/sectors", tags=["sectors"])


@router.get("", response_model=SectorListResponse)
def list_sectors(
    service: DataServiceDependency,
    provider: str | None = Query(default=None, pattern=r"^(ths|dc|tdx)$"),
    query: str | None = Query(default=None, min_length=1, max_length=64),
    category: str | None = Query(default=None, min_length=1, max_length=32),
    market: str | None = Query(default=None, min_length=1, max_length=16),
    as_of: date | None = None,
    limit: int = Query(default=100, ge=1, le=500),
) -> dict:
    return service.list_sectors(
        provider=provider,
        query=query,
        category=category,
        market=market,
        as_of=as_of,
        limit=limit,
    )


@router.get(
    "/{provider}/{sector_code}/snapshot",
    response_model=SectorSnapshotResponse,
)
def sector_snapshot(
    provider: str,
    sector_code: str,
    service: DataServiceDependency,
    as_of: date | None = None,
) -> dict:
    return service.sector_snapshot(provider, sector_code.upper(), as_of=as_of)


@router.get(
    "/{provider}/{sector_code}/members",
    response_model=SectorMembersResponse,
)
def sector_members(
    provider: str,
    sector_code: str,
    service: DataServiceDependency,
    as_of: date | None = None,
    limit: int = Query(default=500, ge=1, le=5000),
) -> dict:
    return service.sector_members(
        provider,
        sector_code.upper(),
        as_of=as_of,
        limit=limit,
    )


@router.get(
    "/{provider}/{sector_code}/research-pack",
    response_model=SectorResearchPackResponse,
)
def sector_research_pack(
    provider: str,
    sector_code: str,
    service: DataServiceDependency,
    lookback_days: int = Query(default=180, ge=30, le=730),
    member_limit: int = Query(default=500, ge=1, le=2000),
    as_of: date | None = None,
) -> dict:
    return service.sector_research_pack(
        provider,
        sector_code.upper(),
        lookback_days=lookback_days,
        member_limit=member_limit,
        as_of=as_of,
    )
