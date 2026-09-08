from datetime import date, datetime, timedelta, timezone

import pytest

from service.collection_jobs.models import InvalidTaskParametersError
from service.initialization.service import (
    CATALOG_MONTHLY_WINDOW_HISTORY,
    CATALOG_WINDOW_HISTORY,
    FULL_HISTORY_START,
    InitializationService,
    PLANNING_BATCH_SIZE,
    _published_quarter_ends,
)
from service.history_baselines import INITIALIZATION_STRICT_COVERAGE_LOOKBACK_DAYS


def campaign(**overrides):
    value = {
        "initialization_id": 9,
        "profile": "standard",
        "history_start": date(2025, 1, 1),
        "history_end": date(2026, 8, 28),
        "auto_activate": True,
        "status": "running",
        "current_phase": 0,
        "phase_name": "foundation",
        "planned_steps": 0,
        "completed_steps": 0,
        "failed_steps": 0,
        "verification_round": 1,
    }
    value.update(overrides)
    return value


class FakeRepository:
    def __init__(self, value, steps):
        self.value = value
        self.steps = steps
        self.activated = False
        self.deleted_steps = []
        self.auto_recovery_count = int(
            (self.value.get("options") or {}).get(
                "transient_auto_recovery_count", 0
            )
        )

    def active(self):
        return dict(self.value)

    def get(self, _initialization_id):
        return dict(self.value)

    def phase_steps(self, _initialization_id, _phase):
        return list(self.steps)

    def trade_dates(self, _start_date, _end_date):
        return []

    def update_progress(self, _initialization_id, *, planned, completed, failed, error_message):
        self.value.update(
            planned_steps=planned,
            completed_steps=completed,
            failed_steps=failed,
            error_message=error_message,
        )

    def advance(self, _initialization_id, phase, phase_name):
        self.value.update(
            current_phase=phase,
            phase_name=phase_name,
            planned_steps=0,
            completed_steps=0,
            failed_steps=0,
            error_message=None,
        )

    def set_status(self, _initialization_id, status, *, error_message=None):
        self.value.update(status=status, error_message=error_message)

    def activate(self, _initialization_id):
        assert self.value["status"] == "ready"
        self.value["status"] = "completed"
        self.activated = True

    def delete_step(self, step_id):
        self.deleted_steps.append(step_id)
        self.steps = [step for step in self.steps if step.get("step_id") != step_id]

    def increment_round(self, _initialization_id):
        self.value["verification_round"] += 1
        return self.value["verification_round"]

    def claim_transient_auto_recovery(self, _initialization_id, *, max_recoveries):
        if self.auto_recovery_count >= max_recoveries:
            return None
        self.auto_recovery_count += 1
        self.value.setdefault("options", {})[
            "transient_auto_recovery_count"
        ] = self.auto_recovery_count
        return self.auto_recovery_count


def service_with(repository):
    service = InitializationService(
        repository=repository,
        job_service=object(),
        coverage_service=object(),
    )
    service._plan_phase = lambda _campaign: True
    return service


class PlanningRepository:
    def __init__(self, trade_dates=()):
        self.dates = list(trade_dates)
        self.steps = []

    def trade_dates(self, _start_date, _end_date):
        return self.dates

    def add_collection_step(
        self, initialization_id, phase, step_key, job_id, *, allow_empty, require_verified
    ):
        self.steps.append(step_key)

    def add_coverage_step(self, initialization_id, phase, step_key, coverage_job_id):
        self.steps.append(step_key)

    def add_fanout_step(
        self, initialization_id, phase, step_key, fanout_campaign_id, *, allow_empty
    ):
        self.steps.append(step_key)


class PlanningJobs:
    def __init__(self):
        self.calls = []

    def submit(self, task_name, parameters, **kwargs):
        self.calls.append((task_name, parameters, kwargs))
        return {"job_id": len(self.calls)}, True


class PlanningCoverage:
    def __init__(self):
        self.calls = []

    def submit_audits(self, datasets, **kwargs):
        self.calls.append((datasets, kwargs))
        return {"jobs": [{"job_id": len(self.calls)}]}


