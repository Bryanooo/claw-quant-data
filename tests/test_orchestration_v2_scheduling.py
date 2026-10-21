from datetime import date

from service.acquisition_runtime.fanout import FANOUT_DEFINITIONS
from service.history_recovery import MARKET_WIDE_FANOUT_OVERRIDES
from service.orchestration_v2 import scheduling
from service.orchestration_v2.catalog import acquisition_task_blueprints
from service.tushare_policy import TusharePolicyRegistry
from service.tushare_scheduling import parameters_for_policy


class _Repository:
    def __init__(self):
        self.requests = []
        self.superseded = []
        self.requeued = []

    def create_execution(self, request):
        self.requests.append(request)
        return ({"task_key": request.task_key}, True)

    def supersede_not_expected_daily_scope(
        self, observation_date, task_keys, *, reason
    ):
        self.superseded.append((observation_date, task_keys, reason))
        return [{"task_key": task_key} for task_key in task_keys]

    def requeue_due_daily_scope(
        self, observation_date, task_keys, *, reason
    ):
        self.requeued.append((observation_date, task_keys, reason))
        return [{"task_key": task_key} for task_key in task_keys]


def test_daily_dispatch_creates_one_execution_per_daily_task(monkeypatch):
    repository = _Repository()
    monkeypatch.setattr(scheduling, "is_trade_day", lambda _value: True)

    result = scheduling.dispatch_daily_acquisitions(
        date(2026, 9, 28),
        us_target_date=date(2026, 9, 25),
        repository=repository,
    )

    expected = {
        item.task_key
        for item in acquisition_task_blueprints()
        if (
            item.cadence == "daily"
            and item.task_key not in scheduling.DEFERRED_RESEARCH_DATASETS
        )
    }
    assert "stock_st" in expected
    assert "us_daily" not in expected
    assert result == {
        "target_date": "2026-09-28",
        "delayed_target_date": "2026-09-28",
        "us_target_date": "2026-09-25",
        "trade_day": True,
        "eligible": len(expected),
        "created": len(expected),
        "existing": 0,
        "skipped": None,
        "errors": {},
    }
    assert {item.task_key for item in repository.requests} == expected
    assert all(item.purpose.value == "daily" for item in repository.requests)
    by_task = {item.task_key: item for item in repository.requests}
    assert all(
        by_task[task_key].observation_start
        == by_task[task_key].observation_end
        == date(2026, 9, 25)
        for task_key in (
            scheduling.US_COMPLETED_SESSION_TASKS
            - scheduling.DEFERRED_RESEARCH_DATASETS
        )
    )
    assert all(
        item.observation_start == item.observation_end == date(2026, 9, 28)
        for item in repository.requests
        if item.task_key not in scheduling.US_COMPLETED_SESSION_TASKS
    )
    assert len({item.idempotency_key for item in repository.requests}) == len(expected)


def test_daily_dispatch_does_not_create_weekend_work(monkeypatch):
    repository = _Repository()
    monkeypatch.setattr(scheduling, "is_trade_day", lambda _value: False)

    result = scheduling.dispatch_daily_acquisitions(
        date(2026, 9, 27),
        us_target_date=date(2026, 9, 25),
        repository=repository,
    )

    assert result["skipped"] == "not_a_trade_day"
    assert repository.requests == []


