"""Collection task discovery, submission and monitoring endpoints."""

from dataclasses import asdict
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header, Query, Response, status

from service.api.dependencies import (
    CollectionJobServiceDependency,
    FanoutCampaignServiceDependency,
)
from service.api.schemas import (
    CollectionJobRequest,
    CollectionJobResponse,
    CollectionTaskSummary,
    FanoutBatchRequest,
    FanoutCampaignRequest,
)

router = APIRouter(prefix="/v1", tags=["collection jobs"])
IdempotencyKey = Annotated[
    str | None,
    Header(alias="Idempotency-Key", min_length=8, max_length=128),
]


@router.get("/collection-tasks", response_model=list[CollectionTaskSummary])
def list_collection_tasks(
    service: CollectionJobServiceDependency,
) -> list[dict]:
    return service.list_tasks()


@router.get("/collection-batches/fanout-definitions")
def list_fanout_definitions(
    service: CollectionJobServiceDependency,
) -> list[dict]:
    return service.list_fanout_definitions()


@router.post(
    "/collection-batches/fanout",
    response_model=CollectionJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def submit_fanout_batch(
    request: FanoutBatchRequest,
    response: Response,
    service: CollectionJobServiceDependency,
    idempotency_key: IdempotencyKey = None,
) -> dict:
    job, created = service.submit_fanout(
        request.model_dump(),
        idempotency_key=idempotency_key,
    )
    if not created:
        response.status_code = status.HTTP_200_OK
    return job


@router.get("/collection-fanout-campaigns")
def list_fanout_campaigns(
    service: FanoutCampaignServiceDependency,
    campaign_status: Literal[
        "running", "paused", "attention", "success", "superseded"
    ] | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[dict]:
    return service.list(status=campaign_status, limit=limit)


@router.get("/collection-fanout-schedules")
def list_scheduled_fanout_recipes() -> list[dict]:
    from service.fanout_scheduling import SCHEDULED_FANOUT_RECIPES

    return [asdict(recipe) for recipe in SCHEDULED_FANOUT_RECIPES]


@router.post(
    "/collection-fanout-campaigns",
    status_code=status.HTTP_202_ACCEPTED,
)
def submit_fanout_campaign(
    request: FanoutCampaignRequest,
    response: Response,
    service: FanoutCampaignServiceDependency,
    idempotency_key: IdempotencyKey = None,
) -> dict:
    campaign, created = service.submit(
        request.model_dump(), idempotency_key=idempotency_key
    )
    if not created:
        response.status_code = status.HTTP_200_OK
    return campaign


@router.get("/collection-fanout-campaigns/{campaign_id}")
def get_fanout_campaign(
    campaign_id: int,
    service: FanoutCampaignServiceDependency,
) -> dict:
    return service.get(campaign_id)


@router.post("/collection-fanout-campaigns/{campaign_id}/pause")
def pause_fanout_campaign(
    campaign_id: int,
    service: FanoutCampaignServiceDependency,
) -> dict:
    return service.pause(campaign_id)


@router.post("/collection-fanout-campaigns/{campaign_id}/resume")
def resume_fanout_campaign(
    campaign_id: int,
    service: FanoutCampaignServiceDependency,
) -> dict:
    return service.resume(campaign_id)


@router.post("/collection-fanout-campaigns/{campaign_id}/reconcile")
def reconcile_fanout_campaign(
    campaign_id: int,
    service: FanoutCampaignServiceDependency,
) -> dict:
    return service.reconcile(campaign_id)


@router.get("/collection-jobs", response_model=list[CollectionJobResponse])
def list_collection_jobs(
    service: CollectionJobServiceDependency,
    task_name: str | None = None,
    job_status: Literal["queued", "running", "success", "failed"] | None = Query(
        default=None,
        alias="status",
    ),
    api_name: str | None = Query(default=None, pattern=r"^[A-Za-z][A-Za-z0-9_]*$"),
    period_key: str | None = Query(default=None, max_length=32),
    completion_status: Literal[
        "pending", "running", "retrying", "complete", "empty",
        "verifying", "unverified", "incomplete", "failed",
    ] | None = None,
    parent_job_id: int | None = Query(default=None, ge=1),
    job_kind: Literal["leaf", "batch"] | None = None,
    limit: int = Query(default=50, ge=1, le=200),
) -> list[dict]:
    return service.list(
        task_name=task_name,
        status=job_status,
        api_name=api_name,
        period_key=period_key,
        completion_status=completion_status,
        parent_job_id=parent_job_id,
        job_kind=job_kind,
        limit=limit,
    )


@router.get(
    "/collection-jobs/{job_id}",
    response_model=CollectionJobResponse,
)
def get_collection_job(
    job_id: int,
    service: CollectionJobServiceDependency,
) -> dict:
    return service.get(job_id)


@router.post(
    "/collection-jobs",
    response_model=CollectionJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def submit_collection_job(
    request: CollectionJobRequest,
    response: Response,
    service: CollectionJobServiceDependency,
    idempotency_key: IdempotencyKey = None,
) -> dict:
    job, created = service.submit(
        request.task_name,
        request.parameters,
        max_attempts=request.max_attempts,
        idempotency_key=idempotency_key,
    )
    if not created:
        response.status_code = status.HTTP_200_OK
    return job


@router.post(
    "/collection-jobs/{job_id}/retry",
    response_model=CollectionJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def retry_collection_job(
    job_id: int,
    response: Response,
    service: CollectionJobServiceDependency,
    idempotency_key: IdempotencyKey = None,
) -> dict:
    job, created = service.retry(job_id, idempotency_key=idempotency_key)
    if not created:
        response.status_code = status.HTTP_200_OK
    return job