class PlanningFanout:
    def __init__(self):
        self.calls = []

    def submit(self, request, **kwargs):
        self.calls.append((request, kwargs))
        return {"campaign_id": len(self.calls)}, True


class StartRepository:
    def __init__(self):
        self.value = None

    def create(self, **kwargs):
        self.value = campaign(**kwargs)
        return dict(self.value), False

    def get(self, _initialization_id):
        return dict(self.value)


def collection_step(completion_status="complete", **overrides):
    value = {
        "resource_type": "collection",
        "collection_status": "success",
        "completion_status": completion_status,
        "completion_evidence": {"verified": True},
        "allow_empty": False,
        "require_verified": True,
    }
    value.update(overrides)
    return value


def test_financial_periods_only_include_published_quarters():
    assert _published_quarter_ends(
        date(2025, 1, 1), date(2025, 8, 30)
    ) == [date(2025, 3, 31)]
    assert _published_quarter_ends(
        date(2024, 12, 1), date(2025, 8, 31)
    ) == [date(2024, 12, 31), date(2025, 3, 31), date(2025, 6, 30)]


def test_full_profile_is_discoverable_with_market_history_start():
    full = next(
        item for item in InitializationService.profiles() if item["name"] == "full"
    )
    assert full["history_days"] is None
    assert full["history_start"] == FULL_HISTORY_START.isoformat()


def test_full_profile_defaults_to_all_market_history_and_bypasses_ten_year_limit():
    repository = StartRepository()
    service = InitializationService(
        repository=repository,
        job_service=PlanningJobs(),
        coverage_service=PlanningCoverage(),
    )

    result, created = service.start(
        profile="full",
        history_start=None,
        history_end=date(2026, 8, 28),
        auto_activate=True,
        idempotency_key="full-history-unit-test",
    )

    assert created is False
    assert result["history_start"] == FULL_HISTORY_START
    with pytest.raises(InvalidTaskParametersError, match="cannot start before"):
        service.start(
            profile="full",
            history_start=date(1990, 12, 18),
            history_end=date(2026, 8, 28),
            auto_activate=True,
            idempotency_key="full-history-too-early",
        )


def test_foundation_exhausts_both_fund_basic_markets():
    repository = PlanningRepository()
    jobs = PlanningJobs()
    service = InitializationService(
        repository=repository, job_service=jobs, coverage_service=PlanningCoverage()
    )

    assert service._plan_foundation(campaign(profile="full"), set()) is True

    fund_calls = [
        parameters
        for task_name, parameters, _options in jobs.calls
        if task_name == "tushare_interface"
        and parameters["api_name"] == "fund_basic"
    ]
    assert {item["parameters"]["market"] for item in fund_calls} == {"E", "O"}
    assert all(item["complete"] is True and item["resume"] is True for item in fund_calls)


def test_full_history_uses_dataset_specific_reliable_start_dates():
    repository = PlanningRepository(
        [
            date(1995, 1, 3),
            date(1997, 1, 3),
            date(2007, 1, 4),
            date(2010, 1, 4),
        ]
    )
    jobs = PlanningJobs()
    service = InitializationService(
        repository=repository, job_service=jobs, coverage_service=PlanningCoverage()
    )

    complete = service._plan_core_history(
        campaign(profile="full", history_start=FULL_HISTORY_START), set()
    )

    assert complete is True
    tasks_by_date = {}
    for task_name, parameters, _kwargs in jobs.calls:
        if task_name == "tushare_interface":
            trade_date = parameters["parameters"]["trade_date"]
            logical_task = parameters["api_name"]
        else:
            trade_date = parameters["trade_date"]
            logical_task = task_name
        tasks_by_date.setdefault(trade_date, set()).add(logical_task)
    assert tasks_by_date["19950103"] == {
        "stock_daily", "stock_daily_basic", "index_daily"
    }
    assert tasks_by_date["19970103"] == {
        "stock_daily", "stock_daily_basic", "index_daily"
    }
    assert tasks_by_date["20070104"] == {
        "stock_daily", "stock_daily_basic", "stock_limit", "index_daily"
    }
    assert tasks_by_date["20100104"] == {
        "stock_daily", "stock_daily_basic", "moneyflow", "stock_limit",
        "index_daily",
    }


