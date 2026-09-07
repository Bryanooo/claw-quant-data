"""Interface-level collection completion overview."""

from fastapi import APIRouter, Depends

from service.api.dependencies import get_collection_monitor_service
from service.collection_monitor import CollectionMonitorService


router = APIRouter(prefix="/v1", tags=["collection monitoring"])


@router.get("/collection-overview")
def collection_overview(
    service: CollectionMonitorService = Depends(get_collection_monitor_service),
) -> dict:
    return service.overview()


@router.post("/collection-dispatch", status_code=202)
def dispatch_latest_collection_cycles() -> dict:
    from service.fanout_scheduling import submit_latest_scheduled_fanouts
    from service.tushare_scheduling import local_today, submit_latest_policy_batches

    today = local_today()
    submitted = submit_latest_policy_batches(today=today)
    fanout = submit_latest_scheduled_fanouts(today=today)
    return {
        "submitted": submitted,
        "fanout": fanout,
        "total": sum(submitted.values())
        + sum(item["created"] for item in fanout.values()),
    }
