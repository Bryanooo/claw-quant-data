from service.api.app import create_app
from service.data_service.catalog import (
    CANONICAL_ENDPOINTS,
    RAW_ENDPOINTS,
    RESEARCH_ENDPOINTS,
    STANDARD_ENDPOINTS,
    build_data_service_catalog,
)


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