def test_full_history_collects_kpl_concepts_from_contract_start():
    repository = PlanningRepository([date(2024, 10, 11), date(2024, 10, 14)])
    jobs = PlanningJobs()
    service = InitializationService(
        repository=repository, job_service=jobs, coverage_service=PlanningCoverage()
    )

    assert service._plan_core_history(
        campaign(profile="full", history_start=FULL_HISTORY_START), set()
    ) is True

    kpl_dates = [
        parameters["parameters"]["trade_date"]
        for task_name, parameters, _options in jobs.calls
        if task_name == "tushare_interface"
        and parameters["api_name"] == "kpl_concept_cons"
    ]
    assert kpl_dates == ["20241014"]
    kpl_payload = next(
        parameters
        for task_name, parameters, _options in jobs.calls
        if task_name == "tushare_interface"
        and parameters["api_name"] == "kpl_concept_cons"
    )
    assert kpl_payload["page_size"] == 3000


def test_finance_history_includes_verified_auxiliary_period_collectors():
    repository = PlanningRepository()
    jobs = PlanningJobs()
    service = InitializationService(
        repository=repository, job_service=jobs, coverage_service=PlanningCoverage()
    )

    assert service._plan_finance_history(
        campaign(
            history_start=date(2025, 1, 1),
            history_end=date(2025, 5, 1),
            current_phase=2,
            phase_name="finance_history",
        ),
        set(),
    ) is True

    interfaces = {
        parameters["api_name"]
        for task_name, parameters, _kwargs in jobs.calls
        if task_name == "tushare_interface"
    }
    assert interfaces == {"disclosure_date", "express", "forecast", "fina_mainbz"}
    assert all(
        parameters["parameters"] == {"period": "20250331"}
        for task_name, parameters, _kwargs in jobs.calls
        if task_name == "tushare_interface"
    )


def test_large_history_planning_is_bounded_per_reconcile():
    dates = [date(2020, 1, 1) + timedelta(days=day) for day in range(126)]
    repository = PlanningRepository(dates)
    jobs = PlanningJobs()
    service = InitializationService(
        repository=repository, job_service=jobs, coverage_service=PlanningCoverage()
    )

    complete = service._plan_core_history(campaign(profile="full"), set())

    assert complete is False
    assert len(jobs.calls) == PLANNING_BATCH_SIZE


def test_core_history_progress_uses_stable_logical_total_not_materialized_batch():
    dates = [
        date(1995, 1, 3),
        date(2007, 1, 4),
        date(2010, 1, 4),
        date(2024, 10, 14),
    ]
    repository = PlanningRepository(dates)
    service = InitializationService(
        repository=repository,
        job_service=PlanningJobs(),
        coverage_service=PlanningCoverage(),
    )

    result = service._decorate(
        campaign(
            profile="full",
            history_start=FULL_HISTORY_START,
            current_phase=1,
            phase_name="core_history",
            planned_steps=5,
            completed_steps=4,
        )
    )

    # 3 + 4 + 5 + 6 datasets are eligible on the four boundary dates.
    assert result["materialized_steps"] == 5
    assert result["logical_total_steps"] == 18
    assert result["remaining_steps"] == 14
    assert result["progress_ratio"] == 4 / 18
    assert result["progress_basis"] == "logical_total"


def test_initialization_progress_exposes_current_materialized_work_range():
    repository = PlanningRepository()
    repository.phase_work_window = lambda _initialization_id, _phase: {
        "materialized_start": date(2018, 1, 1),
        "materialized_end": date(2018, 4, 30),
        "active_start": date(2018, 3, 1),
        "active_end": date(2018, 4, 30),
        "queued": 120,
        "running": 2,
        "completed": 378,
        "failed": 0,
        "resources": [{"resource": "daily", "queued": 60, "running": 1}],
    }
    service = InitializationService(
        repository=repository,
        job_service=PlanningJobs(),
        coverage_service=PlanningCoverage(),
    )

    result = service._decorate(campaign(current_phase=1, phase_name="core_history"))

    assert result["work_window"]["active_start"] == date(2018, 3, 1)
    assert result["work_window"]["queued"] == 120


