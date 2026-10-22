"""Unified discovery endpoint for public API namespaces and data layers."""

from fastapi import APIRouter

from service.api.dependencies import (
    DataServiceDependency,
    InterfaceDataServiceDependency,
    RawArchiveServiceDependency,
)
from service.api.schemas import DataServiceCatalogResponse
from service.cache import TTLCache
from service.data_service.catalog import build_data_service_catalog


router = APIRouter(prefix="/v1", tags=["catalog"])

# The catalog joins interface contracts, datasets and raw endpoints; it only
# changes when registries or migrations change, so a two-minute TTL is safe.
_CATALOG_CACHE = TTLCache(ttl_seconds=120, max_entries=2)


@router.get("/catalog", response_model=DataServiceCatalogResponse)
def data_service_catalog(
    raw_service: RawArchiveServiceDependency,
    data_service: DataServiceDependency,
    interface_service: InterfaceDataServiceDependency,
) -> dict:
    def build() -> dict:
        return build_data_service_catalog(
            raw_interfaces=raw_service.list_interfaces(),
            datasets=data_service.list_datasets(),
            interfaces=interface_service.list_interfaces(),
        )

    return _CATALOG_CACHE.get_or_compute("catalog", build)
