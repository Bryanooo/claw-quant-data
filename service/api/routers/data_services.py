"""Unified discovery endpoint for public data-service layers."""

from fastapi import APIRouter

from service.api.dependencies import (
    DataServiceDependency,
    InterfaceDataServiceDependency,
    RawArchiveServiceDependency,
)
from service.api.schemas import DataServiceCatalogResponse
from service.data_service.catalog import build_data_service_catalog


router = APIRouter(prefix="/v1", tags=["service catalog"])


@router.get("/catalog", response_model=DataServiceCatalogResponse)
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


@router.get(
    "/data-services",
    response_model=DataServiceCatalogResponse,
    deprecated=True,
    summary="兼容的数据服务目录",
)
def legacy_data_service_catalog(
    raw_service: RawArchiveServiceDependency,
    data_service: DataServiceDependency,
    interface_service: InterfaceDataServiceDependency,
) -> dict:
    return data_service_catalog(raw_service, data_service, interface_service)
