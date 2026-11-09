"""Liveness and readiness endpoints."""

from fastapi import APIRouter, Request, Response
from psycopg2 import Error as DatabaseError

from service.api.schemas import LiveResponse, ReadyResponse
from service.config import APP_VERSION
from service.schema_migrations import missing_migrations

router = APIRouter(prefix="/v1/ops/health", tags=["operations"])


@router.get("/live", response_model=LiveResponse)
def live() -> dict:
    return {
        "status": "ok",
        "service": "claw-quant-data",
        "version": APP_VERSION,
    }


@router.get("/ready", response_model=ReadyResponse, response_model_exclude_none=True)
def ready(request: Request, response: Response) -> dict:
    try:
        missing = missing_migrations(request.app.state.database.fetch_all)
    except DatabaseError:
        response.status_code = 503
        return {"status": "not_ready", "database": "unavailable"}
    if missing:
        response.status_code = 503
        return {"status": "not_ready", "database": "ok", "missing_migrations": missing}
    return {"status": "ready", "database": "ok"}
