from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

import collectors.scheduler as scheduler_module
from collectors.scheduler import create_scheduler, enqueue_scheduled_collection


@pytest.fixture(autouse=True)
def _enable_routine_mode_for_unit_tests(monkeypatch):
    """Unit scheduling behavior must not depend on a developer database mode."""
    import service.initialization.repository as initialization_repository

    monkeypatch.setattr(
        initialization_repository, "routine_collection_enabled", lambda: True
    )


def test_index_daily_schedule_collects_full_market_with_offset_exhaustion(monkeypatch):
    import collectors.index.daily as index_daily_module

    calls = []

    class Result:
        stored_rows = 9206
        evidence = {"pages_completed": 10, "exhausted": True}

    class FakeCollector:
        def run_offset_paginated(self, **parameters):
            calls.append(parameters)
            return Result()

    monkeypatch.setattr(index_daily_module, "IndexDailyCollector", FakeCollector)
    monkeypatch.setattr(scheduler_module, "_is_trade_day", lambda _value: True)
    monkeypatch.setattr(
        scheduler_module,
        "business_now",
        lambda: datetime(2026, 9, 3, 16, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
    )

    assert scheduler_module.run_index_daily.__wrapped__() == 9206
    assert calls == [
        {"trade_date": "20260903", "page_size": 1000, "max_pages": 100}
    ]


def test_income_bootstrap_recollects_nonempty_periods_instead_of_skipping(monkeypatch):
    import collectors.stock.finance.income as income_module
    import time

    periods = []

    class FakeCollector:
        def collect(self, *, period):
            periods.append(period)
            return 1

    monkeypatch.setattr(income_module, "IncomeCollector", FakeCollector)
    monkeypatch.setattr(time, "sleep", lambda _seconds: None)

    assert scheduler_module.run_income_bootstrap.__wrapped__() == 21
    assert periods[0] == "20200331"
    assert periods[-1] == "20250331"
    assert len(periods) == 21


def test_scheduler_registers_expected_jobs_with_tracking():
    scheduler = create_scheduler()
    jobs = {job.id: job for job in scheduler.get_jobs()}

    assert len(jobs) == 43
    collection_job_ids = (
        "daily_daily",
        "index_daily_daily",
        "fx_daily_daily",
        "sge_daily_daily",
    )
    for job_id in collection_job_ids:
        assert job_id in jobs
        assert jobs[job_id].func is enqueue_scheduled_collection
        assert jobs[job_id].args == (job_id,)
        assert hasattr(scheduler_module._SCHEDULED_COLLECTION_TASKS[job_id], "__wrapped__")

    for job_id in (
        "tushare_policy_dispatch",
        "data_coverage_dispatch",
    ):
        assert job_id in jobs
        assert hasattr(jobs[job_id].func, "__wrapped__")

    assert jobs["service_heartbeat"].func is scheduler_module.run_scheduler_heartbeat
    assert "hour='16,19,23'" in str(jobs["daily_daily"].trigger)
    assert "hour='16,19,23'" in str(jobs["bak_basic_daily"].trigger)
    for job_id in (
        "income_quarterly",
        "balancesheet_quarterly",
        "cashflow_quarterly",
        "fina_indicator_quarterly",
    ):
        fields = {field.name: str(field) for field in jobs[job_id].trigger.fields}
        assert fields["day_of_week"] == "mon-fri"
    assert "income_annual_update" not in jobs
    assert jobs["collection_schedule_reconciler"].func is (
        scheduler_module.run_collection_schedule_reconciler
    )
    assert jobs["collection_initialization_reconciler"].func is (
        scheduler_module.run_collection_initialization_reconciler
    )
    assert jobs["fanout_campaign_reconciler"].func is (
        scheduler_module.run_fanout_campaign_reconciler
    )


def test_routine_schedule_is_gated_until_initialization_finishes(monkeypatch):
    import service.initialization.repository as initialization_repository

    monkeypatch.setattr(
        initialization_repository, "routine_collection_enabled", lambda: False
    )

    class ForbiddenRepository:
        def create(self, *_args, **_kwargs):
            pytest.fail("no routine job may be created before initialization activation")

    assert enqueue_scheduled_collection(
        "daily_daily", repository=ForbiddenRepository()
    ) == 0


def test_scheduled_task_contract_rejects_non_whitelisted_callables():
    validated = scheduler_module.scheduled_collection_ids()
    assert "daily_daily" in validated
    assert "inspector_15min" not in validated


def test_scheduled_jobs_persist_their_canonical_interface_identity(monkeypatch):
    import service.initialization.repository as initialization_repository

    monkeypatch.setattr(
        initialization_repository, "routine_collection_enabled", lambda: True
    )
    observed = {}

    class Repository:
        def create(self, *_args, **kwargs):
            observed.update(kwargs)
            return ({"job_id": 7}, True)

    class Cursors:
        def advance(self, *_args, **_kwargs):
            return True

    assert enqueue_scheduled_collection(
        "daily_daily", repository=Repository(), cursor_repository=Cursors()
    ) == 1
    assert observed["api_name"] == "daily"


def test_week_month_dedicated_mapping_matches_registered_schedule_ids():
    from service.tushare_scheduling import DEDICATED_RUN_IDS

    registered = scheduler_module.scheduled_collection_ids()
    assert set(DEDICATED_RUN_IDS["stk_weekly_monthly"]) <= registered


def test_schedule_reconciler_submits_each_missed_date(monkeypatch):
    scheduler = create_scheduler()
    submitted = []

    class FakeCursors:
        def get(self, _schedule_id):
            return {
                "last_dispatched_for": datetime(
                    2026, 8, 26, 0, 0, tzinfo=ZoneInfo("Asia/Shanghai")
                ),
                "last_job_id": 42,
            }

    monkeypatch.setattr(
        scheduler_module,
        "enqueue_scheduled_collection",
        lambda schedule_id, scheduled_for, **_kwargs: submitted.append(
            (schedule_id, scheduled_for)
        ) or 1,
    )
    count = scheduler_module.reconcile_collection_schedules(
        scheduler,
        now=datetime(2026, 8, 28, 21, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        cursor_repository=FakeCursors(),
    )

    assert count == len(submitted)
    assert count > 0
    assert all(schedule_id not in scheduler_module._CONTROL_JOB_IDS for schedule_id, _ in submitted)
    assert all(fire_time <= datetime(2026, 8, 28, 21, 0, tzinfo=ZoneInfo("Asia/Shanghai")) for _, fire_time in submitted)

    daily_fires = [
        fire_time
        for schedule_id, fire_time in submitted
        if schedule_id == "daily_daily"
    ]
    assert [item.date().isoformat() for item in daily_fires] == [
        "2026-08-26",
        "2026-08-27",
        "2026-08-28",
    ]


def test_schedule_reconciler_replays_each_bounded_date_for_new_schedules(monkeypatch):
    scheduler = create_scheduler()
    submitted = []
    bootstrapped = []

    class EmptyCursors:
        def get(self, _schedule_id):
            return None

        def bootstrap(self, schedule_id, scheduled_for, **_metadata):
            bootstrapped.append((schedule_id, scheduled_for))
            return True

    monkeypatch.setattr(
        scheduler_module,
        "enqueue_scheduled_collection",
        lambda schedule_id, scheduled_for, **_kwargs: submitted.append(
            (schedule_id, scheduled_for)
        ) or 1,
    )
    count = scheduler_module.reconcile_collection_schedules(
        scheduler,
        now=datetime(2026, 8, 28, 21, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        cursor_repository=EmptyCursors(),
    )

    assert count == len(submitted)
    assert count > 0
    assert bootstrapped  # schedules with no fire inside the bounded window
    assert all(
        fire_time >= datetime(2026, 8, 20, 21, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
        for _, fire_time in submitted
    )


def test_schedule_reconciler_does_not_let_weekend_hide_friday(monkeypatch):
    scheduler = create_scheduler()
    submitted = []

    class FridayCursor:
        def get(self, _schedule_id):
            return {
                "last_dispatched_for": datetime(
                    2026, 8, 27, 23, 59, tzinfo=ZoneInfo("Asia/Shanghai")
                ),
                "last_job_id": 42,
            }

    monkeypatch.setattr(
        scheduler_module,
        "enqueue_scheduled_collection",
        lambda schedule_id, scheduled_for, **_kwargs: submitted.append(
            (schedule_id, scheduled_for)
        ) or 1,
    )

    scheduler_module.reconcile_collection_schedules(
        scheduler,
        now=datetime(2026, 8, 30, 21, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        cursor_repository=FridayCursor(),
    )

    stk_limit_dates = [
        fire_time.date().isoformat()
        for schedule_id, fire_time in submitted
        if schedule_id == "stk_limit_daily"
    ]
    assert stk_limit_dates == ["2026-08-28", "2026-08-29", "2026-08-30"]


def test_schedule_reconciler_repairs_bootstrap_cursor_without_a_job(monkeypatch):
    scheduler = create_scheduler()
    submitted = []

    class BootstrapCursor:
        def get(self, _schedule_id):
            return {
                "last_dispatched_for": datetime(
                    2026, 8, 28, 0, 0, tzinfo=ZoneInfo("Asia/Shanghai")
                ),
                "last_job_id": None,
            }

    monkeypatch.setattr(
        scheduler_module,
        "enqueue_scheduled_collection",
        lambda schedule_id, scheduled_for, **_kwargs: submitted.append(
            (schedule_id, scheduled_for)
        ) or 1,
    )
    count = scheduler_module.reconcile_collection_schedules(
        scheduler,
        now=datetime(2026, 8, 28, 21, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        cursor_repository=BootstrapCursor(),
    )

    assert count == len(submitted)
    assert count > 0


def test_catch_up_collector_uses_planned_business_time(monkeypatch):
    from service.clock import business_today

    observed = []
    monkeypatch.setattr(
        scheduler_module,
        "run_daily",
        lambda: observed.append(business_today().isoformat()) or 2,
    )

    result = scheduler_module.execute_scheduled_collection(
        "daily_daily", "2026-08-28T16:00:00+08:00"
    )

    assert result.rows_inserted == 2
    assert observed == ["2026-08-28"]


def test_scheduled_zero_rows_is_not_misclassified_as_verified_empty(monkeypatch):
    monkeypatch.setattr(scheduler_module, "run_stk_limit", lambda: 0)

    result = scheduler_module.execute_scheduled_collection(
        "stk_limit_daily", "2026-08-31T09:00:00+08:00"
    )

    assert result.rows_fetched == 0
    assert result.completion_status == "unverified"
    assert result.completion_evidence["verified"] is False
    assert result.completion_evidence["zero_result_reason"] == (
        "scheduled_collector_zero_is_ambiguous"
    )


def test_stock_limit_has_same_day_publication_delay_retries():
    job = create_scheduler().get_job("stk_limit_daily")
    fields = {field.name: str(field) for field in job.trigger.fields}

    assert fields["hour"] == "9,10,12"


@pytest.mark.parametrize(
    ("month", "expected_period"),
    [(2, "20251231"), (4, "20260331"), (7, "20260630"), (10, "20260930")],
)
def test_finance_refresh_tracks_the_current_disclosure_period(
    monkeypatch, month, expected_period
):
    import collectors.stock.finance.income as income_module

    periods = []

    class FakeCollector:
        def collect(self, *, period):
            periods.append(period)
            return 1

    monkeypatch.setattr(income_module, "IncomeCollector", FakeCollector)
    monkeypatch.setattr(
        scheduler_module,
        "business_now",
        lambda: datetime(2026, month, 15, 21, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
    )

    assert scheduler_module.run_income.__wrapped__() == 1
    assert periods == [expected_period]


def test_policy_and_coverage_patrols_wait_for_next_morning_publications():
    scheduler = create_scheduler()
    policy_fields = {
        field.name: str(field)
        for field in scheduler.get_job("tushare_policy_dispatch").trigger.fields
    }
    coverage_fields = {
        field.name: str(field)
        for field in scheduler.get_job("data_coverage_dispatch").trigger.fields
    }

    assert policy_fields["hour"] == "7,9,13,19,23"
    assert policy_fields["minute"] == "15"
    assert coverage_fields["hour"] == "9"
    assert coverage_fields["minute"] == "30"


@pytest.mark.parametrize(("hour", "expected_current"), [(13, False), (19, True), (23, True)])
def test_policy_patrol_switches_to_current_trade_date_after_close(
    monkeypatch, hour, expected_current
):
    import service.fanout_scheduling as fanout_scheduling
    import service.tushare_scheduling as tushare_scheduling

    observed = []
    monkeypatch.setattr(
        scheduler_module,
        "business_now",
        lambda: datetime(2026, 8, 31, hour, 10, tzinfo=ZoneInfo("Asia/Shanghai")),
    )
    monkeypatch.setattr(
        tushare_scheduling,
        "submit_latest_policy_batches",
        lambda **kwargs: observed.append(("policy", kwargs)) or {"daily": 0},
    )
    monkeypatch.setattr(
        fanout_scheduling,
        "submit_latest_scheduled_fanouts",
        lambda **kwargs: observed.append(("fanout", kwargs))
        or {"daily": {"created": 0, "failed": 0}},
    )

    scheduler_module.run_tushare_policy_dispatch.__wrapped__()

    assert observed[0][1]["today"].isoformat() == "2026-08-31"
    assert observed[0][1]["include_current_daily"] is expected_current
    assert observed[1][1]["include_current_daily"] is expected_current


@pytest.mark.parametrize(
    ("function_name", "module_name", "class_name", "expected_keys"),
    [
        (
            "run_stk_limit",
            "collectors.stock.market.stk_limit",
            "STKLimitCollector",
            {"trade_date", "page_size", "max_pages"},
        ),
        ("run_suspend_d", "collectors.stock.market.suspend_d", "SuspendDCollector", {"trade_date"}),
        ("run_hsgt_top10", "collectors.stock.market.hsgt_top10", "HsgtTop10Collector", {"trade_date"}),
        ("run_ggt_top10", "collectors.stock.market.ggt_top10", "GgtTop10Collector", {"trade_date"}),
        ("run_ggt_daily", "collectors.stock.market.ggt_daily", "GgtDailyCollector", {"start_date", "end_date"}),
        ("run_ggt_monthly", "collectors.stock.market.ggt_monthly", "GgtMonthlyCollector", {"start_month", "end_month"}),
    ],
)
def test_scheduler_uses_collector_pipeline_and_keyword_parameters(
    monkeypatch,
    function_name,
    module_name,
    class_name,
    expected_keys,
):
    module = __import__(module_name, fromlist=[class_name])
    calls = []

    class FakeCollector:
        def collect(self, **parameters):
            calls.append(parameters)
            return 7

        def run_offset_paginated(self, **parameters):
            calls.append(parameters)

            class Result:
                stored_rows = 7

            return Result()

    monkeypatch.setattr(module, class_name, FakeCollector)
    monkeypatch.setattr(scheduler_module, "_is_trade_day", lambda _date: True)

    result = getattr(scheduler_module, function_name).__wrapped__()

    assert result == 7
    assert len(calls) == 1
    assert set(calls[0]) == expected_keys
