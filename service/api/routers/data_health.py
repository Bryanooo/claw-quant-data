"""Consolidated data-health endpoint for operators."""

from fastapi import APIRouter, Depends

from service.api.dependencies import get_data_health_service
from service.data_health import DataHealthService


router = APIRouter(prefix="/v1/ops", tags=["operations"])


@router.get("/data-health")
def data_health(
    service: DataHealthService = Depends(get_data_health_service),
) -> dict:
    return service.overview()


@router.get("/data-health/summary")
def data_health_summary(
    service: DataHealthService = Depends(get_data_health_service),
) -> dict:
    return service.summary()


@router.get("/history-obligations")
def history_obligations(
    service: DataHealthService = Depends(get_data_health_service),
) -> dict:
    """Return initialization coverage by upstream interface, not job state."""
    return service.history_obligations()