def test_closed_day_keeps_next_morning_tasks_on_prior_open_day(monkeypatch):
    repository = _Repository()
    def calendar_query(statement, _params):
        if "us_tradecal" in statement:
            return [{"cal_date": date(2026, 10, 9)}]
        return [
            {"cal_date": date(2026, 10, 9)},
            {"cal_date": date(2026, 10, 8)},
            {"cal_date": date(2026, 9, 30)},
        ]

    monkeypatch.setattr(scheduling, "query", calendar_query)
    monkeypatch.setattr(scheduling, "is_trade_day", lambda _value: True)

    result = scheduling.dispatch_latest_daily_acquisitions(
        date(2026, 10, 11),
        include_current_daily=True,
        repository=repository,
    )

    assert result["target_date"] == "2026-10-09"
    assert result["delayed_target_date"] == "2026-10-08"
    assert result["superseded_not_due"] == 4
    assert result["requeued_after_release"] == 0
    assert repository.superseded[0][0] == date(2026, 10, 9)
    assert set(repository.superseded[0][1]) == {
        "ccass_hold", "etf_share_size", "margin", "margin_detail"
    }
    by_task = {item.task_key: item for item in repository.requests}
    assert "us_daily" not in by_task
    assert by_task["margin"].observation_key == "2026-10-08"
    assert by_task["margin_detail"].observation_key == "2026-10-08"


def test_open_day_dispatches_previous_day_after_next_morning_release(monkeypatch):
    repository = _Repository()
    def calendar_query(statement, _params):
        if "us_tradecal" in statement:
            return [{"cal_date": date(2026, 10, 12)}]
        return [
            {"cal_date": date(2026, 10, 12)},
            {"cal_date": date(2026, 10, 9)},
            {"cal_date": date(2026, 10, 8)},
        ]

    monkeypatch.setattr(scheduling, "query", calendar_query)
    monkeypatch.setattr(scheduling, "is_trade_day", lambda _value: True)

    result = scheduling.dispatch_latest_daily_acquisitions(
        date(2026, 10, 12),
        include_current_daily=False,
        next_morning_released=True,
        repository=repository,
    )

    by_task = {item.task_key: item for item in repository.requests}
    assert "us_daily" not in by_task
    assert by_task["margin"].observation_key == "2026-10-09"
    assert by_task["margin_detail"].observation_key == "2026-10-09"
    assert result["superseded_not_due"] == 0
    assert result["requeued_after_release"] == 4
    assert repository.requeued[0][0] == date(2026, 10, 9)


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
    assert policies.get("stock_basic").cadence == "daily"
    assert (
        policies.get("cyq_perf").cadence,
        policies.get("cyq_perf").parameter_strategy,
    ) == ("weekly", "ts_code_fanout")


def test_cyq_perf_is_dispatched_as_one_closed_week(monkeypatch):
    repository = _Repository()
    monkeypatch.setattr(
        scheduling,
        "dispatch_latest_daily_acquisitions",
        lambda *_args, **_kwargs: {
            "eligible": 0,
            "created": 0,
            "existing": 0,
            "errors": {},
        },
    )

    scheduling.dispatch_due_acquisitions(
        date(2026, 10, 21),
        include_current_daily=False,
        repository=repository,
    )

    request = next(item for item in repository.requests if item.task_key == "cyq_perf")
    assert request.observation_key == "2026-W42"
    assert request.observation_start == date(2026, 10, 12)
    assert request.observation_end == date(2026, 10, 18)
    assert request.frozen_scope["cadence"] == "weekly"


def test_daily_schedule_has_no_unbatched_dynamic_entity_fanout():
    # factor_value has about 202 governed factor-name children.  One exact-day
    # run remains below its 1,000-call allowance, while a multi-day child can
    # silently hit the provider's 6,000-row response cap.
    exempt = {*MARKET_WIDE_FANOUT_OVERRIDES, "dividend", "factor_value"}
    unsafe = []
    for blueprint in acquisition_task_blueprints():
        fanout = FANOUT_DEFINITIONS.get(blueprint.task_key)
        if (
            blueprint.cadence == "daily"
            and fanout is not None
            and fanout.source != "static"
            and blueprint.task_key not in exempt
        ):
            unsafe.append(blueprint.task_key)

    assert unsafe == []


def test_legacy_ggt_catalog_gap_still_builds_bounded_trade_date_request():
    policy = TusharePolicyRegistry().get("ggt_daily")

    assert parameters_for_policy(
        policy,
        set(),
        today=date(2026, 9, 28),
        trade_date="20260925",
    ) == {"trade_date": "20260925"}
