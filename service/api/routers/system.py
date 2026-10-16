"""Canonical system overview for operators and maintainers."""

from fastapi import APIRouter, Depends

from service.api.dependencies import (
    DataServiceDependency,
    InterfaceDataServiceDependency,
    RawArchiveServiceDependency,
    get_data_health_service,
)
from service.data_health import DataHealthService
from service.data_service.catalog import build_data_service_catalog
from service.system_overview import build_system_overview


router = APIRouter(prefix="/v1/system", tags=["system"])


@router.get("/overview")
def system_overview(
    raw_service: RawArchiveServiceDependency,
    data_service: DataServiceDependency,
    interface_service: InterfaceDataServiceDependency,
    health_service: DataHealthService = Depends(get_data_health_service),
) -> dict:
    public_catalog = build_data_service_catalog(
        raw_interfaces=raw_service.list_interfaces(),
        datasets=data_service.list_datasets(),
        interfaces=interface_service.list_interfaces(),
    )
    return build_system_overview(
        public_catalog=public_catalog,
        data_health=health_service.overview(),
    )
