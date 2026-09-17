"""Investment calendar API."""

from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, Query

from service.api.dependencies import get_investment_calendar_service
from service.investment_calendar import InvestmentCalendarService


router = APIRouter(prefix="/v1/investment-calendar", tags=["investment calendar"])


@router.get("")
def list_investment_events(
    start_date: date,
    end_date: date,
    importance: Literal["important", "high", "all"] = "important",
    country: str | None = Query(default=None, min_length=1, max_length=32),
    event_type: str | None = Query(default=None, min_length=1, max_length=32),
    service: InvestmentCalendarService = Depends(get_investment_calendar_service),
) -> dict:
    return service.list_events(
        start_date=start_date,
        end_date=end_date,
        importance=importance,
        country=country,
        event_type=event_type,
    )


@router.get("/{event_date}")
def investment_events_for_day(
    event_date: date,
    importance: Literal["important", "high", "all"] = "important",
    country: str | None = Query(default=None, min_length=1, max_length=32),
    event_type: str | None = Query(default=None, min_length=1, max_length=32),
    service: InvestmentCalendarService = Depends(get_investment_calendar_service),
) -> dict:
    return service.day_events(
        event_date,
        importance=importance,
        country=country,
        event_type=event_type,
    )
