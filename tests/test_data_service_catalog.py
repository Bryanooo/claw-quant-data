from service.data_service.catalog import build_data_service_catalog


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
            {"api_name": "adj_factor", "datasets": ["adj_factor"], "records_url": "/api/v1/interfaces/adj_factor/records"},
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
    }
    assert research["metrics"]["capabilities"] == 10
    assert all(item["status"] == "available" for item in research["items"])
