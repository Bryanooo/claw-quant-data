"""Interface-level collection completion overview."""

from datetime import date

from fastapi import APIRouter, Depends, Query

from service.api.dependencies import (
    get_collection_monitor_service,
    get_delivery_monitor_service,
)
from service.collection_monitor import CollectionMonitorService
from service.delivery_monitor import DeliveryMonitorService


router = APIRouter(prefix="/v1", tags=["collection monitoring"])


@router.get("/collection-overview")
def collection_overview(
    service: CollectionMonitorService = Depends(get_collection_monitor_service),
) -> dict:
    return service.overview()


@router.get("/delivery/today")
def today_delivery_progress(
    business_date: date | None = Query(default=None),
    service: DeliveryMonitorService = Depends(get_delivery_monitor_service),
) -> dict:
    return service.today(business_date)


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
