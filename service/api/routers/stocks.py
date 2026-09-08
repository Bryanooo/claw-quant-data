"""High-level stock endpoints."""

from datetime import date

from fastapi import APIRouter, Query

from service.api.dependencies import DataServiceDependency
from service.api.schemas import StockResearchPackResponse, StockSnapshotResponse

router = APIRouter(prefix="/v1/stocks", tags=["stocks"])


@router.get("/{ts_code}/snapshot", response_model=StockSnapshotResponse)
def stock_snapshot(
    ts_code: str,
    service: DataServiceDependency,
) -> dict:
    return service.stock_snapshot(ts_code.upper())


@router.get(
    "/{ts_code}/research-pack",
    response_model=StockResearchPackResponse,
)
def stock_research_pack(
    ts_code: str,
    service: DataServiceDependency,
    lookback_days: int = Query(default=180, ge=30, le=730),
    benchmark: str = Query(default="399006.SZ", pattern=r"^[0-9A-Za-z.]{4,16}$"),
    financial_periods: int = Query(default=8, ge=1, le=12),
    as_of: date | None = None,
) -> dict:
    return service.stock_research_pack(
        ts_code.upper(),
        lookback_days=lookback_days,
        benchmark=benchmark.upper(),
        financial_periods=financial_periods,
        as_of=as_of,
    )
