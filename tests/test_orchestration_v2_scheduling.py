from datetime import date

from service.orchestration_v2 import scheduling
from service.orchestration_v2.catalog import acquisition_task_blueprints
from service.tushare_policy import TusharePolicyRegistry
from service.tushare_scheduling import parameters_for_policy


class _Repository:
    def __init__(self):
        self.requests = []

    def create_execution(self, request):
        self.requests.append(request)
        return ({"task_key": request.task_key}, True)


def test_daily_dispatch_creates_one_execution_per_daily_task(monkeypatch):
    repository = _Repository()
    monkeypatch.setattr(scheduling, "is_trade_day", lambda _value: True)

    result = scheduling.dispatch_daily_acquisitions(
        date(2026, 9, 28),
        repository=repository,
    )

    expected = {
        item.task_key
        for item in acquisition_task_blueprints()
        if item.cadence == "daily"
    }
    assert "stock_st" in expected
    assert result == {
        "target_date": "2026-09-28",
        "delayed_target_date": "2026-09-28",
        "trade_day": True,
        "eligible": len(expected),
        "created": len(expected),
        "existing": 0,
        "skipped": None,
        "errors": {},
    }
    assert {item.task_key for item in repository.requests} == expected
    assert all(item.purpose.value == "daily" for item in repository.requests)
    assert all(
        item.observation_start == item.observation_end == date(2026, 9, 28)
        for item in repository.requests
    )
    assert len({item.idempotency_key for item in repository.requests}) == len(expected)


def test_daily_dispatch_does_not_create_weekend_work(monkeypatch):
    repository = _Repository()
    monkeypatch.setattr(scheduling, "is_trade_day", lambda _value: False)

    result = scheduling.dispatch_daily_acquisitions(
        date(2026, 9, 27),
        repository=repository,
    )

    assert result["skipped"] == "not_a_trade_day"
    assert repository.requests == []


def test_reviewed_cadences_do_not_fall_back_to_snapshot_heuristics():
    policies = TusharePolicyRegistry()
    assert (policies.get("cn_gdp").cadence, policies.get("cn_gdp").parameter_strategy) == (
        "quarterly",
        "report_period",
    )
    assert (policies.get("ggt_daily").cadence, policies.get("ggt_daily").parameter_strategy) == (
        "daily",
        "trade_date",
    )
    assert policies.get("ths_member").parameter_strategy == "dependency_fanout"


def test_legacy_ggt_catalog_gap_still_builds_bounded_trade_date_request():
    policy = TusharePolicyRegistry().get("ggt_daily")

    assert parameters_for_policy(
        policy,
        set(),
        today=date(2026, 9, 28),
        trade_date="20260925",
    ) == {"trade_date": "20260925"}
