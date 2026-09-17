"""Lossless Tushare request and payload audit endpoints."""

from datetime import datetime

from fastapi import APIRouter, Query

from service.api.dependencies import RawArchiveServiceDependency
from service.api.schemas import (
    RawCoverageResponse,
    RawInterfaceSummary,
    RawLineageResponse,
    RawRecordPageResponse,
    RawRequestPageResponse,
)


router = APIRouter(prefix="/v1/raw", tags=["raw-audit"])


@router.get("/interfaces", response_model=list[RawInterfaceSummary])
def list_raw_interfaces(service: RawArchiveServiceDependency) -> list[dict]:
    return service.list_interfaces()


@router.get("/{api_name}/requests", response_model=RawRequestPageResponse)
def list_raw_requests(
    api_name: str,
    service: RawArchiveServiceDependency,
    status: str | None = None,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
) -> dict:
    return service.list_requests(
        api_name,
        status=status,
        start_time=start_time,
        end_time=end_time,
        limit=limit,
        offset=offset,
    )


@router.get("/{api_name}/records", response_model=RawRecordPageResponse)
def list_raw_records(
    api_name: str,
    service: RawArchiveServiceDependency,
    request_hash: str | None = None,
    record_hash: str | None = None,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    include_total: bool = False,
) -> dict:
    return service.list_records(
        api_name,
        request_hash=request_hash,
        record_hash=record_hash,
        start_time=start_time,
        end_time=end_time,
        limit=limit,
        offset=offset,
        include_total=include_total,
    )


@router.get("/{api_name}/coverage", response_model=RawCoverageResponse)
def raw_coverage(api_name: str, service: RawArchiveServiceDependency) -> dict:
    return service.coverage(api_name)


@router.get("/{api_name}/lineage/{record_hash}", response_model=RawLineageResponse)
def raw_lineage(
    api_name: str,
    record_hash: str,
    service: RawArchiveServiceDependency,
    limit: int = Query(default=100, ge=1, le=1000),
) -> dict:
    return service.lineage(api_name, record_hash, limit=limit)
