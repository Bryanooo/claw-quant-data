from collectors.tushare_raw import collection_partition_supplied


def test_static_dependency_partition_is_complete_inside_v2_acquire_node():
    assert collection_partition_supplied(
        "dependency_fanout",
        {"_api_name": "stock_hsgt", "type": "HK_SZ", "trade_date": "20260914"},
    )


def test_unpartitioned_dependency_request_still_fails_closed():
    assert not collection_partition_supplied(
        "dependency_fanout",
        {"_api_name": "stock_hsgt", "trade_date": "20260914"},
    )


def test_quarter_range_proves_report_period_partition():
    assert collection_partition_supplied(
        "report_period",
        {"_api_name": "cn_gdp", "start_q": "2026Q2", "end_q": "2026Q2"},
    )