def test_catalog_history_uses_bounded_windows_and_all_libor_currencies():
    repository = PlanningRepository()
    jobs = PlanningJobs()
    service = InitializationService(
        repository=repository, job_service=jobs, coverage_service=PlanningCoverage()
    )

    assert service._plan_catalog_history(
        campaign(
            history_start=date(2026, 1, 1),
            history_end=date(2026, 2, 28),
            current_phase=3,
            phase_name="catalog_history",
        ),
        set(),
    ) is True

    calls = {name: [] for name in (*CATALOG_WINDOW_HISTORY, *CATALOG_MONTHLY_WINDOW_HISTORY)}
    for task_name, parameters, options in jobs.calls:
        assert task_name == "tushare_interface"
        assert parameters["complete"] is True
        assert options["resource_class"] == "initialization"
        calls[parameters["api_name"]].append(parameters["parameters"])
    assert len(calls["libor"]) == 5
    assert {item["curr_type"] for item in calls["libor"]} == {
        "USD", "EUR", "JPY", "GBP", "CHF"
    }
    assert len(calls["slb_sec_detail"]) == 2
    assert calls["slb_sec_detail"][0] == {
        "start_date": "20260101", "end_date": "20260131"
    }


def test_full_history_verification_respects_dataset_start_dates():
    repository = PlanningRepository()
    coverage = PlanningCoverage()
    service = InitializationService(
        repository=repository, job_service=PlanningJobs(), coverage_service=coverage
    )

    assert service._plan_verification(
        campaign(
            profile="full",
            history_start=FULL_HISTORY_START,
            current_phase=6,
            phase_name="verification",
        ),
        set(),
    ) is True

    starts = {datasets[0]: kwargs["start_date"] for datasets, kwargs in coverage.calls}
    strict_start = date(2026, 8, 28) - timedelta(
        days=INITIALIZATION_STRICT_COVERAGE_LOOKBACK_DAYS - 1
    )
    assert starts["stock_daily"] == strict_start
    assert starts["stock_limit"] == strict_start
    assert starts["moneyflow"] == strict_start
    assert starts["index_daily"] == strict_start
    assert starts["kpl_concept_cons"] == date(2024, 10, 14)


def test_full_initialization_plans_verified_whole_universe_fanouts():
    repository = PlanningRepository()
    fanout = PlanningFanout()
    jobs = PlanningJobs()
    service = InitializationService(
        repository=repository,
        job_service=jobs,
        coverage_service=PlanningCoverage(),
        fanout_service=fanout,
    )

    assert service._plan_fanout_baseline(
        campaign(profile="full", current_phase=5, phase_name="fanout_baseline"),
        set(),
    ) is True

    assert [call[0]["api_name"] for call in fanout.calls] == [
        "cb_rate",
        "cb_rating",
        "ci_index_member",
        "fut_basic",
        "fut_index_daily",
        "index_member_all",
        "pledge_stat",
        "top10_cb_holders",
        "cyq_chips",
        "cyq_perf",
        "fina_audit",
        "stk_rewards",
        "top10_floatholders",
        "top10_holders",
        "index_weight",
        "fut_weekly_monthly",
        "stk_week_month_adj",
    ]
    assert all(call[0]["page_size"] == 200 for call in fanout.calls)
    assert repository.steps[:17] == [
        "fanout:cb_rate",
        "fanout:cb_rating",
        "fanout:ci_index_member",
        "fanout:fut_basic",
        "fanout:fut_index_daily",
        "fanout:index_member_all",
        "fanout:pledge_stat",
        "fanout:top10_cb_holders",
        "fanout:cyq_chips",
        "fanout:cyq_perf",
        "fanout:fina_audit",
        "fanout:stk_rewards",
        "fanout:top10_floatholders",
        "fanout:top10_holders",
        "fanout:index_weight",
        "fanout:fut_weekly_monthly",
        "fanout:stk_week_month_adj",
    ]
    assert all(
        call[1]["cadence"] == "initialization"
        and call[1]["period_key"] == "initial-2026-08-28"
        for call in fanout.calls
    )
    requests = {call[0]["api_name"]: call[0] for call in fanout.calls}
    # 2026 Q2 is not publication-mature until 08-31.
    assert requests["top10_cb_holders"]["period"] == "2026-03-31"
    assert requests["cyq_chips"] == {
        "api_name": "cyq_chips",
        "page_size": 200,
        "start_date": "2026-07-29",
        "end_date": "2026-08-28",
    }
    market_calls = [call for call in jobs.calls if call[0] == "tushare_interface"]
    fund_nav = [call for call in market_calls if call[1]["api_name"] == "fund_nav"]
    assert len(fund_nav) == 366
    assert fund_nav[0][1]["parameters"] == {"nav_date": "20250828"}
    assert fund_nav[-1][1]["parameters"] == {"nav_date": "20260828"}
    assert all(
        call[1]["page_size"] == 5000 and call[1]["max_pages"] == 100
        for call in fund_nav
    )
    fund_portfolio = [
        call for call in market_calls if call[1]["api_name"] == "fund_portfolio"
    ]
    assert len(fund_portfolio) == 1
    assert fund_portfolio[0][1]["parameters"] == {"period": "20260331"}
    assert fund_portfolio[0][1]["max_pages"] == 500
    progress = service._decorate(
        campaign(profile="full", current_phase=5, phase_name="fanout_baseline")
    )
    assert progress["logical_total_steps"] == 384


