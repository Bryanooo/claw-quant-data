from service.api.app import create_app
from service.data_service.catalog import (
    CANONICAL_ENDPOINTS,
    RAW_ENDPOINTS,
    RESEARCH_ENDPOINTS,
    STANDARD_ENDPOINTS,
    build_data_service_catalog,
)
from service.api.schemas import DataServiceEndpoint
from service.data_service.lineage import (
    CANONICAL_ENDPOINT_LINEAGE,
    research_endpoint_lineage,
)
from service.data_service.registry import DATASETS
from service.data_service.source_policy import READY_CANONICAL_ADAPTERS
from service.source_connectors.financial_data_catalog import FINANCIAL_DATA_ROUTES


class FakeDatabase:
    def close(self):
        pass


def test_catalog_distinguishes_registration_from_observed_raw_coverage():
    catalog = build_data_service_catalog(
        raw_interfaces=[
            {
                "api_name": "daily",
                "request_count": 4,
                "successful_requests": 3,
                "empty_requests": 0,
                "failed_requests": 1,
                "has_records": True,
            },
            {
                "api_name": "monthly",
                "request_count": 0,
                "successful_requests": 0,
                "empty_requests": 0,
                "failed_requests": 0,
                "has_records": False,
            },
        ],
        datasets=[
            {"name": "stock_daily", "date_column": "trade_date"},
            {"name": "stock_basic", "date_column": None},
        ],
        interfaces=[
            {"api_name": "daily", "datasets": ["stock_daily"], "records_url": None},
            {"api_name": "adj_factor", "datasets": ["adj_factor"], "records_url": "/api/v1/data/interfaces/adj_factor/records"},
        ],
    )

    raw, standard, research = catalog["layers"]
    assert raw["metrics"] == {
        "interfaces": 2,
        "observed_interfaces": 1,
        "interfaces_with_records": 1,
        "interfaces_with_failed_requests": 1,
    }
    assert standard["metrics"] == {
        "datasets": 2,
        "dated_datasets": 1,
        "mapped_interfaces": 2,
        "direct_interface_queries": 1,
        "canonical_endpoints": 24,
    }
    assert research["metrics"]["endpoints"] == 28
    assert all(item["status"] == "available" for item in research["items"])


def test_every_advertised_data_service_endpoint_exists_in_openapi():
    paths = create_app(database_factory=FakeDatabase).openapi()["paths"]

    endpoints = (*RAW_ENDPOINTS, *STANDARD_ENDPOINTS, *RESEARCH_ENDPOINTS)
    identities = [
        (endpoint["method"], endpoint["path"])
        for endpoint in endpoints
    ]
    assert len(endpoints) == 63
    assert len(identities) == len(set(identities))
    for endpoint in endpoints:
        assert endpoint["path"] in paths, endpoint["path"]
        assert endpoint["method"].lower() in paths[endpoint["path"]]


def test_canonical_and_research_catalog_counts_are_stable():
    assert len(CANONICAL_ENDPOINTS) == 24
    assert len(RESEARCH_ENDPOINTS) == 28


def test_every_canonical_and_research_service_exposes_complete_lineage():
    registered = {item.name for item in DATASETS.list()}
    canonical_paths = {item["path"] for item in CANONICAL_ENDPOINTS}
    assert set(CANONICAL_ENDPOINT_LINEAGE) == canonical_paths

    for item in CANONICAL_ENDPOINT_LINEAGE.values():
        assert item["local_datasets"]
        assert set(item["local_datasets"]) <= registered
        assert set(item["fallback_routes"]) <= set(FINANCIAL_DATA_ROUTES)
        assert set(item["fallback_routes"]) <= set(READY_CANONICAL_ADAPTERS)

    for endpoint in RESEARCH_ENDPOINTS:
        lineage = research_endpoint_lineage(endpoint["path"])
        if lineage["data_origin"] == "claw_derived":
            assert lineage["local_datasets"], endpoint["path"]
            assert set(lineage["local_datasets"]) <= registered
        assert lineage["runtime_external_query"] is False


def test_catalog_endpoint_contract_keeps_sources_and_fallbacks():
    catalog = build_data_service_catalog(
        raw_interfaces=[],
        datasets=[
            {"name": item.name, "date_column": item.date_column, "source_ids": list(item.source_ids)}
            for item in DATASETS.list()
        ],
        interfaces=[],
    )
    endpoints = [
        endpoint
        for layer in catalog["layers"]
        for endpoint in layer["endpoints"]
    ]
    validated = [DataServiceEndpoint.model_validate(item) for item in endpoints]
    assert len(validated) == 63
    market_bars = next(item for item in validated if item.path.endswith("/market-bars"))
    assert market_bars.upstream_sources == ["tushare", "financial_data"]
    assert market_bars.local_datasets == ["stock_daily"]
    assert market_bars.runtime_external_query is True
    fundamentals = next(item for item in validated if item.path.endswith("/fundamentals"))
    assert fundamentals.data_origin == "claw_derived"
    assert "financial_indicator" in fundamentals.local_datasets
    assert fundamentals.runtime_external_query is False
