"""Installation-time initial collection lifecycle endpoints."""

from typing import Annotated

from fastapi import APIRouter, Header, Query, Response, status

from service.api.dependencies import InitializationServiceDependency
from service.api.schemas import InitializationRequest


router = APIRouter(prefix="/v1/initialization", tags=["initialization"])
IdempotencyKey = Annotated[
    str | None,
    Header(alias="Idempotency-Key", min_length=8, max_length=128),
]


@router.get("")
def initialization_overview(service: InitializationServiceDependency) -> dict:
    return service.overview()


@router.post("/preflight")
def initialization_preflight(
    request: InitializationRequest,
    service: InitializationServiceDependency,
) -> dict:
    return service.preflight(
        profile=request.profile,
        history_start=request.history_start,
        history_end=request.history_end,
    )


@router.post("", status_code=status.HTTP_202_ACCEPTED)
def start_initialization(
    request: InitializationRequest,
    response: Response,
    service: InitializationServiceDependency,
    idempotency_key: IdempotencyKey = None,
) -> dict:
    campaign, created = service.start(
        profile=request.profile,
        history_start=request.history_start,
        history_end=request.history_end,
        auto_activate=request.auto_activate,
        idempotency_key=idempotency_key,
    )
    if not created:
        response.status_code = status.HTTP_200_OK
    return campaign


@router.get("/{initialization_id}")
def get_initialization(
    initialization_id: int,
    service: InitializationServiceDependency,
) -> dict:
    return service.get(initialization_id)


@router.get("/{initialization_id}/steps")
def get_initialization_steps(
    initialization_id: int,
    service: InitializationServiceDependency,
    limit: int = Query(default=500, ge=1, le=2000),
) -> list[dict]:
    return service.list_steps(initialization_id, limit=limit)


@router.post("/{initialization_id}/pause")
def pause_initialization(
    initialization_id: int,
    service: InitializationServiceDependency,
) -> dict:
    return service.pause(initialization_id)


@router.post("/{initialization_id}/resume")
def resume_initialization(
    initialization_id: int,
    service: InitializationServiceDependency,
) -> dict:
    return service.resume(initialization_id)


@router.post("/{initialization_id}/activate")
def activate_initialization(
    initialization_id: int,
    service: InitializationServiceDependency,
) -> dict:
    return service.activate(initialization_id)
