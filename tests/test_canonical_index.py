from datetime import date

import pytest

from service.api.schemas import (
    CanonicalIndexConstituentsResponse,
    CanonicalIndexProfilesResponse,
)
from service.data_service.canonical_index import CanonicalIndexDataService
from service.source_connectors.contracts import AcquisitionMode, ConnectorResult


class FakeDataService:
    def __init__(self, rows=None):
        self.rows = rows or {}

    def query_dataset(self, name, **kwargs):
        key = kwargs["exact_filters"].get("ts_code") or kwargs["exact_filters"].get("index_code")
        return {"data": list(self.rows.get((name, key), []))}


class FakeBroker:
    def __init__(self, responses=()):
        self.responses = list(responses)
        self.calls = []

    def query(self, request):
        self.calls.append(request)
        return ConnectorResult(
            source_id="financial_data", endpoint_key="common_query",
            acquisition_mode=AcquisitionMode.QUERY_THROUGH,
            records=(self.responses.pop(0),), fetched_rows=1, status="complete",
        )


def _response(route, fields, rows):
    return {"status": "SUCCESS", "results": [{
        "url": route, "meta": {"fields": fields}, "data": rows,
    }]}


def test_index_profile_prefers_local_contract():
    local = {
        "ts_code": "000300.SH", "name": "沪深300", "market": "SSE",
        "publisher": "中证指数", "category": "规模指数",
        "base_date": date(2004, 12, 31), "base_point": 1000,
        "list_date": date(2005, 4, 8),
    }
    broker = FakeBroker()
    result = CanonicalIndexDataService(
        FakeDataService({("index_basic", "000300.SH"): [local]}), broker
    ).profiles(symbols=["000300.SH"])

    assert broker.calls == []
    assert result["data"][0]["base_point"] == 1000
    assert result["data"][0]["source_id"] == "tushare"
    CanonicalIndexProfilesResponse.model_validate(result)


def test_index_constituents_fallback_normalizes_weight():
    route = "/api/v1/index_fnd/index-constituents-list-weight"
    fields = ["symbol", "update_date", "stock_symbol", "sec_name", "weight"]
    broker = FakeBroker([_response(route, fields, [[
        "000300.SH", "2026-06-30", "600519.SH", "贵州茅台", 4.25,
    ]])])
    result = CanonicalIndexDataService(
        FakeDataService(), broker
    ).constituents(
        symbols=["000300.SH"], update_dates=[date(2026, 6, 30)]
    )

    row = result["data"][0]
    assert row["instrument_id"] == "600519.SH"
    assert row["weight_pct"] == pytest.approx(4.25)
    assert result["meta"]["unresolved"] == []
    CanonicalIndexConstituentsResponse.model_validate(result)
