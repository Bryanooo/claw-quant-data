from datetime import date

import pytest

from service.data_service.canonical_equity import CanonicalEquityDataService
from service.data_service.models import InvalidQueryError, UpstreamFallbackError
from service.source_connectors.contracts import AcquisitionMode, ConnectorResult


class FakeDataService:
    def __init__(self, *, profiles=None, valuations=None, sessions=None):
        self.profiles = profiles or {}
        self.valuations = valuations or {}
        self.sessions = sessions or []
        self.calls = []

    def query_dataset(self, name, **kwargs):
        self.calls.append((name, kwargs))
        if name == "stock_basic":
            return {"data": self.profiles.get(kwargs["exact_filters"]["ts_code"], [])}
        if name == "stock_daily_basic":
            return {"data": self.valuations.get(kwargs["exact_filters"]["ts_code"], [])}
        if name == "trade_calendar":
            return {"data": self.sessions}
        raise AssertionError(name)


class FakeBroker:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.calls = []

    def query(self, request):
        self.calls.append(request)
        if self.error:
            raise self.error
        return ConnectorResult(
            source_id="financial_data",
            endpoint_key="common_query",
            acquisition_mode=AcquisitionMode.QUERY_THROUGH,
            records=(self.response,),
            fetched_rows=1,
            status="complete",
        )


def _provider_response(route, fields, rows):
    return {
        "status": "SUCCESS",
        "results": [{"url": route, "meta": {"fields": fields}, "data": rows}],
    }


def test_equity_profile_uses_local_identity_without_spending_quota():
    data = FakeDataService(profiles={"300750.SZ": [{
        "ts_code": "300750.SZ",
        "symbol": "300750",
        "name": "宁德时代",
        "fullname": "宁德时代新能源科技股份有限公司",
        "enname": "Contemporary Amperex Technology Co., Ltd.",
        "area": "福建",
        "industry": "电气设备",
        "market": "创业板",
        "exchange": "SZSE",
        "curr_type": "CNY",
        "list_status": "L",
        "list_date": "20180611",
        "act_name": "曾毓群",
    }]})
    broker = FakeBroker()

    result = CanonicalEquityDataService(data, broker).profiles(symbols=["300750.sz"])

    assert broker.calls == []
    profile = result["data"][0]
    assert profile["instrument_id"] == "300750.SZ"
    assert profile["listing_status"] == "listed"
    assert profile["listing_date"] == date(2018, 6, 11)
    assert profile["industry_classification"] == "tushare_legacy"
    assert profile["source_id"] == "tushare"


def test_equity_profile_fallback_decodes_controller_payload():
    fields = [
        "symbol", "stock_code", "stock_abbr", "company_cn_name",
        "company_en_name", "exchange_en_abbr", "listing_board",
        "listing_status", "listing_date", "province",
        "sw_second_industry_name", "actual_controller",
    ]
    controller = '{"data":[{"actual_controller_name":"曾毓群"}],"meta":{}}'
    broker = FakeBroker(_provider_response(
        "/api/v1/stock_fnd/stock-basic-info",
        fields,
        [[
            "300750.SZ", "300750", "宁德时代", "宁德时代新能源科技股份有限公司",
            "CATL", "SZSE", "创业板", "上市", "2018-06-11 00:00:00",
            "福建省", "电池", controller,
        ]],
    ))

    result = CanonicalEquityDataService(FakeDataService(), broker).profiles(
        symbols=["300750.SZ"]
    )

    profile = result["data"][0]
    assert profile["actual_controller"] == "曾毓群"
    assert profile["industry_classification"] == "sw_level_2"
    assert profile["source_id"] == "financial_data"


