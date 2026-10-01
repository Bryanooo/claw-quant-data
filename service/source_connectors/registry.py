"""Allow-listed source, endpoint and runtime connector registries."""

from __future__ import annotations

from collections.abc import Iterable
from threading import RLock

from service.source_connectors.contracts import (
    AcquisitionMode,
    EndpointSpec,
    SourceConnector,
    SourceKind,
    SourceSpec,
)


class SourceNotFoundError(LookupError):
    pass


class SourceEndpointNotFoundError(LookupError):
    pass


class SourceRegistry:
    def __init__(
        self,
        sources: Iterable[SourceSpec] = (),
        endpoints: Iterable[EndpointSpec] = (),
    ):
        self._sources: dict[str, SourceSpec] = {}
        self._endpoints: dict[tuple[str, str], EndpointSpec] = {}
        for source in sources:
            self.register_source(source)
        for endpoint in endpoints:
            self.register_endpoint(endpoint)

    def register_source(self, source: SourceSpec) -> None:
        if source.source_id in self._sources:
            raise ValueError(f"duplicate data source: {source.source_id}")
        if not source.acquisition_modes:
            raise ValueError("data source must declare at least one acquisition mode")
        self._sources[source.source_id] = source

    def register_endpoint(self, endpoint: EndpointSpec) -> None:
        source = self.get_source(endpoint.source_id)
        if endpoint.acquisition_mode not in source.acquisition_modes:
            raise ValueError(
                f"endpoint mode {endpoint.acquisition_mode} is not supported by "
                f"source {endpoint.source_id}"
            )
        key = (endpoint.source_id, endpoint.endpoint_key)
        if key in self._endpoints:
            raise ValueError(
                f"duplicate source endpoint: {endpoint.source_id}/{endpoint.endpoint_key}"
            )
        self._endpoints[key] = endpoint

    def get_source(self, source_id: str) -> SourceSpec:
        try:
            return self._sources[source_id]
        except KeyError as exc:
            raise SourceNotFoundError(f"unknown data source: {source_id}") from exc

    def get_endpoint(self, source_id: str, endpoint_key: str) -> EndpointSpec:
        try:
            return self._endpoints[(source_id, endpoint_key)]
        except KeyError as exc:
            raise SourceEndpointNotFoundError(
                f"unknown source endpoint: {source_id}/{endpoint_key}"
            ) from exc

    def list_sources(self) -> tuple[SourceSpec, ...]:
        return tuple(sorted(self._sources.values(), key=lambda item: item.source_id))

    def list_endpoints(self, source_id: str | None = None) -> tuple[EndpointSpec, ...]:
        if source_id is not None:
            self.get_source(source_id)
        return tuple(sorted(
            (
                item for item in self._endpoints.values()
                if source_id is None or item.source_id == source_id
            ),
            key=lambda item: (item.source_id, item.endpoint_key),
        ))


class ConnectorRegistry:
    def __init__(self):
        self._connectors: dict[str, SourceConnector] = {}
        self._lock = RLock()

    def register(self, connector: SourceConnector, *, replace: bool = False) -> None:
        source_id = connector.source.source_id
        with self._lock:
            if source_id in self._connectors and not replace:
                raise ValueError(f"connector already registered: {source_id}")
            self._connectors[source_id] = connector

    def get(self, source_id: str) -> SourceConnector:
        with self._lock:
            try:
                return self._connectors[source_id]
            except KeyError as exc:
                raise SourceNotFoundError(
                    f"no runtime connector registered for: {source_id}"
                ) from exc

    def __contains__(self, source_id: str) -> bool:
        with self._lock:
            return source_id in self._connectors


TUSHARE_SOURCE = SourceSpec(
    source_id="tushare",
    display_name="Tushare Pro",
    kind=SourceKind.API,
    acquisition_modes=(AcquisitionMode.SCHEDULED_PULL,),
    credential_ref="env:TUSHARE_TOKEN",
    base_url="https://api.tushare.pro",
    timezone="Asia/Shanghai",
    license_policy={"persist_raw_records": True},
    configuration={"adapter": "tushare"},
)


