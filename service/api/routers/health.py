"""Liveness and readiness endpoints."""

from fastapi import APIRouter, Request

from service.api.schemas import LiveResponse, ReadyResponse
from service.config import APP_VERSION

router = APIRouter(tags=["health"])


@router.get("/health/live", response_model=LiveResponse)
def live() -> dict:
    return {
        "status": "ok",
        "service": "claw-quant-data",
        "version": APP_VERSION,
    }


@router.get("/health/ready", response_model=ReadyResponse)
def ready(request: Request) -> dict:
    row = request.app.state.database.fetch_one("SELECT 1 AS ok")
    return {
        "status": "ready" if row and row["ok"] == 1 else "not_ready",
        "database": "ok" if row and row["ok"] == 1 else "unavailable",
    }
