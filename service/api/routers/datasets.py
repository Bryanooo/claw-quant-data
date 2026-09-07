"""Dataset discovery, querying and freshness endpoints."""

from fastapi import APIRouter, Query, Request

from service.api.dependencies import DataServiceDependency
from service.api.schemas import (
    DatasetDescription,
    DatasetSummary,
    FreshnessItem,
    RecordsResponse,
)

router = APIRouter(prefix="/v1", tags=["datasets"])

_STANDARD_QUERY_PARAMETERS = {
    "date",
    "start_date",
    "end_date",
    "limit",
    "offset",
    "include_total",
}


@router.get("/datasets", response_model=list[DatasetSummary])
def list_datasets(
    service: DataServiceDependency,
) -> list[dict]:
    return service.list_datasets()


@router.get("/freshness", response_model=list[FreshnessItem])
def get_freshness(
    service: DataServiceDependency,
    dataset: str | None = None,
) -> list[dict]:
    return service.freshness(dataset)


@router.get("/datasets/{dataset_name}", response_model=DatasetDescription)
def describe_dataset(
    dataset_name: str,
    service: DataServiceDependency,
) -> dict:
    return service.describe_dataset(dataset_name)


@router.get("/datasets/{dataset_name}/records", response_model=RecordsResponse)
def query_dataset(
    dataset_name: str,
    request: Request,
    service: DataServiceDependency,
    date_value: str | None = Query(default=None, alias="date"),
    start_date: str | None = None,
    end_date: str | None = None,
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    include_total: bool = False,
) -> dict:
    exact_filters: dict[str, str] = {}
    for name, value in request.query_params.multi_items():
        if name not in _STANDARD_QUERY_PARAMETERS:
            exact_filters[name] = value

    return service.query_dataset(
        dataset_name,
        exact_filters=exact_filters,
        date_value=date_value,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
        offset=offset,
        include_total=include_total,
    )
