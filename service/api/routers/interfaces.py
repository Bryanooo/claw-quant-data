"""Tushare interface discovery and raw-record query endpoints."""

from fastapi import APIRouter, Query, Request

from service.api.dependencies import InterfaceDataServiceDependency
from service.api.schemas import (
    InterfaceDescription,
    InterfaceRecordsResponse,
    InterfaceSummary,
)


router = APIRouter(prefix="/v1/interfaces", tags=["interfaces"])

_STANDARD_QUERY_PARAMETERS = {
    "date_field",
    "date",
    "start_date",
    "end_date",
    "limit",
    "offset",
    "include_total",
}


@router.get("", response_model=list[InterfaceSummary])
def list_interfaces(service: InterfaceDataServiceDependency) -> list[dict]:
    return service.list_interfaces()


@router.get("/{api_name}", response_model=InterfaceDescription)
def describe_interface(
    api_name: str,
    service: InterfaceDataServiceDependency,
) -> dict:
    return service.describe_interface(api_name)


@router.get("/{api_name}/records", response_model=InterfaceRecordsResponse)
def query_interface_records(
    api_name: str,
    request: Request,
    service: InterfaceDataServiceDependency,
    date_field: str | None = None,
    date_value: str | None = Query(default=None, alias="date"),
    start_date: str | None = None,
    end_date: str | None = None,
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    include_total: bool = False,
) -> dict:
    filters: dict[str, str] = {}
    for name, value in request.query_params.multi_items():
        if name not in _STANDARD_QUERY_PARAMETERS:
            filters[name] = value
    return service.query_records(
        api_name,
        filters=filters,
        date_field=date_field,
        date_value=date_value,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
        offset=offset,
        include_total=include_total,
    )