def test_non_full_initialization_skips_expensive_whole_universe_fanouts():
    fanout = PlanningFanout()
    service = InitializationService(
        repository=PlanningRepository(),
        job_service=PlanningJobs(),
        coverage_service=PlanningCoverage(),
        fanout_service=fanout,
    )

    assert service._plan_fanout_baseline(campaign(profile="standard"), set()) is True
    assert fanout.calls == []


def test_step_completion_is_fail_closed():
    assert InitializationService._step_state(collection_step()) == "complete"
    assert InitializationService._step_state(
        collection_step("complete", completion_evidence={})
    ) == "failed"
    assert InitializationService._step_state(
        {
            "resource_type": "fanout",
            "fanout_status": "running",
            "fanout_completion_status": "running",
            "allow_empty": False,
        }
    ) == "running"
    assert InitializationService._step_state(
        {
            "resource_type": "fanout",
            "fanout_status": "success",
            "fanout_completion_status": "complete",
            "allow_empty": False,
        }
    ) == "complete"
    assert InitializationService._step_state(
        {
            "resource_type": "fanout",
            "fanout_status": "attention",
            "fanout_completion_status": "incomplete",
            "allow_empty": False,
        }
    ) == "failed"
    assert InitializationService._step_state(
        collection_step(
            "complete",
            completion_evidence={"verification": {"verified": True}},
        )
    ) == "complete"
    assert InitializationService._step_state(collection_step("verifying")) == "running"
    assert InitializationService._step_state(collection_step("empty")) == "failed"
    assert InitializationService._step_state(
        collection_step("empty", allow_empty=True)
    ) == "complete"
    assert InitializationService._step_state(collection_step("unverified")) == "failed"
    assert InitializationService._step_state(
        {
            "resource_type": "coverage",
            "coverage_status": "success",
            "audit_status": "complete",
        }
    ) == "complete"
    assert InitializationService._step_state(
        {
            "resource_type": "coverage",
            "coverage_status": "success",
            "audit_status": "gaps",
        }
    ) == "failed"


def test_reconcile_advances_only_after_every_step_completes():
    repository = FakeRepository(campaign(), [collection_step(), collection_step()])

    result = service_with(repository).reconcile(9)

    assert result["current_phase"] == 1
    assert result["phase_name"] == "core_history"
    assert result["status"] == "running"


