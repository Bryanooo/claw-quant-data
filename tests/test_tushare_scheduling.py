from datetime import date
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pytest

import service.tushare_scheduling as scheduling
from service.tushare_catalog import TushareInterfaceCatalog
from service.tushare_policy import TusharePolicyRegistry
from service.collection_jobs.models import HandlerMetadata


@pytest.fixture(autouse=True)
def _enable_routine_mode_for_unit_tests(monkeypatch):
    """Policy unit tests exercise dispatch, not initialization mode gating."""
    import service.initialization.repository as initialization_repository

    monkeypatch.setattr(
        initialization_repository, "routine_collection_enabled", lambda: True
    )


class FakeRepository:
    def __init__(self):
        self.jobs = {}
        self.next_job_id = 1
        self.rechecks = []

    def create(self, task_name, parameters, **options):
        key = options["idempotency_key"]
        created = key not in self.jobs
        job = {
            "job_id": self.next_job_id,
            "task_name": task_name,
            "parameters": parameters,
            **options,
        }
        if created:
            self.jobs[key] = job
            self.next_job_id += 1
        return self.jobs[key], created

    def create_empty_recheck(self, root_job_id, **policy):
        job = next(item for item in self.jobs.values() if item["job_id"] == root_job_id)
        if job.get("completion_status") != "empty" or job.get("rechecked"):
            return None
        job["rechecked"] = True
        recheck = {"job_id": self.next_job_id, "root_job_id": root_job_id, **policy}
        self.next_job_id += 1
        self.rechecks.append(recheck)
        return recheck


def test_every_automatic_policy_can_build_bounded_parameters(monkeypatch):
    monkeypatch.setattr(scheduling, "_latest_trade_date", lambda _today: "20260828")
    catalog = TushareInterfaceCatalog()
    policies = TusharePolicyRegistry()

    candidates = []
    for contract in catalog.list():
        policy = policies.get(contract.api_name)
        if (
            contract.collectable
            and policy.automatic_safe
            and contract.api_name not in scheduling.DEDICATED_SCHEDULED_APIS
        ):
            candidates.append(contract.api_name)
            parameters = scheduling.parameters_for_policy(
                policy,
                {item["name"] for item in contract.input_parameters},
                today=date(2026, 8, 29),
                trade_date="20260828",
            )
            if policy.pagination_mode == "partitioned":
                assert parameters

    assert len(candidates) >= 115
    assert "ccass_hold_detail" not in candidates
    assert "ccass_hold" in candidates
    assert "hk_daily" in candidates
    assert "hk_hold" in candidates
    assert "moneyflow_hsgt" in candidates
    assert "stk_mins" not in candidates
    assert "opt_daily" not in candidates
    assert "fut_weekly_detail" not in candidates
    assert "tdx_member" not in candidates


def test_policy_submission_is_idempotent_for_same_effective_trade_day(monkeypatch):
    monkeypatch.setattr(scheduling, "_latest_trade_date", lambda _today: "20260828")
    repository = FakeRepository()

    first = scheduling.submit_policy_batch(
        "daily", today=date(2026, 8, 29), repository=repository
    )
    second = scheduling.submit_policy_batch(
        "daily", today=date(2026, 8, 31), repository=repository
    )

    assert first >= 90
    assert second == 0
    assert len(repository.jobs) == first
    assert all(len(key) <= 128 for key in repository.jobs)
    assert all(
        job["task_name"] == "tushare_interface"
        and job["parameters"]["complete"] is True
        and job["parameters"]["resume"] is True
        for job in repository.jobs.values()
    )


def test_policy_job_identity_changes_only_when_handler_contract_changes():
    first = HandlerMetadata("generic", "catalog_raw:moneyflow", "1", "old")
    upgraded = HandlerMetadata("specialized", "specialized:MoneyflowCollector", "3", "new")
    parameters = {"trade_date": "20260828"}

    first_key = scheduling._policy_job_key(
        "moneyflow", "daily", date(2026, 8, 28), parameters, first
    )
    same_key = scheduling._policy_job_key(
        "moneyflow", "daily", date(2026, 8, 28), parameters, first
    )
    upgraded_key = scheduling._policy_job_key(
        "moneyflow", "daily", date(2026, 8, 28), parameters, upgraded
    )

    assert first_key == same_key
    assert first_key != upgraded_key
    assert len(upgraded_key) <= 128