CHINAMONEY_SOURCE = SourceSpec(
    source_id="chinamoney",
    display_name="中国货币网（全国银行间同业拆借中心）",
    kind=SourceKind.API,
    acquisition_modes=(AcquisitionMode.SCHEDULED_PULL,),
    base_url="https://www.chinamoney.com.cn/ags/ms/",
    timezone="Asia/Shanghai",
    license_policy={
        "persist_raw_records": True,
        "official_public_data": True,
    },
    configuration={"adapter": "chinamoney"},
)


FINANCIAL_DATA_SOURCE = SourceSpec(
    source_id="financial_data",
    display_name="Financial Data Query",
    kind=SourceKind.API,
    acquisition_modes=(AcquisitionMode.QUERY_THROUGH,),
    credential_ref="env:FINANCIAL_DATA_API_KEY",
    base_url=(
        "https://dfdatamcpnexus-prod.antgroup-inc.cn/api/v1/common_query"
    ),
    timezone="Asia/Shanghai",
    license_policy={
        "persist_raw_records": False,
        "query_through_only": True,
    },
    configuration={
        "adapter": "financial_data",
        "api_version": "1.6.0",
        "catalog_discovered_routes": 163,
    },
)


def build_source_registry() -> SourceRegistry:
    registry = SourceRegistry((
        TUSHARE_SOURCE,
        CHINAMONEY_SOURCE,
        FINANCIAL_DATA_SOURCE,
    ))
    registry.register_endpoint(EndpointSpec(
        source_id="financial_data",
        endpoint_key="common_query",
        title="统一金融数据按需查询",
        acquisition_mode=AcquisitionMode.QUERY_THROUGH,
        resource_class="realtime_query",
        cache_ttl_seconds=15,
        request_contract={
            "modes": [
                "data", "tool_recall", "entity_recognition", "macro_recall",
                "macro_query", "onecode_recall", "onecode_query",
            ],
            "catalog_discovered_routes": 163,
            "catalog_is_lower_bound": True,
        },
        completeness_policy={
            "query_through": True,
            "success_does_not_imply_non_empty": True,
            "business_timestamp_required_for_realtime_claims": True,
        },
    ))
    registry.register_endpoint(EndpointSpec(
        source_id="chinamoney",
        endpoint_key="lpr_history",
        title="贷款市场报价利率（LPR）历史",
        acquisition_mode=AcquisitionMode.SCHEDULED_PULL,
        resource_class="generic",
        cadence="monthly",
        parser_name="chinamoney_lpr_json",
        parser_version="1",
        request_contract={
            "start_date": "YYYY-MM-DD",
            "end_date": "YYYY-MM-DD",
            "official_page": (
                "https://www.chinamoney.com.cn/chinese/bklpr/"
            ),
        },
        completeness_policy={
            "expected_frequency": "monthly",
            "required_fields": ["showDateCN", "1Y", "5Y"],
            "authoritative": True,
        },
    ))
    # Tushare remains the first adapter. Its existing machine-readable catalog
    # now populates the provider-neutral endpoint registry instead of becoming
    # the global data-source model.
    from service.tushare_catalog import TushareInterfaceCatalog
    from service.tushare_policy import TusharePolicyRegistry

    policies = TusharePolicyRegistry()
    for contract in TushareInterfaceCatalog().list():
        if not contract.collectable:
            continue
        policy = policies.get(contract.api_name)
        registry.register_endpoint(EndpointSpec(
            source_id="tushare",
            endpoint_key=contract.api_name,
            title=contract.title,
            acquisition_mode=AcquisitionMode.SCHEDULED_PULL,
            resource_class="generic",
            cadence=policy.cadence,
            request_contract={
                "document_ids": list(contract.document_ids),
                "implementation_mode": contract.implementation.get(
                    "mode", "unknown"
                ),
            },
            completeness_policy={
                "pagination_mode": policy.pagination_mode,
                "page_size": policy.page_size,
                "max_pages": policy.max_pages,
                "documented_row_limit": policy.documented_row_limit,
                "automatic_safe": policy.automatic_safe,
                "automatic_reason": policy.automatic_reason,
            },
        ))
    return registry


SOURCE_REGISTRY = build_source_registry()
SOURCE_CONNECTORS = ConnectorRegistry()
