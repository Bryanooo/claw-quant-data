"""Agent-oriented deterministic research endpoints."""

from datetime import date

from fastapi import APIRouter, Depends, Query

from service.api.dependencies import ResearchServiceDependency, get_data_health_service
from service.data_health import DataHealthService


router = APIRouter(prefix="/v1/research", tags=["research"])


@router.get("/capabilities")
def research_capabilities(service: ResearchServiceDependency) -> dict:
    return service.capabilities()


@router.get("/readiness")
def research_readiness(
    service: DataHealthService = Depends(get_data_health_service),
) -> dict:
    """Return bounded quality evidence without exposing the operations API."""

    payload = service.summary()
    payload["scope"] = "research_readiness"
    payload["capabilities_url"] = "/api/v1/research/capabilities"
    payload.pop("full_health_url", None)
    return payload


@router.get("/stocks/{ts_code}/fundamentals")
def stock_fundamentals(
    ts_code: str,
    service: ResearchServiceDependency,
    periods: int = Query(default=12, ge=2, le=20),
    as_of: date | None = None,
) -> dict:
    return service.fundamentals(ts_code.upper(), periods=periods, as_of=as_of)


@router.get("/stocks/{ts_code}/valuation")
def stock_valuation(
    ts_code: str,
    service: ResearchServiceDependency,
    lookback_days: int = Query(default=730, ge=60, le=1000),
    peer_limit: int = Query(default=20, ge=0, le=50),
    as_of: date | None = None,
) -> dict:
    return service.valuation(
        ts_code.upper(), lookback_days=lookback_days,
        peer_limit=peer_limit, as_of=as_of,
    )


@router.get("/stocks/{ts_code}/technicals")
def stock_technicals(
    ts_code: str,
    service: ResearchServiceDependency,
    lookback_days: int = Query(default=400, ge=60, le=1000),
    benchmark: str = Query(default="399006.SZ", pattern=r"^[0-9A-Za-z.]{4,16}$"),
    as_of: date | None = None,
) -> dict:
    return service.technicals(
        ts_code.upper(), lookback_days=lookback_days,
        benchmark=benchmark.upper(), as_of=as_of,
    )


@router.get("/stocks/{ts_code}/capital-flow")
def stock_capital_flow(
    ts_code: str,
    service: ResearchServiceDependency,
    lookback_days: int = Query(default=60, ge=5, le=250),
    as_of: date | None = None,
) -> dict:
    return service.capital_flow(
        ts_code.upper(), lookback_days=lookback_days, as_of=as_of,
    )


@router.get("/stocks/{ts_code}/event-study")
def stock_event_study(
    ts_code: str,
    service: ResearchServiceDependency,
    event_date: date = Query(),
    pre_days: int = Query(default=5, ge=0, le=60),
    post_days: int = Query(default=10, ge=0, le=120),
    benchmark: str = Query(default="399006.SZ", pattern=r"^[0-9A-Za-z.]{4,16}$"),
) -> dict:
    return service.event_study(
        ts_code.upper(), event_date=event_date,
        pre_days=pre_days, post_days=post_days,
        benchmark=benchmark.upper(),
    )


@router.get("/market/breadth")
def market_breadth(
    service: ResearchServiceDependency,
    as_of: date | None = None,
) -> dict:
    return service.market_breadth(as_of=as_of)


@router.get("/sectors/{provider}/rotation")
def sector_rotation(
    provider: str,
    service: ResearchServiceDependency,
    lookback_days: int = Query(default=60, ge=5, le=365),
    limit: int = Query(default=20, ge=1, le=100),
    as_of: date | None = None,
) -> dict:
    return service.sector_rotation(
        provider.lower(), lookback_days=lookback_days,
        limit=limit, as_of=as_of,
    )
