"""Consolidated data-health endpoint for operators."""

from fastapi import APIRouter, Depends

from service.api.dependencies import get_data_health_service
from service.cache import TTLCache
from service.data_health import DataHealthService


router = APIRouter(prefix="/v1/ops", tags=["operations"])

# Health aggregates four repository roll-ups; it feeds both the dashboard poll
# and the system overview.  A 20-second TTL collapses those duplicate reads
# without hiding a fresh collection cycle.
_HEALTH_CACHE = TTLCache(ttl_seconds=20, max_entries=2)


@router.get("/data-health")
def data_health(
    service: DataHealthService = Depends(get_data_health_service),
    refresh: bool = False,
) -> dict:
    return _HEALTH_CACHE.get_or_compute("overview", service.overview, force=refresh)


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
