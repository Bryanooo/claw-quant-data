"""Unified discovery endpoint for public data-service layers."""

from fastapi import APIRouter

from service.api.dependencies import (
    DataServiceDependency,
    InterfaceDataServiceDependency,
    RawArchiveServiceDependency,
)
from service.api.schemas import DataServiceCatalogResponse
from service.data_service.catalog import build_data_service_catalog


router = APIRouter(prefix="/v1/data-services", tags=["data services"])


@router.get("", response_model=DataServiceCatalogResponse)
def data_service_catalog(
    raw_service: RawArchiveServiceDependency,
    data_service: DataServiceDependency,
    interface_service: InterfaceDataServiceDependency,
) -> dict:
    return build_data_service_catalog(
        raw_interfaces=raw_service.list_interfaces(),
        datasets=data_service.list_datasets(),
        interfaces=interface_service.list_interfaces(),
    )
