from datetime import date

import pytest

from service.api.schemas import (
    CanonicalFundDividendsResponse,
    CanonicalFundManagersResponse,
)
from service.data_service.canonical_fund import CanonicalFundDataService
from service.data_service.models import InvalidQueryError, UpstreamFallbackError
from service.source_connectors.contracts import AcquisitionMode, ConnectorResult


class FakeDataService:
    def __init__(self, records=None):
        self.records = records or {}
        self.calls = []

    def query_dataset(self, name, **kwargs):
        self.calls.append((name, kwargs))
        symbol = kwargs["exact_filters"]["ts_code"]
        period = kwargs.get("date_value")
        return {"data": self.records.get((name, symbol, period), self.records.get((name, symbol), []))}


class FakeBroker:
    def __init__(self, responses=None, error=None):
        self.responses = list(responses or [])
        self.error = error
        self.calls = []

    def query(self, request):
        self.calls.append(request)
        if self.error:
            raise self.error
        response = self.responses.pop(0)
        return ConnectorResult(
            source_id="financial_data",
            endpoint_key="common_query",
            acquisition_mode=AcquisitionMode.QUERY_THROUGH,
            records=(response,),
            fetched_rows=1,
            status="complete",
        )


def _provider_response(route, fields, rows):
    return {
        "status": "SUCCESS",
        "results": [{"url": route, "meta": {"fields": fields}, "data": rows}],
    }


def test_profiles_prefer_local_and_normalize_amount_and_fee_units():
    data = FakeDataService({("fund_basic", "000001.OF"): [{
        "ts_code": "000001.OF",
        "name": "华夏成长",
        "management": "华夏基金管理有限公司",
        "custodian": "中国建设银行股份有限公司",
        "fund_type": "混合型",
        "invest_type": "成长型",
        "found_date": date(2001, 12, 18),
        "min_amount": 0.1,
        "m_fee": 1.2,
        "c_fee": 0.2,
    }]})
    broker = FakeBroker()

    result = CanonicalFundDataService(data, broker).profiles(symbols=["000001.of"])

    assert broker.calls == []
    profile = result["data"][0]
    assert profile["minimum_purchase_amount"] == 1000
    assert profile["management_fee_rate"] == pytest.approx(0.012)
    assert profile["custodian_fee_rate"] == pytest.approx(0.002)
    assert profile["source_id"] == "tushare"


def test_profiles_fallback_for_missing_symbol_with_same_contract():
    fields = [
        "symbol", "fund_name", "fund_mgmt_company", "establishment_date",
        "min_purchase_amount", "currency", "mgmt_fee_rate", "custodian_fee_rate",
    ]
    broker = FakeBroker([_provider_response(
        "/api/v1/fund/fund-archive",
        fields,
        [["000001.OF", "华夏成长证券投资基金", "CHINAAMC", "20011218", 10, "CNY", "1.2%", "0.2%"]],
    )])

    result = CanonicalFundDataService(FakeDataService(), broker).profiles(
        symbols=["000001.OF"]
    )

    assert result["meta"]["fallback_used"] is True
    profile = result["data"][0]
    assert profile["minimum_purchase_amount"] == 10
    assert profile["management_fee_rate"] == pytest.approx(0.012)
    assert profile["source_id"] == "financial_data"


def test_nav_does_not_infer_missing_daily_partitions():
    local = [{
        "ts_code": "000001.OF",
        "ann_date": date(2026, 9, 30),
        "nav_date": date(2026, 9, 30),
        "unit_nav": 1.222,
        "accum_nav": 3.795,
        "adj_nav": 7.947448,
    }]
    data = FakeDataService({("fund_nav", "000001.OF"): local})
    broker = FakeBroker()

    result = CanonicalFundDataService(data, broker).nav(
        symbols=["000001.OF"],
        start_date=date(2026, 9, 1),
        end_date=date(2026, 9, 30),
    )

    assert broker.calls == []
    assert result["meta"]["fallback_used"] is False
    assert result["data"][0]["daily_return_rate"] is None


def test_nav_empty_slice_fallback_preserves_decimal_return_rate():
    fields = [
        "symbol", "nav_date", "unit_nav", "cumulative_nav", "adj_nav",
        "pct_chg_1d", "annualized_yield_7d", "daily_profit_per_10k",
    ]
    broker = FakeBroker([_provider_response(
        "/api/v1/fund/net-value",
        fields,
        [["000001.OF", "2026-09-30 00:00:00", 1.222, 3.795, 7.947448, -0.0193, 0.844, 0.232]],
    )])

    result = CanonicalFundDataService(FakeDataService(), broker).nav(
        symbols=["000001.OF"],
        start_date=date(2026, 9, 30),
        end_date=date(2026, 9, 30),
    )

    assert result["data"][0]["daily_return_rate"] == pytest.approx(-0.0193)
    assert result["data"][0]["annualized_yield_7d_rate"] == pytest.approx(0.00844)
    assert result["data"][0]["daily_profit_per_10k"] == pytest.approx(0.232)
    assert result["meta"]["coverage"]["000001.OF"]["fallback_rows"] == 1


