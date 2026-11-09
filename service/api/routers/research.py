"""Agent-oriented deterministic research endpoints."""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query

from service.api.dependencies import ResearchServiceDependency, get_data_health_service
from service.cache import TTLCache
from service.data_health import DataHealthService
from service.research.validation import validation_catalog
from service.research.factor_inputs import factor_input_catalog
from service.research.local_factors.service import (
    factor_catalog_payload,
    query_local_factor_values,
)


router = APIRouter(prefix="/v1/research", tags=["research"])

_CAPABILITIES_CACHE = TTLCache(ttl_seconds=120, max_entries=2)
_TECHNICALS_CACHE = TTLCache(ttl_seconds=60, max_entries=6)
_INSTRUMENT_TECHNICALS_CACHE = TTLCache(ttl_seconds=60, max_entries=12)


@router.get("/calendar")
def research_calendar(day: date, exchange: str = Query(default="SSE", pattern="^(SSE|SZSE)$")) -> dict:
    from service.tools.trade_cal import get_trade_calendar
    from service.research.calendar import session_from_rows
    return session_from_rows(day, exchange, get_trade_calendar(day.year, exchange=exchange))


@router.get("/validation-set")
def research_validation_set() -> dict:
    return validation_catalog()


@router.get("/capabilities")
def research_capabilities(service: ResearchServiceDependency) -> dict:
    # Capability discovery is static plus the lightweight backfill ledger.
    # Strict runtime data state has its own endpoint and is intentionally not
    # hidden behind (or recomputed by) catalog discovery.  The matrix walks
    # every technique and interface, so it is cached for two minutes.
    def build() -> dict:
        return service.capabilities()

    return _CAPABILITIES_CACHE.get_or_compute("capabilities", build)


@router.get("/factor-inputs")
def factor_inputs() -> dict:
    """Return versioned observation bundles consumable by factor-lab."""

    return factor_input_catalog()


@router.get("/factor-slices/csi300")
def csi300_factor_slice(day: date, factor: list[str] = Query(),
                       knowledge: str = Query("known_then", pattern="^(known_then|reconstructed)$")) -> dict:
    """One exact-date index universe; never drops securities with missing factors."""
    import psycopg2
    from service.research.index_slice import EvidenceUnavailable, build_slice

    try:
        return build_slice(day, factor, knowledge)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except EvidenceUnavailable as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (psycopg2.OperationalError, psycopg2.errors.QueryCanceled) as exc:
        raise HTTPException(status_code=503, detail="Research database unavailable or timed out") from exc


@router.get("/factors/local/catalog")
@router.get("/factors/catalog")
def local_factor_catalog(family: str | None = None) -> dict:
    """Discover the versioned local 272-factor ABI and overlap policy."""

    from service.data_service.factor_catalog import factor_catalog
    result = factor_catalog()
    if family:
        result = {**result, "factors": [f for f in result["factors"] if f["family"].casefold() == family.casefold()]}
        result["factor_count"] = len(result["factors"])
    return result


