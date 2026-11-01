"""Intraday observation status, history and watchlist controls."""

from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, Query

from service.api.dependencies import get_intraday_observation_service
from service.intraday.service import IntradayObservationService


router = APIRouter(prefix="/v1/intraday", tags=["intraday"])


class ObservationSetting(BaseModel):
    enabled: bool
    profile: str = "balanced"


@router.get("/overview")
def intraday_overview(
    history_limit: int = Query(default=120, ge=1, le=160),
    service: IntradayObservationService = Depends(get_intraday_observation_service),
) -> dict:
    return service.overview(history_limit=history_limit)


@router.post("/run")
def run_intraday_observation(
    service: IntradayObservationService = Depends(get_intraday_observation_service),
) -> dict:
    """Run one idempotent five-minute slot (an explicit quota-consuming action)."""

    return service.run(trigger_source="manual")


@router.put("/watchlist/{symbol}/observation")
def set_watchlist_observation(
    symbol: str,
    setting: ObservationSetting,
    service: IntradayObservationService = Depends(get_intraday_observation_service),
) -> dict:
    if setting.profile not in {"balanced", "sensitive", "conservative"}:
        raise HTTPException(status_code=422, detail="unsupported observation profile")
    try:
        return service.set_watchlist_observation(
            symbol, enabled=setting.enabled, profile=setting.profile,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
