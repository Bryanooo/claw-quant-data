from datetime import date

import pytest

from service.data_service.canonical_market import CanonicalMarketDataService
from service.data_service.models import InvalidQueryError, UpstreamFallbackError
from service.source_connectors.contracts import AcquisitionMode, ConnectorResult


class FakeDataService:
    def __init__(self, *, bars=None, sessions=None):
        self.bars = bars or {}
        self.sessions = sessions or []
        self.calls = []

    def query_dataset(self, name, **kwargs):
        self.calls.append((name, kwargs))
        if name == "stock_daily":
            return {"data": self.bars.get(kwargs["exact_filters"]["ts_code"], [])}
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
        "results": [{
            "url": route,
            "meta": {"fields": fields},
            "data": rows,
        }],
    }


def test_daily_bars_use_local_db_and_normalize_tushare_units():
    data = FakeDataService(bars={"000001.SZ": [{
        "ts_code": "000001.SZ",
        "trade_date": date(2026, 9, 30),
        "open": 11.36,
        "high": 11.65,
        "low": 11.33,
        "close": 11.57,
        "pre_close": 11.35,
        "change": 0.22,
        "pct_chg": 1.9383,
        "vol": 1_045_357.45,
        "amount": 1_205_814.85764,
    }]})
    broker = FakeBroker()

    response = CanonicalMarketDataService(data, broker).daily_bars(
        symbols=["000001.sz"],
        start_date=date(2026, 9, 30),
        end_date=date(2026, 9, 30),
    )

    assert broker.calls == []
    assert response["meta"]["fallback_used"] is False
    assert response["data"][0]["volume"] == 104_535_745
    assert response["data"][0]["amount"] == pytest.approx(1_205_814_857.64)
    assert response["data"][0]["source_id"] == "tushare"


def test_daily_bars_fall_back_only_for_empty_local_symbols():
    fields = [
        "symbol", "period", "adj_type", "date", "begin_date", "open",
        "high", "low", "close", "previous_close", "volume", "amount",
    ]
    broker = FakeBroker(_provider_response(
        "/api/v1/quote/kline-batch",
        fields,
        [[
            "000001.SZ", "P_Day1", "S_Unsplit", "2026-09-30 00:00:00",
            "2026-09-30 00:00:00", 11.36, 11.65, 11.33, 11.57, 11.35,
            104_535_745, 1_205_814_857.64,
        ]],
    ))

    response = CanonicalMarketDataService(FakeDataService(), broker).daily_bars(
        symbols=["000001.SZ"],
        start_date=date(2026, 9, 30),
        end_date=date(2026, 9, 30),
    )

    assert len(broker.calls) == 1
    assert response["meta"]["fallback_used"] is True
    assert response["meta"]["fallback_symbols"] == ["000001.SZ"]
    assert response["data"][0]["volume"] == 104_535_745
    assert response["data"][0]["amount"] == pytest.approx(1_205_814_857.64)
    assert response["data"][0]["source_id"] == "financial_data"


def test_daily_bars_fill_calendar_gap_without_overwriting_local_rows():
    local = {
        "ts_code": "000001.SZ",
        "trade_date": date(2026, 9, 30),
        "open": 11.36,
        "high": 11.65,
        "low": 11.33,
        "close": 11.57,
        "pre_close": 11.35,
        "change": 0.22,
        "pct_chg": 1.9383,
        "vol": 1_045_357.45,
        "amount": 1_205_814.85764,
    }
    fields = [
        "symbol", "period", "adj_type", "date", "begin_date", "open",
        "high", "low", "close", "previous_close", "volume", "amount",
    ]
    broker = FakeBroker(_provider_response(
        "/api/v1/quote/kline-batch",
        fields,
        [
            ["000001.SZ", "P_Day1", "S_Unsplit", "2026-09-30 00:00:00",
             "2026-09-30 00:00:00", 1, 1, 1, 999, 1, 1, 1],
            ["000001.SZ", "P_Day1", "S_Unsplit", "2026-09-29 00:00:00",
             "2026-09-29 00:00:00", 11.3, 11.41, 11.28, 11.35, 11.3,
             69_097_909, 784_632_823.03],
        ],
    ))
    data = FakeDataService(
        bars={"000001.SZ": [local]},
        sessions=[{"cal_date": date(2026, 9, 29)}, {"cal_date": date(2026, 9, 30)}],
    )

    response = CanonicalMarketDataService(data, broker).daily_bars(
        symbols=["000001.SZ"],
        start_date=date(2026, 9, 29),
        end_date=date(2026, 9, 30),
    )

    assert response["meta"]["fallback_used"] is True
    assert len(response["data"]) == 2
    by_date = {row["period_end"]: row for row in response["data"]}
    assert by_date[date(2026, 9, 30)]["source_id"] == "tushare"
    assert by_date[date(2026, 9, 30)]["close"] == 11.57
    assert by_date[date(2026, 9, 29)]["source_id"] == "financial_data"
    assert response["meta"]["unresolved_open_dates"]["000001.SZ"] == []


def test_daily_bars_can_forbid_quota_fallback():
    broker = FakeBroker()

    response = CanonicalMarketDataService(FakeDataService(), broker).daily_bars(
        symbols=["000001.SZ"],
        start_date=date(2026, 9, 30),
        end_date=date(2026, 9, 30),
        allow_quota_fallback=False,
    )

    assert broker.calls == []
    assert response["data"] == []
    assert response["meta"]["fallback_used"] is False
    assert response["meta"]["unresolved_symbols"] == ["000001.SZ"]


def test_trading_sessions_fall_back_to_canonical_dates():
    broker = FakeBroker(_provider_response(
        "/api/v1/common/trading-day",
        ["symbol", "trading_days", "time_zone"],
        [["000001.SZ", ["20260929", "20260930"], "Asia/Shanghai"]],
    ))

    response = CanonicalMarketDataService(FakeDataService(), broker).trading_days(
        symbol="000001.SZ",
        start_date=date(2026, 9, 29),
        end_date=date(2026, 9, 30),
    )

    assert response["meta"]["fallback_used"] is True
    assert [row["session_date"] for row in response["data"]] == [
        date(2026, 9, 29), date(2026, 9, 30)
    ]
    assert {row["source_id"] for row in response["data"]} == {"financial_data"}


def test_canonical_fallback_rejects_protocol_drift_and_unbounded_input():
    bad_broker = FakeBroker(_provider_response(
        "/api/v1/quote/kline-batch",
        ["symbol", "period"],
        [["000001.SZ"]],
    ))
    service = CanonicalMarketDataService(FakeDataService(), bad_broker)

    with pytest.raises(UpstreamFallbackError, match="FinancialDataProtocolError"):
        service.daily_bars(
            symbols=["000001.SZ"],
            start_date=date(2026, 9, 30),
            end_date=date(2026, 9, 30),
        )
    with pytest.raises(InvalidQueryError, match="366 days"):
        service.daily_bars(
            symbols=["000001.SZ"],
            start_date=date(2025, 1, 1),
            end_date=date(2026, 9, 30),
        )
    with pytest.raises(InvalidQueryError, match="A-share"):
        service.daily_bars(
            symbols=["AAPL.O"],
            start_date=date(2026, 9, 30),
            end_date=date(2026, 9, 30),
        )
