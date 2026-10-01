from scripts.report_tushare_data_presence import (
    _implementation_tables,
    _scheduled_api_names,
)


def test_generic_collectors_report_their_typed_business_tables():
    tables = _implementation_tables()

    assert "tushare_norm_fund_portfolio" in tables["fund_portfolio"]
    assert "tushare_norm_daily_basic" in tables["daily_basic"]
    assert "tushare_raw_record" not in tables["fund_portfolio"]


def test_scheduled_interfaces_use_the_runtime_selected_endpoint():
    scheduled = _scheduled_api_names({"balancesheet", "financial_indicator"})

    assert scheduled == {"balancesheet", "fina_indicator"}
    assert "balancesheet_vip" not in scheduled
    assert "fina_indicator_vip" not in scheduled
