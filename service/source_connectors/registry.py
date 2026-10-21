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
        source_id = "financial_data" if source_id == "ant_data" else source_id
        try:
            return self._sources[source_id]
        except KeyError as exc:
            raise SourceNotFoundError(f"unknown data source: {source_id}") from exc

    def get_endpoint(self, source_id: str, endpoint_key: str) -> EndpointSpec:
        source_id = "financial_data" if source_id == "ant_data" else source_id
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
            source_id = self.get_source(source_id).source_id
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
    configuration={
        "adapter": "tushare",
        "business_scope": "证券、基金、指数、宏观等批量基础数据",
    },
)


CHINAMONEY_SOURCE = SourceSpec(
    source_id="chinamoney",
    display_name="中国货币网（全国银行间同业拆借中心）",
    kind=SourceKind.API,
    acquisition_modes=(AcquisitionMode.SCHEDULED_PULL, AcquisitionMode.QUERY_THROUGH),
    base_url="https://www.chinamoney.com.cn/ags/ms/",
    timezone="Asia/Shanghai",
    license_policy={
        "persist_raw_records": True,
        "official_public_data": True,
    },
    configuration={
        "adapter": "chinamoney",
        "business_scope": "中国贷款市场报价利率（LPR）历史及 FR/FDR 定盘利率",
        "canonical_datasets": ["cn_lpr"],
    },
)


FINANCIAL_DATA_SOURCE = SourceSpec(
    source_id="financial_data",
    display_name="蚂蚁",
    kind=SourceKind.API,
    acquisition_modes=(AcquisitionMode.QUERY_THROUGH, AcquisitionMode.SCHEDULED_PULL),
    credential_ref="env:ANT_DATA_API_KEY",
    base_url=(
        "https://dfdatamcpnexus-prod.antgroup-inc.cn/api/v1/common_query"
    ),
    timezone="Asia/Shanghai",
    license_policy={
        "persist_raw_records": False,
        "scheduled_pull_routes": [
            "altdata.hot-stock-rank",
            "altdata.hot-plate-rank",
            "stock_fnd.equity-structure",
            "stock_fnd.free-float",
            "stock_fnd.actual-controller",
            "stock_fnd.controlling-shareholder",
            "stock_fnd.style-classification",
        ],
    },
    configuration={
        "adapter": "financial_data",
        "preferred_api_alias": "ant_data",
        "credential_env": "ANT_DATA_API_KEY",
        "legacy_source_id": "financial_data",
        "api_version": "1.6.0",
        "catalog_discovered_routes": 163,
        "business_scope": "本地规范数据无法覆盖时的限额按需补充；白名单路由按计划采集",
    },
)


_FINANCIAL_SCHEDULED_ENDPOINTS: tuple[dict[str, str], ...] = (
    {
        "endpoint_key": "altdata.hot-stock-rank",
        "route": "/api/v1/altdata/hot-stock-rank",
        "title": "支付宝热门股票榜",
        "cadence": "daily",
    },
    {
        "endpoint_key": "altdata.hot-plate-rank",
        "route": "/api/v1/altdata/hot-plate-rank",
        "title": "支付宝热门板块榜",
        "cadence": "daily",
    },
    {
        "endpoint_key": "stock_fnd.equity-structure",
        "route": "/api/v1/stock_fnd/equity-structure",
        "title": "股本结构（全市场快照）",
        "cadence": "weekly",
    },
    {
        "endpoint_key": "stock_fnd.free-float",
        "route": "/api/v1/stock_fnd/free-float",
        "title": "自由流通股本（全市场事件史）",
        "cadence": "weekly",
    },
    {
        "endpoint_key": "stock_fnd.actual-controller",
        "route": "/api/v1/stock_fnd/actual-controller",
        "title": "实际控制人",
        "cadence": "monthly",
    },
    {
        "endpoint_key": "stock_fnd.controlling-shareholder",
        "route": "/api/v1/stock_fnd/controlling-shareholder",
        "title": "控股股东",
        "cadence": "monthly",
    },
    {
        "endpoint_key": "stock_fnd.style-classification",
        "route": "/api/v1/stock_fnd/style-classification",
        "title": "股票风格规模分类",
        "cadence": "monthly",
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
        capabilities={
            "fields": [], "route_dependent_fields": True,
            "field_contracts_url": "/api/v1/data/sources/ant_data/route-contracts",
            "point_in_time": False, "history_verified": None,
            "permission": "credential_and_route_dependent", "failure_domain": "ant_data",
            "fallback_equivalence": "not_asserted",
        },
        completeness_policy={
            "query_through": True,
            "success_does_not_imply_non_empty": True,
            "business_timestamp_required_for_realtime_claims": True,
        },
    ))
    # Reviewed scheduled-pull allow-list (2026-10 product decision): routes
    # whose facts have no Tushare equivalent and whose research value needs
    # accumulated time series.  Params/enumeration live inside the acquire
    # node (ant_scheduled.py); the endpoint contract stays declarative.
    for _spec in _FINANCIAL_SCHEDULED_ENDPOINTS:
        registry.register_endpoint(EndpointSpec(
            source_id="financial_data",
            endpoint_key=_spec["endpoint_key"],
            title=_spec["title"],
            acquisition_mode=AcquisitionMode.SCHEDULED_PULL,
            resource_class="reference",
            cadence=_spec["cadence"],
            request_contract={"route": _spec["route"], "collection": "ant_norm"},
            completeness_policy={
                "expected_frequency": _spec["cadence"],
                "scheduled_payload_bound": "100_requests_per_payload",
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
            capabilities={
                "fields": [field["name"] for field in contract.output_parameters],
                "field_contracts": list(contract.output_parameters),
                "permission": dict(contract.permission),
                "implementation": dict(contract.implementation),
                "history_verified": None, "point_in_time": False,
                "failure_domain": "tushare", "fallback_equivalence": "not_asserted",
                "units": "see_field_contracts",
            },
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
    from service.source_connectors.public_catalog import PUBLIC_SOURCES, PUBLIC_ENDPOINTS
    for source in PUBLIC_SOURCES:
        registry.register_source(source)
    for endpoint in PUBLIC_ENDPOINTS:
        registry.register_endpoint(endpoint)
    return registry


SOURCE_REGISTRY = build_source_registry()
SOURCE_CONNECTORS = ConnectorRegistry()