def test_policy_submission_creates_one_separate_recheck_for_empty_result(monkeypatch):
    monkeypatch.setattr(scheduling, "_latest_trade_date", lambda _today: "20260828")
    repository = FakeRepository()

    first = scheduling.submit_policy_batch(
        "daily", today=date(2026, 8, 29), repository=repository
    )
    for job in repository.jobs.values():
        job["completion_status"] = "empty"
    second = scheduling.submit_policy_batch(
        "daily", today=date(2026, 8, 31), repository=repository
    )
    third = scheduling.submit_policy_batch(
        "daily", today=date(2026, 8, 31), repository=repository
    )

    assert second == first
    assert len(repository.rechecks) == first
    assert third == 0
    assert all(item["max_generations"] == 3 for item in repository.rechecks)


def test_next_morning_empty_recheck_waits_for_publication_cutoff(monkeypatch):
    timezone = ZoneInfo("Asia/Shanghai")
    monkeypatch.setattr(
        scheduling,
        "business_now",
        lambda: datetime(2026, 9, 1, 9, 14, tzinfo=timezone),
    )

    assert scheduling._publication_is_mature("margin", date(2026, 8, 31)) is False
    assert scheduling._publication_is_mature("ccass_hold", date(2026, 8, 31)) is False
    assert scheduling._publication_is_mature("daily_info", date(2026, 8, 31)) is True

    monkeypatch.setattr(
        scheduling,
        "business_now",
        lambda: datetime(2026, 9, 1, 9, 15, tzinfo=timezone),
    )
    assert scheduling._publication_is_mature("margin", date(2026, 8, 31)) is True


def test_documented_alternative_parameters_use_safe_partitions(monkeypatch):
    monkeypatch.setattr(scheduling, "_latest_trade_date", lambda _today: "20260828")
    catalog = TushareInterfaceCatalog()
    policies = TusharePolicyRegistry()

    dividend = catalog.get("dividend")
    dividend_params = scheduling.parameters_for_policy(
        policies.get("dividend"),
        {item["name"] for item in dividend.input_parameters},
        today=date(2026, 8, 29),
        trade_date="20260828",
    )
    assert dividend_params == {"ann_date": "20260828"}
    assert policies.get("fut_weekly_detail").automatic_safe is False


def test_index_periodic_policies_use_market_wide_offset_pagination():
    policies = TusharePolicyRegistry()

    for api_name, cadence in (
        ("index_daily", "daily"),
        ("index_weekly", "weekly"),
        ("index_monthly", "monthly"),
    ):
        policy = policies.get(api_name)
        assert policy.parameter_strategy == "trade_date"
        assert policy.pagination_mode == "offset"
        assert policy.cadence == cadence
        assert policy.automatic_safe is True


def test_fund_market_partitions_are_automatic_and_exhaust_offset_pages(monkeypatch):
    monkeypatch.setattr(scheduling, "_latest_trade_date", lambda _today: "20260904")
    catalog = TushareInterfaceCatalog()
    policies = TusharePolicyRegistry()

    nav = policies.get("fund_nav")
    assert nav.parameter_strategy == "trade_date"
    assert nav.pagination_mode == "offset"
    assert nav.cadence == "daily"
    assert nav.automatic_safe is True
    assert nav.page_size == 5000
    assert scheduling.parameters_for_policy(
        nav,
        {item["name"] for item in catalog.get("fund_nav").input_parameters},
        today=date(2026, 9, 8),
    ) == {"nav_date": "20260904"}

    portfolio = policies.get("fund_portfolio")
    assert portfolio.parameter_strategy == "report_period"
    assert portfolio.pagination_mode == "offset"
    assert portfolio.cadence == "quarterly"
    assert portfolio.automatic_safe is True
    assert portfolio.page_size == 5000
    assert portfolio.max_pages == 500
    assert scheduling.parameters_for_policy(
        portfolio,
        {
            item["name"]
            for item in catalog.get("fund_portfolio").input_parameters
        },
        today=date(2026, 9, 8),
    ) == {"period": "20260630"}


def test_index_weight_fanout_uses_offset_pagination():
    policy = TusharePolicyRegistry().get("index_weight")

    assert policy.pagination_mode == "offset"


