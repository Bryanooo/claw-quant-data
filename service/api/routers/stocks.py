"""High-level stock endpoints."""

from fastapi import APIRouter

from service.api.dependencies import DataServiceDependency
from service.api.schemas import StockSnapshotResponse

router = APIRouter(prefix="/v1/stocks", tags=["stocks"])


@router.get("/{ts_code}/snapshot", response_model=StockSnapshotResponse)
def stock_snapshot(
    ts_code: str,
    service: DataServiceDependency,
) -> dict:
    return service.stock_snapshot(ts_code.upper())