def test_holdings_normalize_weight_and_stock_identity():
    fields = [
        "symbol", "stock_name", "holding_shares", "stock_symbol",
        "report_period", "listing_market", "stock_ratio", "secu_market",
        "pct_to_nav", "holding_mv",
    ]
    broker = FakeBroker([_provider_response(
        "/api/v1/fund/stock-portfolio",
        fields,
        [["000001.OF", "中际旭创", 200000, "300308", "20260630", "深圳A股", "中际旭创：6.45%", "SZ", 0.0645, 254000000]],
    )])

    result = CanonicalFundDataService(FakeDataService(), broker).stock_holdings(
        symbols=["000001.OF"],
        report_dates=[date(2026, 6, 30)],
    )

    holding = result["data"][0]
    assert holding["instrument_id"] == "300308.SZ"
    assert holding["weight_pct"] == pytest.approx(6.45)
    assert holding["holding_market_value"] == 254000000


def test_holdings_local_rows_win_and_quarter_dates_are_validated():
    local = [{
        "ts_code": "000001.OF",
        "ann_date": date(2026, 8, 31),
        "end_date": date(2026, 6, 30),
        "symbol": "605111.SH",
        "mkv": 33467284.64,
        "amount": 337576,
        "stk_mkv_ratio": 1.06,
    }]
    data = FakeDataService({("fund_portfolio", "000001.OF", "2026-06-30"): local})
    broker = FakeBroker()
    service = CanonicalFundDataService(data, broker)

    result = service.stock_holdings(
        symbols=["000001.OF"], report_dates=[date(2026, 6, 30)]
    )
    assert broker.calls == []
    assert result["data"][0]["weight_pct"] == pytest.approx(1.06)
    assert result["data"][0]["source_id"] == "tushare"

    with pytest.raises(InvalidQueryError, match="quarter ends"):
        service.stock_holdings(
            symbols=["000001.OF"], report_dates=[date(2026, 6, 29)]
        )


def test_fund_fallback_rejects_protocol_drift_and_unbounded_input():
    bad_broker = FakeBroker([_provider_response(
        "/api/v1/fund/net-value", ["symbol", "nav_date"], [["000001.OF"]]
    )])
    service = CanonicalFundDataService(FakeDataService(), bad_broker)
    with pytest.raises(UpstreamFallbackError, match="FinancialDataProtocolError"):
        service.nav(
            symbols=["000001.OF"],
            start_date=date(2026, 9, 30),
            end_date=date(2026, 9, 30),
        )
    with pytest.raises(InvalidQueryError, match="366 days"):
        service.nav(
            symbols=["000001.OF"],
            start_date=date(2025, 1, 1),
            end_date=date(2026, 9, 30),
        )
    with pytest.raises(InvalidQueryError, match="OF/SH/SZ"):
        service.profiles(symbols=["NOT-A-FUND"])


def test_fund_dividend_prefers_local_cash_per_unit():
    local = {
        "ts_code": "000001.OF", "ann_date": date(2026, 4, 1),
        "record_date": date(2026, 4, 8), "ex_date": date(2026, 4, 9),
        "pay_date": date(2026, 4, 12), "div_cash": 0.25,
        "base_unit": 1.0, "div_proc": "实施",
    }
    broker = FakeBroker()
    result = CanonicalFundDataService(
        FakeDataService({("fund_div", "000001.OF"): [local]}), broker
    ).dividends(
        symbols=["000001.OF"], start_date=date(2026, 1, 1),
        end_date=date(2026, 12, 31),
    )

    assert broker.calls == []
    assert result["data"][0]["cash_per_unit"] == pytest.approx(0.25)
    CanonicalFundDividendsResponse.model_validate(result)


def test_fund_manager_fallback_normalizes_tenure():
    route = "/api/v1/fund/fund-manager"
    fields = [
        "symbol", "tenure_return", "tenure_start_date", "manager_name",
        "career_start_date", "tenure_end_date", "background",
    ]
    broker = FakeBroker([_provider_response(route, fields, [[
        "000001.OF", 0.35, "2020-01-01", "张三", "2010-01-01", None,
        "基金经理履历",
    ]])])
    result = CanonicalFundDataService(
        FakeDataService(), broker
    ).managers(symbols=["000001.OF"])

    assert result["data"][0]["manager_name"] == "张三"
    assert result["data"][0]["tenure_return_rate"] == pytest.approx(0.35)
    CanonicalFundManagersResponse.model_validate(result)