def test_reconcile_stops_for_attention_on_failed_step():
    repository = FakeRepository(campaign(), [collection_step("incomplete")])

    result = service_with(repository).reconcile(9)

    assert result["status"] == "attention"
    assert result["failed_steps"] == 1
    assert "require attention" in result["error_message"]


def test_reconcile_active_auto_recovers_settled_network_failures(monkeypatch):
    import service.initialization.service as initialization_module

    repository = FakeRepository(
        campaign(status="attention"),
        [
            collection_step(
                "failed",
                step_id=17,
                collection_status="failed",
                completion_evidence={
                    "failure": {"category": "network", "retryable": True}
                },
                collection_finished_at=datetime.now(timezone.utc) - timedelta(hours=1),
            )
        ],
    )
    service = service_with(repository)
    service._plan_phase = lambda _campaign: False
    monkeypatch.setattr(
        initialization_module, "INITIALIZATION_AUTO_RECOVERY_COOLDOWN_SECONDS", 300
    )
    monkeypatch.setattr(
        initialization_module, "INITIALIZATION_AUTO_RECOVERY_MAX_ROUNDS", 3
    )

    result = service.reconcile_active()

    assert result["status"] == "running"
    assert repository.deleted_steps == [17]
    assert repository.value["verification_round"] == 2
    assert repository.auto_recovery_count == 1


def test_reconcile_active_keeps_completeness_failure_in_attention(monkeypatch):
    import service.initialization.service as initialization_module

    repository = FakeRepository(
        campaign(status="attention"),
        [
            collection_step(
                "incomplete",
                step_id=18,
                collection_status="failed",
                completion_evidence={
                    "failure": {"category": "completeness", "retryable": True}
                },
                collection_finished_at=datetime.now(timezone.utc) - timedelta(hours=1),
            )
        ],
    )
    monkeypatch.setattr(
        initialization_module, "INITIALIZATION_AUTO_RECOVERY_MAX_ROUNDS", 3
    )

    result = service_with(repository).reconcile_active()

    assert result["status"] == "attention"
    assert repository.deleted_steps == []


def test_reconcile_active_stops_after_bounded_transient_recoveries(monkeypatch):
    import service.initialization.service as initialization_module

    repository = FakeRepository(
        campaign(
            status="attention",
            verification_round=11,
            options={"transient_auto_recovery_count": 3},
        ),
        [
            collection_step(
                "failed",
                step_id=19,
                collection_status="failed",
                completion_evidence={
                    "failure": {"category": "network", "retryable": True}
                },
                collection_finished_at=datetime.now(timezone.utc) - timedelta(hours=1),
            )
        ],
    )
    monkeypatch.setattr(
        initialization_module, "INITIALIZATION_AUTO_RECOVERY_MAX_ROUNDS", 3
    )

    result = service_with(repository).reconcile_active()

    assert result["status"] == "attention"
    assert repository.deleted_steps == []
    assert repository.value["verification_round"] == 11


def test_reconcile_waits_for_whole_batch_before_escalating_failure():
    repository = FakeRepository(
        campaign(),
        [collection_step("incomplete"), collection_step("verifying")],
    )
    service = service_with(repository)
    service._plan_phase = lambda _campaign: pytest.fail(
        "a new planning batch must not be created while work is still running"
    )

    result = service.reconcile(9)

    assert result["status"] == "running"
    assert result["failed_steps"] == 1
    assert result["planned_steps"] == 2


def test_final_verification_automatically_activates_daily_mode():
    repository = FakeRepository(
        campaign(current_phase=6, phase_name="verification"),
        [
            {
                "resource_type": "coverage",
                "coverage_status": "success",
                "audit_status": "complete",
            }
        ],
    )

    result = service_with(repository).reconcile(9)

    assert repository.activated is True
    assert result["status"] == "completed"


def test_empty_phase_advances_and_empty_final_phase_can_auto_activate():
    repository = FakeRepository(campaign(), [])
    assert service_with(repository).reconcile(9)["current_phase"] == 1

    repository = FakeRepository(
        campaign(current_phase=6, phase_name="verification"), []
    )
    result = service_with(repository).reconcile(9)
    assert repository.activated is True
    assert result["status"] == "completed"
