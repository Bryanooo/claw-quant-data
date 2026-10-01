from datetime import date

import pytest

from service.api.schemas import (
    CanonicalEquityPledgesResponse,
    CanonicalEquityRestrictedReleasesResponse,
    CanonicalEquityRiskAlertsResponse,
    CanonicalEquityShareholdersResponse,
    CanonicalEquitySuspensionsResponse,
)
from service.data_service.canonical_equity_actions import CanonicalEquityActionService
from service.source_connectors.contracts import AcquisitionMode, ConnectorResult


class FakeDataService:
    def __init__(self, rows=None):
        self.rows = rows or {}
        self.calls = []

    def query_dataset(self, name, **kwargs):
        self.calls.append((name, kwargs))
        symbol = kwargs["exact_filters"]["ts_code"]
        return {"data": list(self.rows.get((name, symbol), []))}


class QueueBroker:
    def __init__(self, *responses):
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
    return {
        "status": "SUCCESS",
        "results": [{"url": route, "meta": {"fields": fields}, "data": rows}],
    }


def test_shareholders_prefer_both_local_disclosure_scopes():
    period = date(2026, 6, 30)
    common = {
        "ts_code": "300750.SZ", "ann_date": date(2026, 7, 25),
        "end_date": period, "holder_name": "香港中央结算有限公司",
        "hold_amount": 894_158_187, "hold_ratio": 19.3263,
        "hold_float_ratio": 20.9893, "hold_change": 132_842_713,
        "holder_type": "一般企业",
    }
    data = FakeDataService({
        ("top10_holders", "300750.SZ"): [common],
        ("top10_floatholders", "300750.SZ"): [common],
    })
    broker = QueueBroker()

    result = CanonicalEquityActionService(data, broker).shareholders(
        symbols=["300750.SZ"], report_dates=[period]
    )

    assert broker.calls == []
    assert {row["scope"] for row in result["data"]} == {"total", "float"}
    assert result["data"][0]["holding_shares"] == 894_158_187
    assert result["meta"]["unresolved"] == []
    CanonicalEquityShareholdersResponse.model_validate(result)


def test_restricted_releases_preserve_local_share_and_percentage_units():
    local = {
        "ts_code": "300750.SZ", "ann_date": date(2024, 9, 20),
        "float_date": date(2024, 9, 24), "float_share": 15_589_025,
        "float_ratio": 0.3541, "holder_name": "核心员工",
        "share_type": "股权激励限售流通",
    }
    broker = QueueBroker()
    result = CanonicalEquityActionService(
        FakeDataService({("share_float", "300750.SZ"): [local]}), broker
    ).restricted_releases(
        symbols=["300750.SZ"], start_date=date(2024, 1, 1),
        end_date=date(2024, 12, 31),
    )

    assert broker.calls == []
    row = result["data"][0]
    assert row["release_shares"] == 15_589_025
    assert row["release_pct_total"] == pytest.approx(0.3541)
    CanonicalEquityRestrictedReleasesResponse.model_validate(result)


def test_pledges_fallback_normalizes_provider_event():
    route = "/api/v1/stock_sh_equity/freeze-pledge"
    fields = [
        "symbol", "information_publish_date", "event_date", "event_type",
        "shareholder_name", "receiver_name", "involved_shares",
        "pct_of_total_shares", "pct_of_pledger", "end_date",
        "estimated_release_date", "is_completely_released",
        "freeze_pledge_reason", "statement",
    ]
    broker = QueueBroker(_response(route, fields, [[
        "300750.SZ", "2026-08-01", "2026-07-30", "股权质押",
        "某股东", "某银行", 10_000_000, 0.22, 5.1, "2027-07-30",
        "2027-07-30", "否", "融资", "质押进展",
    ]]))

    result = CanonicalEquityActionService(
        FakeDataService(), broker
    ).pledges(
        symbols=["300750.SZ"], start_date=date(2026, 7, 1),
        end_date=date(2026, 8, 31),
    )

    row = result["data"][0]
    assert row["involved_shares"] == 10_000_000
    assert row["is_released"] is False
    assert row["source_id"] == "financial_data"
    CanonicalEquityPledgesResponse.model_validate(result)


def test_risk_alerts_prefer_local_episode_over_daily_snapshot():
    episode = {
        "ts_code": "000001.SZ", "name": "平安银行",
        "start_date": date(2020, 1, 2), "end_date": date(2020, 2, 3),
        "type": "ST",
    }
    snapshot = {
        "ts_code": "000001.SZ", "name": "平安银行",
        "trade_date": date(2020, 1, 3), "st_type": "ST",
    }
    broker = QueueBroker()
    result = CanonicalEquityActionService(FakeDataService({
        ("stk_alert", "000001.SZ"): [episode],
        ("stock_st", "000001.SZ"): [snapshot],
    }), broker).risk_alerts(
        symbols=["000001.SZ"], start_date=date(2020, 1, 1),
        end_date=date(2020, 12, 31),
    )

    assert broker.calls == []
    assert len(result["data"]) == 1
    assert result["data"][0]["source_dataset"] == "stk_alert"
    CanonicalEquityRiskAlertsResponse.model_validate(result)


def test_suspensions_keep_local_timing_without_quota():
    local = {
        "ts_code": "300750.SZ", "trade_date": date(2018, 6, 11),
        "suspend_timing": "09:30-10:00", "suspend_type": "S",
    }
    broker = QueueBroker()
    result = CanonicalEquityActionService(FakeDataService({
        ("stock_suspend", "300750.SZ"): [local],
    }), broker).suspensions(
        symbols=["300750.SZ"], start_date=date(2018, 6, 1),
        end_date=date(2018, 6, 30),
    )

    assert broker.calls == []
    assert result["data"][0]["suspend_time"] == "09:30-10:00"
    assert result["data"][0]["source_id"] == "tushare"
    CanonicalEquitySuspensionsResponse.model_validate(result)