def test_securities_lending_policies_exhaust_offset_pages():
    policies = TusharePolicyRegistry()
    for api_name in ("slb_len", "slb_len_mm", "slb_sec", "slb_sec_detail"):
        policy = policies.get(api_name)
        assert policy.parameter_strategy == "trade_date"
        assert policy.pagination_mode == "offset"
        assert policy.automatic_safe is True


def test_kpl_concept_cons_uses_live_verified_offset_pagination():
    policy = TusharePolicyRegistry().get("kpl_concept_cons")

    assert policy.parameter_strategy == "trade_date"
    assert policy.pagination_mode == "offset"
    assert policy.page_size == 3000
    assert policy.cadence == "daily"
    assert policy.automatic_safe is True


@pytest.mark.parametrize("api_name", ["stk_limit", "index_daily"])
def test_market_wide_daily_interfaces_use_live_verified_large_pages(api_name):
    policy = TusharePolicyRegistry().get(api_name)

    assert policy.parameter_strategy == "trade_date"
    assert policy.pagination_mode == "offset"
    assert policy.page_size == 5000
    assert policy.automatic_safe is True


def test_margin_detail_uses_offset_before_market_coverage_verification():
    policy = TusharePolicyRegistry().get("margin_detail")

    assert policy.parameter_strategy == "trade_date"
    assert policy.pagination_mode == "offset"
    assert policy.page_size == 1000
    assert policy.automatic_safe is True


def test_weekly_and_monthly_scope_use_closed_period_last_trade_day(monkeypatch):
    boundaries = []

    def fake_latest(boundary):
        boundaries.append(boundary)
        return "20260828" if boundary == date(2026, 8, 30) else "20260831"

    monkeypatch.setattr(scheduling, "_latest_trade_date", fake_latest)
    repository = FakeRepository()

    scheduling.submit_policy_batch(
        "weekly", today=date(2026, 8, 27), repository=repository
    )
    weekly_jobs = [
        job for job in repository.jobs.values()
        if job.get("api_name") == "index_weekly"
    ]
    scheduling.submit_policy_batch(
        "monthly", today=date(2026, 9, 3), repository=repository
    )
    monthly_jobs = [
        job for job in repository.jobs.values()
        if job.get("api_name") == "index_monthly"
    ]

    assert boundaries[:2] == [date(2026, 8, 30), date(2026, 8, 31)]
    assert weekly_jobs[0]["parameters"]["parameters"] == {
        "trade_date": "20260828"
    }
    assert weekly_jobs[0]["expected_for"] == date(2026, 8, 28)
    assert weekly_jobs[0]["period_key"] == "2026-W35"
    assert monthly_jobs[0]["parameters"]["parameters"] == {
        "trade_date": "20260831"
    }
    assert monthly_jobs[0]["expected_for"] == date(2026, 8, 31)
    assert monthly_jobs[0]["period_key"] == "2026-08"


def test_local_today_uses_shanghai_business_date(monkeypatch):
    class FakeDateTime:
        @staticmethod
        def now(target_timezone):
            return datetime(
                2026, 8, 28, 17, 30, tzinfo=timezone.utc
            ).astimezone(target_timezone)

    monkeypatch.setattr(scheduling, "datetime", FakeDateTime)

    assert scheduling.local_today() == date(2026, 8, 29)


def test_post_close_policy_patrol_submits_current_trade_date(monkeypatch):
    observed = []

    def fake_submit(cadence, *, today, repository=None):
        observed.append((cadence, today))
        return 0

    monkeypatch.setattr(scheduling, "submit_policy_batch", fake_submit)

    scheduling.submit_latest_policy_batches(
        today=date(2026, 8, 31),
        include_current_daily=True,
    )

    assert observed[0] == ("daily", date(2026, 8, 31))
    assert observed[1] == ("weekly", date(2026, 8, 24))


def test_pre_close_policy_patrol_keeps_previous_day_guard(monkeypatch):
    observed = []

    def fake_submit(cadence, *, today, repository=None):
        observed.append((cadence, today))
        return 0

    monkeypatch.setattr(scheduling, "submit_policy_batch", fake_submit)

    scheduling.submit_latest_policy_batches(today=date(2026, 8, 31))

    assert observed[0] == ("daily", date(2026, 8, 30))