def test_local_valuation_normalizes_shares_market_caps_and_yield_rates():
    data = FakeDataService(valuations={"300750.SZ": [{
        "ts_code": "300750.SZ",
        "trade_date": date(2026, 9, 30),
        "close": 291.11,
        "pe": 18.6567,
        "pe_ttm": 15.8475,
        "pb": 3.5509,
        "ps": 3.1792,
        "ps_ttm": 2.5819,
        "dv_ratio": 2.3205,
        "dv_ttm": 2.8536,
        "total_share": 462724.9686,
        "float_share": 426061.7083,
        "total_mv": 134703866.0167,
        "circ_mv": 124030824.3981,
    }]})
    broker = FakeBroker()

    result = CanonicalEquityDataService(data, broker).valuations(
        symbols=["300750.SZ"],
        start_date=date(2026, 9, 30),
        end_date=date(2026, 9, 30),
    )

    assert broker.calls == []
    row = result["data"][0]
    assert row["total_shares"] == pytest.approx(4_627_249_686)
    assert row["total_market_cap"] == pytest.approx(1_347_038_660_167)
    assert row["dividend_yield_lyr_rate"] == pytest.approx(0.023205)
    assert row["source_id"] == "tushare"


def test_valuation_fallback_uses_equivalent_pb_and_preserves_local_precedence():
    local = {
        "ts_code": "300750.SZ", "trade_date": date(2026, 9, 30),
        "pe": 18.6567, "pe_ttm": 15.8475, "pb": 3.5509,
        "ps": 3.1792, "ps_ttm": 2.5819, "dv_ratio": 2.3205,
        "dv_ttm": 2.8536, "total_mv": 134703866.0167,
    }
    fields = [
        "symbol", "trading_day", "total_market_cap", "pe_lyr", "pe_ttm",
        "pb_mrq", "ps_lyr", "ps_ttm", "dividend_yield_lyr",
        "dividend_yield_ttm",
    ]
    broker = FakeBroker(_provider_response(
        "/api/v1/stock/daily-valuation-indicators",
        fields,
        [
            ["300750.SZ", "2026-09-30 00:00:00", 1, 999, 999, 999, 999, 999, 999, 999],
            ["300750.SZ", "2026-09-29 00:00:00", 1_300_000_000_000, 18, 16, 3.5, 3, 2.5, 2, 2.8],
        ],
    ))
    data = FakeDataService(
        valuations={"300750.SZ": [local]},
        sessions=[{"cal_date": date(2026, 9, 29)}, {"cal_date": date(2026, 9, 30)}],
    )

    result = CanonicalEquityDataService(data, broker).valuations(
        symbols=["300750.SZ"],
        start_date=date(2026, 9, 29),
        end_date=date(2026, 9, 30),
    )

    by_date = {row["observation_date"]: row for row in result["data"]}
    assert by_date[date(2026, 9, 30)]["pe_lyr"] == pytest.approx(18.6567)
    assert by_date[date(2026, 9, 30)]["source_id"] == "tushare"
    assert by_date[date(2026, 9, 29)]["pb_mrq"] == pytest.approx(3.5)
    assert by_date[date(2026, 9, 29)]["source_id"] == "financial_data"
    assert result["meta"]["unresolved_open_dates"]["300750.SZ"] == []


def test_equity_adapter_rejects_invalid_scope_and_protocol_drift():
    service = CanonicalEquityDataService(FakeDataService(), FakeBroker(
        _provider_response(
            "/api/v1/stock/daily-valuation-indicators",
            ["symbol", "trading_day"],
            [["300750.SZ"]],
        )
    ))
    with pytest.raises(UpstreamFallbackError, match="FinancialDataProtocolError"):
        service.valuations(
            symbols=["300750.SZ"],
            start_date=date(2026, 9, 30),
            end_date=date(2026, 9, 30),
        )
    with pytest.raises(InvalidQueryError, match="366 days"):
        service.valuations(
            symbols=["300750.SZ"],
            start_date=date(2025, 1, 1),
            end_date=date(2026, 9, 30),
        )
    with pytest.raises(InvalidQueryError, match="A-share"):
        service.profiles(symbols=["AAPL.O"])
