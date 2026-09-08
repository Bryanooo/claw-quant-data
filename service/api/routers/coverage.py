"""Dataset date/report-partition coverage endpoints."""

from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Header, Query, Response, status

from service.api.dependencies import CoverageServiceDependency
from service.api.schemas import CoverageAuditRequest, CoverageRepairRequest

router = APIRouter(prefix="/v1/coverage", tags=["data coverage"])
IdempotencyKey = Annotated[
    str | None,
    Header(alias="Idempotency-Key", min_length=8, max_length=128),
]


@router.get("")
def coverage_overview(service: CoverageServiceDependency) -> dict:
    return service.overview()


@router.get("/datasets/{dataset_name}/partitions")
def coverage_partitions(
    dataset_name: str,
    service: CoverageServiceDependency,
    start_date: date | None = None,
    end_date: date | None = None,
    partition_status: Literal[
        "present", "partial", "missing", "pending", "observed_only", "problem"
    ] | None = Query(default=None, alias="status"),
    limit: int = Query(default=200, ge=1, le=1000),
) -> dict:
    return service.list_partitions(
        dataset_name,
        start_date=start_date,
        end_date=end_date,
        status=partition_status,
        limit=limit,
    )


@router.get("/jobs")
def coverage_jobs(
    service: CoverageServiceDependency,
    job_status: Literal["queued", "running", "success", "failed"] | None = Query(
        default=None,
        alias="status",
    ),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[dict]:
    return service.list_jobs(status=job_status, limit=limit)


@router.post("/audits", status_code=status.HTTP_202_ACCEPTED)
def submit_coverage_audits(
    request: CoverageAuditRequest,
    response: Response,
    service: CoverageServiceDependency,
    idempotency_key: IdempotencyKey = None,
) -> dict:
    result = service.submit_audits(
        request.datasets,
        start_date=request.start_date,
        end_date=request.end_date,
        idempotency_key=idempotency_key,
    )
    if result["created"] == 0:
        response.status_code = status.HTTP_200_OK
    return result


@router.post("/repairs", status_code=status.HTTP_202_ACCEPTED)
def submit_coverage_repairs(
    request: CoverageRepairRequest,
    response: Response,
    service: CoverageServiceDependency,
) -> dict:
    result = service.submit_repairs(
        request.dataset,
        start_date=request.start_date,
        end_date=request.end_date,
    )
    if result["created"] == 0:
        response.status_code = status.HTTP_200_OK
    return result