@router.get("/factors/local/{ts_code}")
@router.get("/factors/{ts_code}")
def local_factor_values(
    ts_code: str,
    factor: list[str] = Query(default=[]),
    start_date: date | None = None,
    end_date: date | None = None,
    limit: int = Query(default=500, ge=1, le=3000),
) -> dict:
    """Read selected factors directly from their array positions."""

    try:
        return query_local_factor_values(
            ts_code, names=factor, start_date=start_date,
            end_date=end_date, limit=limit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/readiness")
def research_readiness(
    service: DataHealthService = Depends(get_data_health_service),
) -> dict:
    """Return strict data state and a separate task execution state."""

    return service.research_readiness()


@router.get("/stocks/search")
def search_stocks(
    service: ResearchServiceDependency,
    q: str = Query(min_length=1, max_length=80),
    limit: int = Query(default=20, ge=1, le=30),
) -> dict:
    """Search stocks by exchange code, short name, full name or pinyin initials."""

    return service.search_stocks(q, limit=limit)


@router.get("/instruments/search")
def search_instruments(
    service: ResearchServiceDependency,
    q: str = Query(min_length=1, max_length=80),
    limit: int = Query(default=20, ge=1, le=30),
) -> dict:
    """Search stocks and exchange-traded funds in one unified lookup."""

    return service.search_instruments(q, limit=limit)


@router.get("/watchlist")
def stock_watchlist(service: ResearchServiceDependency) -> dict:
    """List durable stocks selected in the local research dashboard."""

    return service.stock_watchlist()


@router.post("/watchlist/{ts_code}")
def add_stock_watchlist(
    ts_code: str,
    service: ResearchServiceDependency,
) -> dict:
    return service.add_stock_watchlist(ts_code)


@router.delete("/watchlist/{ts_code}")
def remove_stock_watchlist(
    ts_code: str,
    service: ResearchServiceDependency,
) -> dict:
    return service.remove_stock_watchlist(ts_code)


@router.get("/stocks/{ts_code}/fundamentals")
def stock_fundamentals(
    ts_code: str,
    service: ResearchServiceDependency,
    periods: int = Query(default=12, ge=2, le=20),
    as_of: date | None = None,
    include_external: bool = True,
) -> dict:
    return service.fundamentals(
        ts_code.upper(), periods=periods, as_of=as_of,
        include_external=include_external,
    )


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


@router.get("/stocks/{ts_code}/analyst-revisions")
def stock_analyst_revisions(
    ts_code: str,
    service: ResearchServiceDependency,
    window_days: int = Query(default=90, ge=30, le=365),
    target_periods: int = Query(default=4, ge=1, le=8),
    as_of: date | None = None,
) -> dict:
    return service.analyst_revisions(
        ts_code.upper(), window_days=window_days,
        target_periods=target_periods, as_of=as_of,
    )


@router.get("/stocks/{ts_code}/ownership")
def stock_ownership_behavior(
    ts_code: str,
    service: ResearchServiceDependency,
    lookback_days: int = Query(default=1825, ge=365, le=3650),
    as_of: date | None = None,
) -> dict:
    return service.ownership_behavior(
        ts_code.upper(), lookback_days=lookback_days, as_of=as_of,
    )


@router.get("/stocks/{ts_code}/shareholder-return")
def stock_shareholder_return(
    ts_code: str,
    service: ResearchServiceDependency,
    lookback_days: int = Query(default=1825, ge=365, le=5000),
    as_of: date | None = None,
) -> dict:
    return service.shareholder_return(
        ts_code.upper(), lookback_days=lookback_days, as_of=as_of,
    )


_MARKET_CACHE = TTLCache(ttl_seconds=120, max_entries=8)
_DIRECTORY_CACHE = TTLCache(ttl_seconds=300, max_entries=8)


@router.get("/indices/{ts_code}/valuation-distribution")
def index_valuation_distribution(
    ts_code: str, trade_date: date, service: ResearchServiceDependency,
    report_period: date | None = None,
) -> dict:
    return service.group_valuation(ts_code.upper(), trade_date=trade_date,
                                   report_period=report_period)


@router.get("/indices/{ts_code}/valuation-distribution/snapshot")
def stored_index_valuation_distribution(
    ts_code: str, trade_date: date, service: ResearchServiceDependency,
) -> dict:
    return service.stored_group_valuation(ts_code.upper(), trade_date=trade_date)


@router.get("/indices/{ts_code}/valuation-distribution/history")
def index_valuation_distribution_history(
    ts_code: str, start: date, end: date, service: ResearchServiceDependency,
) -> dict:
    return service.group_valuation_history(ts_code.upper(), start=start, end=end)


@router.get("/indices/{ts_code}/valuation")
def index_valuation(
    ts_code: str,
    service: ResearchServiceDependency,
    lookback_days: int = Query(default=750, ge=120, le=3000),
    as_of: date | None = None,
) -> dict:
    key = ("index-valuation", ts_code.upper(), lookback_days, str(as_of))

    def build() -> dict:
        return service.index_valuation(
            ts_code.upper(), lookback_days=lookback_days, as_of=as_of,
        )

    return _MARKET_CACHE.get_or_compute(key, build)


@router.get("/market/funds")
def market_funds(
    service: ResearchServiceDependency,
    days: int = Query(default=120, ge=20, le=500),
    as_of: date | None = None,
) -> dict:
    key = ("market-funds", days, str(as_of))

    def build() -> dict:
        return service.market_funds(days=days, as_of=as_of)

    return _MARKET_CACHE.get_or_compute(key, build)


@router.get("/etfs/directory")
def etf_directory(
    service: ResearchServiceDependency,
    limit: int = Query(default=150, ge=10, le=500),
    as_of: date | None = None,
) -> dict:
    key = ("etf-directory", limit, str(as_of))

    def build() -> dict:
        return service.etf_directory(limit=limit, as_of=as_of)

    return _DIRECTORY_CACHE.get_or_compute(key, build)


@router.get("/etfs/{ts_code}/nav-shares")
def etf_nav_shares(
    ts_code: str,
    service: ResearchServiceDependency,
    lookback_days: int = Query(default=400, ge=60, le=2000),
    as_of: date | None = None,
) -> dict:
    key = ("etf-nav-shares", ts_code.upper(), lookback_days, str(as_of))

    def build() -> dict:
        return service.etf_nav_shares(
            ts_code.upper(), lookback_days=lookback_days, as_of=as_of,
        )

    return _MARKET_CACHE.get_or_compute(key, build)


@router.get("/sectors/directory")
def sector_directory(
    service: ResearchServiceDependency,
    source: str = Query(default="ths", pattern=r"^(ths|dc)$"),
    limit: int = Query(default=400, ge=10, le=1000),
    as_of: date | None = None,
) -> dict:
    key = ("sector-directory", source, limit, str(as_of))

    def build() -> dict:
        return service.sector_directory(source=source, limit=limit, as_of=as_of)

    return _DIRECTORY_CACHE.get_or_compute(key, build)


@router.get("/sectors/alipay-hot-plates")
def alipay_hot_plates(
    service: ResearchServiceDependency,
    limit: int = Query(default=50, ge=5, le=200),
    as_of: date | None = None,
) -> dict:
    key = ("alipay-hot-plates", limit, str(as_of))

    def build() -> dict:
        return service.alipay_hot_plates(limit=limit, as_of=as_of)

    return _MARKET_CACHE.get_or_compute(key, build)


@router.get("/sectors/{ts_code}/members")
def sector_members(
    ts_code: str,
    service: ResearchServiceDependency,
    source: str = Query(default="ths", pattern=r"^(ths|dc)$"),
    limit: int = Query(default=150, ge=10, le=500),
    as_of: date | None = None,
) -> dict:
    key = ("sector-members", source, ts_code.upper(), limit, str(as_of))

    def build() -> dict:
        return service.sector_members(
            ts_code.upper(), source=source, limit=limit, as_of=as_of,
        )

    return _MARKET_CACHE.get_or_compute(key, build)


@router.get("/stocks/{ts_code}/technicals")
def stock_technicals(
    ts_code: str,
    service: ResearchServiceDependency,
    lookback_days: int = Query(default=3000, ge=60, le=10000),
    chart_points: int = Query(default=120, ge=30, le=10000),
    benchmark: str = Query(default="399006.SZ", pattern=r"^[0-9A-Za-z.]{4,16}$"),
    as_of: date | None = None,
    include_external: bool = True,
    include_realtime: bool = True,
    include_chart_alias: bool = True,
) -> dict:
    key = (
        ts_code.upper(), lookback_days, chart_points, benchmark.upper(),
        str(as_of), include_external, include_realtime, include_chart_alias,
    )

    def build() -> dict:
        return service.technicals(
            ts_code.upper(), lookback_days=lookback_days, chart_points=chart_points,
            benchmark=benchmark.upper(), as_of=as_of,
            include_external=include_external,
            include_realtime=include_realtime,
            include_chart_alias=include_chart_alias,
        )

    return _TECHNICALS_CACHE.get_or_compute(key, build)


@router.get("/instruments/{asset_type}/{code}/technicals")
def instrument_technicals(
    asset_type: str,
    code: str,
    service: ResearchServiceDependency,
    lookback_days: int = Query(default=3000, ge=60, le=5000),
    chart_points: int = Query(default=120, ge=30, le=1500),
    benchmark: str | None = Query(
        default=None, pattern=r"^[0-9A-Za-z.]{4,16}$"
    ),
    provider: str | None = Query(default=None, pattern=r"^[a-zA-Z0-9_-]{2,16}$"),
    as_of: date | None = None,
) -> dict:
    """Return one multi-timeframe contract for stock/index/ETF/sector/spot."""

    normalized_code = code if asset_type.lower() == "spot" else code.upper()
    # Include every semantic input: asset/provider and point-in-time boundaries
    # must never share cached results accidentally. Single flight also prevents
    # repeated clicks from starting duplicate DB reads and indicator calculations.
    key = (
        asset_type.lower(), normalized_code, lookback_days, chart_points,
        benchmark.upper() if benchmark else None, provider, str(as_of),
    )
    return _INSTRUMENT_TECHNICALS_CACHE.get_or_compute(
        key,
        lambda: service.instrument_technicals(
            asset_type, normalized_code, lookback_days=lookback_days,
            chart_points=chart_points,
            benchmark=benchmark.upper() if benchmark else None,
            provider=provider, as_of=as_of,
        ),
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


@router.get("/stocks/{ts_code}/repurchase-progress")
def stock_repurchase_progress(
    ts_code: str,
    service: ResearchServiceDependency,
    benchmark: str = Query(default="399006.SZ", pattern=r"^[0-9A-Za-z.]{4,16}$"),
    as_of: date | None = None,
) -> dict:
    return service.repurchase_progress(
        ts_code.upper(), benchmark=benchmark.upper(), as_of=as_of
    )


@router.get("/stocks/{ts_code}/chips")
def stock_chips(
    ts_code: str,
    service: ResearchServiceDependency,
    lookback_days: int = Query(default=120, ge=20, le=500),
    as_of: date | None = None,
) -> dict:
    return service.stock_chips(
        ts_code.upper(), lookback_days=lookback_days, as_of=as_of
    )


@router.get("/stocks/{ts_code}/events")
def stock_events(
    ts_code: str,
    service: ResearchServiceDependency,
    lookback_days: int = Query(default=365, ge=30, le=1825),
    as_of: date | None = None,
) -> dict:
    return service.stock_events(
        ts_code.upper(), lookback_days=lookback_days, as_of=as_of
    )


@router.get("/stocks/{ts_code}/sector-context")
def stock_sector_context(
    ts_code: str,
    service: ResearchServiceDependency,
    provider: str = Query(default="ths", pattern=r"^(ths|dc|tdx)$"),
    lookback_days: int = Query(default=20, ge=5, le=60),
    as_of: date | None = None,
) -> dict:
    return service.stock_sector_context(
        ts_code.upper(), provider=provider,
        lookback_days=lookback_days, as_of=as_of,
    )


@router.get("/stocks/{ts_code}/industry-chain")
def stock_industry_chain(
    ts_code: str,
    service: ResearchServiceDependency,
    as_of: date | None = None,
) -> dict:
    return service.stock_industry_chain(ts_code.upper(), as_of=as_of)


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


@router.get("/market/technical-screen")
def market_technical_screen(
    service: ResearchServiceDependency,
    preset: str = Query(
        default="trend",
        pattern=r"^(trend|breakout|oversold-reversal|volume-breakout)$",
    ),
    limit: int = Query(default=50, ge=1, le=200),
    minimum_amount_thousand_yuan: float = Query(default=0, ge=0),
    exclude_st: bool = True,
    as_of: date | None = None,
) -> dict:
    """Return ranked candidates with universe coverage and audit evidence."""

    return service.technical_screen(
        preset=preset,
        limit=limit,
        minimum_amount_thousand_yuan=minimum_amount_thousand_yuan,
        exclude_st=exclude_st,
        as_of=as_of,
    )


@router.get("/macro/regime")
def macro_regime(
    service: ResearchServiceDependency,
    as_of: date | None = None,
) -> dict:
    """Return a transparent growth/inflation/liquidity regime snapshot."""

    return service.macro_regime(as_of=as_of)


@router.get("/macro/rates")
def macro_rates(
    service: ResearchServiceDependency,
    observations: int = Query(default=60, ge=2, le=250),
    as_of: date | None = None,
) -> dict:
    """Return official ChinaBond and US treasury curves plus the 10Y spread."""

    return service.macro_rates(observations=observations, as_of=as_of)


@router.get("/macro/schedule")
def macro_schedule(
    service: ResearchServiceDependency,
    limit: int = Query(default=60, ge=1, le=200),
    as_of: date | None = None,
) -> dict:
    """Return upcoming macro data release announcements."""

    return service.macro_schedule(limit=limit, as_of=as_of)


@router.get("/macro/{theme}")
def macro_theme(
    theme: str,
    service: ResearchServiceDependency,
    periods: int = Query(default=24, ge=2, le=120),
    as_of: date | None = None,
) -> dict:
    """Return bounded growth, inflation, or liquidity source series."""

    return service.macro_theme(theme, periods=periods, as_of=as_of)


@router.get("/etfs/flows")
def etf_flows(
    service: ResearchServiceDependency,
    lookback_observations: int = Query(default=5, ge=1, le=250),
    limit: int = Query(default=30, ge=1, le=100),
    as_of: date | None = None,
) -> dict:
    """Return creation/redemption proxies grouped by ETF exposure."""

    return service.etf_flows(
        lookback_observations=lookback_observations,
        limit=limit,
        as_of=as_of,
    )


@router.get("/etfs/state-team-signals")
def state_team_etf_signals(
    service: ResearchServiceDependency,
    lookback_observations: int = Query(default=5, ge=1, le=250),
    minimum_flow_yi: float = Query(default=5.0, ge=0.0, le=100000.0),
    limit: int = Query(default=30, ge=1, le=100),
    as_of: date | None = None,
) -> dict:
    """Return explicitly evidence-tiered ETF state-team candidates."""

    return service.state_team_etf_signals(
        lookback_observations=lookback_observations,
        minimum_flow_yi=minimum_flow_yi,
        limit=limit,
        as_of=as_of,
    )


@router.get("/etfs/flow-series")
def etf_flow_series(
    service: ResearchServiceDependency,
    lookback_days: int = Query(default=120, ge=10, le=750),
    min_flow_yi: float = Query(default=5.0, ge=0.0, le=100000.0),
    streak_days: int = Query(default=3, ge=2, le=30),
    as_of: date | None = None,
) -> dict:
    """Return the daily share-change and RMB-flow dual series for broad-base ETFs."""

    return service.etf_flow_series(
        lookback_days=lookback_days,
        min_flow_yi=min_flow_yi,
        streak_days=streak_days,
        as_of=as_of,
    )


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


# Supplemental public evidence shares the connector validation/cache boundary.
# It is intentionally separate from deterministic canonical research datasets.
from service.api.routers.sources import PublicQueryPayload, query_public_source, _endpoint_dict
from service.source_connectors.public_catalog import PUBLIC_ENDPOINTS


@router.get("/public-evidence/capabilities")
def public_evidence_capabilities() -> dict:
    return {"items": [_endpoint_dict(endpoint) for endpoint in PUBLIC_ENDPOINTS],
            "total": len(PUBLIC_ENDPOINTS), "evidence_only": True,
            "canonical": False, "point_in_time": False}


@router.post("/public-evidence/{source_id}/{endpoint_key}")
def public_research_evidence(source_id: str, endpoint_key: str, payload: PublicQueryPayload) -> dict:
    result = query_public_source(source_id, endpoint_key, payload)
    return {**result, "evidence_only": True, "canonical": False, "point_in_time": False}
