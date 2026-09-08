from datetime import date, datetime, timezone
import time

import pytest
from fastapi.testclient import TestClient

from service.api.app import create_app
from service.api.dependencies import (
    get_collection_job_service,
)
from service.collection_jobs.models import (
    JobConflictError,
    JobHandlerMismatchError,
    TaskExecutionResult,
)
from service.collection_jobs.models import InvalidTaskParametersError
from service.collection_jobs.fanout import FanoutPlanner
from service.collection_jobs.registry import TASKS
from service.collection_jobs.service import CollectionJobService
from service.collection_jobs.worker import (
    CollectionJobTimeoutError,
    JobWorker,
    classify_failure,
    execution_deadline,
    parse_resource_classes,
)
from service.collection_jobs.verification import CollectionVerificationPlanner
from collectors.contracts import CollectorResult
from collectors.tushare_raw import IncompleteCollectionError


def make_job(**overrides):
    now = datetime.now(timezone.utc)
    job = {
        "job_id": 1,
        "task_name": "stock_daily",
        "parameters": {"trade_date": "20260725", "ts_code": "000001.SZ"},
        "status": "queued",
        "attempt": 0,
        "max_attempts": 2,
        "rows_inserted": 0,
        "idempotency_key": "daily-000001-20260725",
        "parent_job_id": None,
        "worker_id": None,
        "error_message": None,
        "available_at": now,
        "created_at": now,
        "started_at": None,
        "finished_at": None,
    }
    return {**job, **overrides}


class FakeRepository:
    def __init__(self, job=None, created=True):
        self.job = job or make_job()
        self.created = created

    def create(self, task_name, parameters, **kwargs):
        self.create_options = kwargs
        if self.created:
            self.job = {
                **self.job,
                "task_name": task_name,
                "parameters": parameters,
                "max_attempts": kwargs["max_attempts"],
                "idempotency_key": kwargs["idempotency_key"],
                "parent_job_id": kwargs.get("parent_job_id"),
            }
        return self.job, self.created

    def get(self, job_id):
        return self.job if self.job["job_id"] == job_id else None

    def list(self, **_kwargs):
        return [self.job]


class DummyDatabase:
    def close(self):
        pass


def test_task_registry_normalizes_dates_and_rejects_extra_parameters():
    validated = TASKS.validate(
        "stock_daily",
        {"trade_date": "2026-07-25", "ts_code": "000001.sz"},
    )
    assert validated.trade_date == "20260725"
    assert validated.ts_code == "000001.SZ"

    with pytest.raises(Exception, match="extra"):
        TASKS.validate("stock_daily", {"trade_date": "20260725", "unsafe": True})

    assert TASKS.validate("income_period", {"period": "2026-06-30"}).period == "20260630"
    with pytest.raises(Exception, match="quarter end"):
        TASKS.validate("income_period", {"period": "20260531"})


def test_trade_calendar_is_bounded_by_calendar_year(monkeypatch):
    import collectors.stock.basic.trade_cal as trade_cal_module

    calls = []

    class FakeTradeCalendar:
        def collect(self, **parameters):
            calls.append(parameters)
            return 2

    monkeypatch.setattr(trade_cal_module, "TradeCalCollector", FakeTradeCalendar)
    result = TASKS.run(
        "trade_calendar",
        {
            "start_date": "2025-12-30",
            "end_date": "2026-01-02",
            "exchanges": ["SSE"],
        },
    )

    assert calls == [
        {"exchange": "SSE", "start_date": "20251230", "end_date": "20251231"},
        {"exchange": "SSE", "start_date": "20260101", "end_date": "20260102"},
    ]
    assert result.rows_fetched == 4
    assert result.completion_status == "complete"
    assert result.completion_evidence["verified"] is True
    assert TASKS.get("trade_calendar").handler_version == "2"


def test_generic_tushare_task_accepts_only_authorized_read_interfaces():
    validated = TASKS.validate(
        "tushare_interface",
        {
            "api_name": "cn_cpi",
            "parameters": {"start_m": "202601", "end_m": "202606"},
        },
    )
    assert validated.api_name == "cn_cpi"
    assert "month" in validated.fields.split(",")

    with pytest.raises(Exception, match="not collectable"):
        TASKS.validate(
            "tushare_interface",
            {"api_name": "anns_d", "parameters": {}},
        )
    with pytest.raises(Exception, match="write interface"):
        TASKS.validate(
            "tushare_interface",
            {"api_name": "p_delete", "parameters": {}},
        )

    with pytest.raises(Exception, match="not present"):
        TASKS.validate(
            "tushare_interface",
            {"api_name": "cn_cpi", "parameters": {}, "fields": "month,unsafe"},
        )


def test_job_service_detects_idempotency_key_payload_conflict():
    repository = FakeRepository(
        job=make_job(parameters={"trade_date": "20260724"}),
        created=False,
    )
    service = CollectionJobService(repository, TASKS)

    with pytest.raises(JobConflictError, match="idempotency"):
        service.submit(
            "stock_daily",
            {"trade_date": "20260725", "ts_code": "000001.SZ"},
            max_attempts=2,
            idempotency_key="same-request-key",
        )


def test_job_service_persists_canonical_api_for_dedicated_task():
    repository = FakeRepository()
    service = CollectionJobService(repository, TASKS)

    service.submit(
        "stock_daily",
        {"trade_date": "20260725"},
        max_attempts=3,
        idempotency_key="daily-20260725",
    )

    assert repository.create_options["api_name"] == "daily"


def test_collection_job_api_submits_without_access_key():
    repository = FakeRepository()
    service = CollectionJobService(repository, TASKS)
    app = create_app(database_factory=DummyDatabase)
    app.dependency_overrides[get_collection_job_service] = lambda: service

    with TestClient(app) as client:
        accepted = client.post(
            "/api/v1/collection-jobs",
            headers={
                "Idempotency-Key": "daily-20260725",
            },
            json={
                "task_name": "stock_daily",
                "parameters": {"trade_date": "20260725"},
                "max_attempts": 2,
            },
        )

    assert accepted.status_code == 202
    assert accepted.json()["status"] == "queued"


class WorkerRepository:
    def __init__(self):
        self.job = make_job(status="running", attempt=1)
        self.finished = None
        self.finish_options = None

    def claim_next(self, worker_id, **_options):
        self.claim_options = _options
        job, self.job = self.job, None
        return job

    def finish(self, job_id, *, rows_inserted, **options):
        self.finished = (job_id, rows_inserted)
        self.finish_options = options

    def fail_or_requeue(self, job, error_message, **_kwargs):
        raise AssertionError(error_message)


def test_worker_executes_claimed_job(monkeypatch):
    repository = WorkerRepository()
    monkeypatch.setattr(TASKS, "run", lambda name, parameters: 3)
    worker = JobWorker(
        repository,
        worker_id="test-worker",
        poll_interval=0,
        resource_classes=("market", "scheduled"),
    )

    assert worker.run_once() is True
    assert repository.finished == (1, 3)
    assert repository.claim_options["resource_classes"] == ("market", "scheduled")
    assert worker.run_once() is False


def test_worker_resource_pool_configuration_is_explicit_and_deduplicated():
    assert parse_resource_classes(None) is None
    assert parse_resource_classes(" * ") is None
    assert parse_resource_classes("fanout, fanout, initialization") == (
        "fanout",
        "initialization",
    )
    with pytest.raises(ValueError, match="non-empty"):
        parse_resource_classes(" , ")


def test_worker_submits_targeted_verification_for_full_market_job(monkeypatch):
    repository = WorkerRepository()
    repository.job["parameters"] = {"trade_date": "20260725"}
    monkeypatch.setattr(TASKS, "run", lambda _name, _parameters: 5000)

    worker = JobWorker(repository, worker_id="test-worker", poll_interval=0)
    assert worker.run_once() is True

    assert repository.finish_options["verification"] == {
        "dataset_name": "stock_daily",
        "start_date": date(2026, 7, 25),
        "end_date": date(2026, 7, 25),
        "idempotency_key": "verify-collection-job-1",
    }


def test_worker_treats_dedicated_zero_rows_as_unverified_without_premature_audit(
    monkeypatch,
):
    repository = WorkerRepository()
    repository.job["parameters"] = {"trade_date": "20260831"}
    monkeypatch.setattr(TASKS, "run", lambda _name, _parameters: 0)

    worker = JobWorker(repository, worker_id="test-worker", poll_interval=0)
    assert worker.run_once() is True

    assert repository.finish_options["completion_status"] == "unverified"
    assert repository.finish_options["rows_fetched"] == 0
    assert repository.finish_options["verification"] is None
    assert repository.finish_options["completion_evidence"]["zero_result_reason"] == (
        "dedicated_collector_zero_is_ambiguous"
    )


def test_verification_planner_skips_single_security_and_maps_finance_schedule():
    planner = CollectionVerificationPlanner()
    assert planner.plan(make_job()) is None

    verification = planner.plan(
        make_job(
            task_name="scheduled_collector",
            parameters={
                "schedule_id": "income_quarterly",
                "scheduled_for": "2026-11-01T06:30:00+08:00",
            },
        )
    )

    assert verification.dataset_name == "income"
    assert verification.start_date.isoformat() == "2026-09-30"


def test_verification_planner_maps_complete_interface_partition():
    verification = CollectionVerificationPlanner().plan(
        make_job(
            task_name="tushare_interface",
            parameters={
                "api_name": "margin_detail",
                "parameters": {"trade_date": "20260904"},
            },
        )
    )

    assert verification.dataset_name == "margin_detail"
    assert verification.start_date == date(2026, 9, 4)
    assert verification.end_date == date(2026, 9, 4)


def test_initialization_uses_transport_proof_for_closed_stock_history():
    planner = CollectionVerificationPlanner()

    assert planner.plan(
        make_job(
            task_name="stock_daily",
            parameters={"trade_date": "20250102", "ts_code": None},
            cadence="initialization",
        )
    ) is None
    modern = planner.plan(
        make_job(
            task_name="stock_daily",
            parameters={"trade_date": "20260725", "ts_code": None},
            cadence="initialization",
        )
    )
    assert modern.dataset_name == "stock_daily"


def test_worker_verifies_structured_complete_interface_result(monkeypatch):
    repository = WorkerRepository()
    repository.job.update(
        task_name="tushare_interface",
        parameters={
            "api_name": "margin_detail",
            "parameters": {"trade_date": "20260904"},
        },
    )
    monkeypatch.setattr(
        TASKS,
        "run",
        lambda *_args: TaskExecutionResult(
            rows_inserted=2000,
            rows_fetched=2000,
            completion_status="complete",
            completion_evidence={"verified": True, "exhausted": True},
        ),
    )

    worker = JobWorker(repository, worker_id="test-worker", poll_interval=0)
    assert worker.run_once() is True

    assert repository.finish_options["verification"]["dataset_name"] == "margin_detail"
    assert repository.finish_options["verification"]["start_date"] == date(2026, 9, 4)


def test_worker_does_not_retry_permanent_collection_errors(monkeypatch):
    repository = WorkerRepository()
    failure = {}

    class PermanentError(RuntimeError):
        retryable = False
        retry_after_seconds = 1800

    def fail_or_requeue(job, error_message, **options):
        failure.update(job=job, error_message=error_message, **options)
        return "failed"

    repository.fail_or_requeue = fail_or_requeue
    monkeypatch.setattr(
        TASKS,
        "run",
        lambda *_args: (_ for _ in ()).throw(PermanentError("bad parameter")),
    )

    worker = JobWorker(repository, worker_id="test-worker", poll_interval=0)
    assert worker.run_once() is True
    assert failure["retryable"] is False
    assert failure["retry_after_seconds"] == 1800
    assert "PermanentError: bad parameter" in failure["error_message"]
    assert failure["completion_evidence"]["failure"]["category"] == "invalid_request"
    assert failure["completion_evidence"]["failure"]["retryable"] is False


def test_worker_releases_rate_slot_wait_without_recording_a_failure(monkeypatch):
    repository = WorkerRepository()
    deferred = {}

    class FutureRateSlot(RuntimeError):
        defer_without_failure = True
        retry_after_seconds = 1200

    def defer_running(job, **options):
        deferred.update(job=job, **options)
        return "queued"

    repository.defer_running = defer_running
    monkeypatch.setattr(
        TASKS,
        "run",
        lambda *_args: (_ for _ in ()).throw(FutureRateSlot("wait")),
    )

    assert JobWorker(repository, worker_id="test-worker").run_once() is True
    assert deferred["retry_after_seconds"] == 1200
    assert "FutureRateSlot: wait" in deferred["reason"]


@pytest.mark.parametrize(("attempt", "expected_delay"), [(1, 60), (2, 300), (3, 900)])
def test_worker_applies_shared_exponential_backoff_to_network_failures(
    monkeypatch, attempt, expected_delay
):
    import service.collection_jobs.worker as worker_module

    repository = WorkerRepository()
    repository.job.update(attempt=attempt, max_attempts=3, resource_class="initialization")
    failure = {}

    def fail_or_requeue(job, error_message, **options):
        failure.update(job=job, error_message=error_message, **options)
        return "queued" if attempt < 3 else "failed"

    repository.fail_or_requeue = fail_or_requeue
    monkeypatch.setattr(worker_module, "JOB_NETWORK_RETRY_BASE_SECONDS", 60)
    monkeypatch.setattr(worker_module, "JOB_NETWORK_RETRY_MAX_SECONDS", 900)
    monkeypatch.setattr(
        TASKS,
        "run",
        lambda *_args: (_ for _ in ()).throw(
            ConnectionError("temporary failure in name resolution")
        ),
    )

    assert JobWorker(repository, worker_id="test-worker").run_once() is True
    assert failure["retry_after_seconds"] == expected_delay
    assert failure["defer_resource_class_seconds"] == expected_delay
    evidence = failure["completion_evidence"]["failure"]
    assert evidence["category"] == "network"
    assert evidence["resource_backoff_seconds"] == expected_delay


def test_failure_categories_distinguish_operational_causes():
    assert classify_failure(CollectionJobTimeoutError("slow")) == "timeout"
    assert classify_failure(IncompleteCollectionError("response cap (2000)")) == "completeness"
    assert classify_failure(RuntimeError("访问权限不足")) == "permission"
    assert classify_failure(ConnectionError("connection reset")) == "network"
    assert classify_failure(OSError("[Errno -2] Name or service not known")) == "network"


def test_worker_execution_deadline_interrupts_stuck_call():
    with pytest.raises(CollectionJobTimeoutError):
        with execution_deadline(0.01):
            time.sleep(0.1)


def test_task_registry_snapshots_deterministic_handlers():
    generic = TASKS.handler_metadata(
        "tushare_interface",
        {"api_name": "cn_cpi", "parameters": {}},
    )
    dedicated = TASKS.handler_metadata(
        "stock_daily", {"trade_date": "20260725"}
    )
    routed_specialized = TASKS.handler_metadata(
        "tushare_interface",
        {"api_name": "block_trade", "parameters": {"trade_date": "20260725"}},
    )

    assert generic.handler_type == "generic"
    assert generic.handler_key == "catalog_typed:cn_cpi"
    assert generic.handler_version == "3"
    assert dedicated.handler_type == "dedicated"
    assert dedicated.handler_key.endswith(":_run_stock_daily")
    assert dedicated.handler_version == "2"
    assert routed_specialized.handler_type == "specialized"
    assert routed_specialized.handler_key.endswith("BlockTradeCollector")


def test_stock_daily_uses_offset_exhaustion_for_round_historical_count(monkeypatch):
    import collectors.stock.market.daily as daily_module

    observed = {}

    class FakeDailyCollector:
        def run_offset_paginated(self, **parameters):
            observed.update(parameters)
            return CollectorResult(
                collector_name="tests.FakeDailyCollector",
                collector_version="2",
                api_name="daily",
                table_name="daily",
                fetched_rows=1000,
                stored_rows=1000,
                request_count=2,
                evidence={
                    "verified": True,
                    "verification_type": "offset_exhaustion",
                    "exhausted": True,
                    "page_size": parameters["page_size"],
                },
            )

    monkeypatch.setattr(daily_module, "DailyCollector", FakeDailyCollector)

    result = TASKS.run("stock_daily", {"trade_date": "20000811"})

    assert observed == {
        "page_size": 5000,
        "max_pages": 100,
        "trade_date": "20000811",
    }
    assert result.rows_fetched == 1000
    assert result.rows_inserted == 1000
    assert result.completion_status == "complete"
    assert result.completion_evidence["verification_type"] == "offset_exhaustion"
    assert result.completion_evidence["exhausted"] is True


def test_stock_limit_uses_offset_exhaustion_for_round_historical_count(monkeypatch):
    import collectors.stock.market.stk_limit as stock_limit_module

    observed = {}

    class FakeSTKLimitCollector:
        def run_offset_paginated(self, **parameters):
            observed.update(parameters)
            return CollectorResult(
                collector_name="tests.FakeSTKLimitCollector",
                collector_version="2",
                api_name="stk_limit",
                table_name="stk_limit",
                fetched_rows=2000,
                stored_rows=2000,
                request_count=2,
                evidence={
                    "verified": True,
                    "verification_type": "offset_exhaustion",
                    "exhausted": True,
                    "page_size": parameters["page_size"],
                },
            )

    monkeypatch.setattr(
        stock_limit_module, "STKLimitCollector", FakeSTKLimitCollector
    )

    result = TASKS.run("stock_limit", {"trade_date": "20101222"})

    assert observed == {
        "page_size": 5000,
        "max_pages": 100,
        "trade_date": "20101222",
    }
    assert result.rows_fetched == 2000
    assert result.rows_inserted == 2000
    assert result.completion_status == "complete"
    assert result.completion_evidence["verification_type"] == "offset_exhaustion"
    assert result.completion_evidence["exhausted"] is True


def test_daily_basic_repair_routes_to_daily_basic_not_bak_basic(monkeypatch):
    import service.collection_jobs.registry as registry_module

    observed = {}

    def fake_run(parameters):
        observed.update(parameters.model_dump())
        return TaskExecutionResult(rows_inserted=7, completion_status="complete")

    monkeypatch.setattr(registry_module, "_run_tushare_interface", fake_run)
    result = TASKS.run("stock_daily_basic", {"trade_date": "20260828"})

    assert result.rows_inserted == 7
    assert observed["api_name"] == "daily_basic"
    assert observed["parameters"] == {"trade_date": "20260828"}


def test_specialized_policy_collector_returns_bounded_completion_evidence(monkeypatch):
    import service.collector_catalog as collector_catalog

    class FakeSpecializedCollector:
        def run(self, **_parameters):
            return CollectorResult(
                collector_name="tests.FakeSpecializedCollector",
                collector_version="1",
                api_name="block_trade",
                table_name="block_trade",
                fetched_rows=7,
                stored_rows=7,
            )

    monkeypatch.setattr(
        collector_catalog,
        "resolve_collector_classes",
        lambda _api_name: (FakeSpecializedCollector,),
    )
    result = TASKS.run(
        "tushare_interface",
        {"api_name": "block_trade", "parameters": {"trade_date": "20260828"}},
    )

    assert result.completion_status == "complete"
    assert result.completion_evidence["verified"] is True
    assert result.completion_evidence["verification_type"] == "bounded_policy_scope"
    assert result.completion_evidence["bounded_partition"] is True


def test_specialized_policy_collector_fails_closed_at_suspicious_cap(monkeypatch):
    import service.collector_catalog as collector_catalog

    class CappedSpecializedCollector:
        def run(self, **_parameters):
            return CollectorResult(
                collector_name="tests.CappedSpecializedCollector",
                collector_version="1",
                api_name="block_trade",
                table_name="block_trade",
                fetched_rows=1000,
                stored_rows=1000,
            )

    monkeypatch.setattr(
        collector_catalog,
        "resolve_collector_classes",
        lambda _api_name: (CappedSpecializedCollector,),
    )
    with pytest.raises(IncompleteCollectionError, match="suspicious round cap"):
        TASKS.run(
            "tushare_interface",
            {"api_name": "block_trade", "parameters": {"trade_date": "20260828"}},
        )


def test_task_registry_rejects_changed_persisted_handler():
    job = make_job(
        handler_type="dedicated",
        handler_key="schedule:not_the_requested_handler",
        handler_version="1",
    )
    with pytest.raises(JobHandlerMismatchError, match="does not match"):
        TASKS.assert_handler_compatible(job)


def test_manual_api_defaults_to_three_attempts():
    request = __import__(
        "service.api.schemas", fromlist=["CollectionJobRequest"]
    ).CollectionJobRequest(task_name="stock_daily", parameters={"trade_date": "20260725"})
    assert request.max_attempts == 3


class FanoutRepository:
    def __init__(self, values):
        self.values = values
        self.created = None

    def list_fanout_values(self, source, *, as_of=None):
        assert source in {
            "stock", "convertible_bond", "fund", "index", "pro_data",
            "ci_index", "sw_l3_index", "bc_bond", "etf_sh", "etf_sz",
            "tdx_index", "factor_name",
        }
        self.as_of = as_of
        return self.values

    def create_batch(self, parameters, children, **options):
        self.created = (parameters, children, options)
        return {
            "job_id": 900,
            "task_name": "collection_batch",
            "parameters": parameters,
            "job_kind": "batch",
        }, True


def test_fanout_planner_batches_entities_and_records_resume_cursor():
    repository = FanoutRepository([f"11{i:04d}.SH" for i in range(45)])
    planner = FanoutPlanner(repository, TASKS)

    parent, created = planner.create_batch(
        {"api_name": "cb_rate", "offset": 0, "max_children": 2},
        idempotency_key=None,
    )

    parameters, children, options = repository.created
    assert created is True
    assert parent["job_kind"] == "batch"
    assert len(children) == 2
    assert len(children[0].parameters["parameters"]["ts_code"].split(",")) == 20
    assert parameters["plan"]["entities_selected"] == 40
    assert parameters["plan"]["next_offset"] == 40
    assert parameters["plan"]["has_more"] is True
    assert options["idempotency_key"].startswith("fanout:cb_rate:")
    assert all(child.handler.handler_key == "catalog_typed:cb_rate" for child in children)


def test_fanout_planner_filters_dependency_universe_at_campaign_boundary():
    repository = FanoutRepository(["000001.SZ"])
    planner = FanoutPlanner(repository, TASKS)

    planner.create_batch(
        {"api_name": "pledge_stat", "offset": 0, "max_children": 1},
        idempotency_key="point-in-time-stock-universe",
        expected_for_override=date(2026, 9, 5),
    )

    parameters, _children, _options = repository.created
    assert repository.as_of == date(2026, 9, 5)
    assert parameters["plan"]["universe_as_of"] == "2026-09-05"


def test_fanout_planner_requires_bounded_scope_and_rejects_wide_window():
    planner = FanoutPlanner(FanoutRepository(["000001.SZ"]), TASKS)

    with pytest.raises(InvalidTaskParametersError, match="requires start_date"):
        planner.create_batch(
            {"api_name": "cyq_chips", "offset": 0, "max_children": 1},
            idempotency_key=None,
        )
    with pytest.raises(InvalidTaskParametersError, match="cannot exceed 31 days"):
        planner.create_batch(
            {
                "api_name": "cyq_chips",
                "start_date": date(2026, 1, 1),
                "end_date": date(2026, 3, 1),
                "offset": 0,
                "max_children": 1,
            },
            idempotency_key=None,
        )


def test_index_periodic_fanout_uses_bounded_symbol_windows():
    repository = FanoutRepository(["000001.SH", "000300.SH"])
    planner = FanoutPlanner(repository, TASKS)

    planner.create_batch(
        {
            "api_name": "index_weekly",
            "start_date": date(2026, 1, 1),
            "end_date": date(2026, 8, 30),
            "offset": 0,
            "max_children": 2,
        },
        idempotency_key="index-weekly-bounded",
    )

    parameters, children, _options = repository.created
    assert parameters["plan"]["universe_source"] == "index"
    assert [child.parameters["parameters"]["ts_code"] for child in children] == [
        "000001.SH",
        "000300.SH",
    ]
    assert all(
        child.parameters["parameters"]["start_date"] == "20260101"
        and child.parameters["parameters"]["end_date"] == "20260830"
        for child in children
    )


@pytest.mark.parametrize(
    ("api_name", "expected_source", "parameter_name"),
    [
        ("ci_index_member", "ci_index", "l3_code"),
        ("index_member_all", "sw_l3_index", "l3_code"),
        ("pledge_stat", "stock", "ts_code"),
    ],
)
def test_capped_snapshot_interfaces_use_authoritative_fanout(
    api_name, expected_source, parameter_name
):
    repository = FanoutRepository(["SOURCE001", "SOURCE002"])
    FanoutPlanner(repository, TASKS).create_batch(
        {"api_name": api_name, "offset": 0, "max_children": 2},
        idempotency_key=f"{api_name}-safe-fanout",
    )

    parameters, children, _options = repository.created
    assert parameters["plan"]["universe_source"] == expected_source
    assert [child.parameters["parameters"][parameter_name] for child in children] == [
        "SOURCE001",
        "SOURCE002",
    ]


def test_static_fanout_needs_no_dependency_table_and_is_bounded():
    repository = FanoutRepository([])
    planner = FanoutPlanner(repository, TASKS)
    planner.create_batch(
        {"api_name": "fut_basic", "offset": 1, "max_children": 2},
        idempotency_key="fut-basic-safe-batch",
    )

    parameters, children, _options = repository.created
    assert [child.parameters["parameters"]["exchange"] for child in children] == [
        "DCE", "CZCE"
    ]
    assert parameters["plan"]["next_offset"] == 3


def test_futures_index_static_fanout_uses_one_code_per_request():
    repository = FanoutRepository([])
    FanoutPlanner(repository, TASKS).create_batch(
        {
            "api_name": "fut_index_daily",
            "trade_date": date(2026, 9, 7),
            "offset": 0,
            "max_children": 56,
        },
        idempotency_key="futures-index-complete-static-universe",
    )

    parameters, children, _options = repository.created
    assert parameters["plan"]["batch_size"] == 1
    assert parameters["plan"]["entities_selected"] == 56
    assert len(children) == 56
    assert all("," not in child.parameters["parameters"]["ts_code"] for child in children)
    assert all(
        child.parameters["parameters"]["trade_date"] == "20260907"
        for child in children
    )


def test_stk_rewards_batches_the_official_multi_code_parameter():
    values = [f"{index:06d}.SZ" for index in range(40)]
    repository = FanoutRepository(values)
    FanoutPlanner(repository, TASKS).create_batch(
        {
            "api_name": "stk_rewards",
            "period": date(2026, 6, 30),
            "offset": 0,
            "max_children": 2,
        },
        idempotency_key="stk-rewards-multi-code",
    )

    parameters, children, _options = repository.created
    assert parameters["plan"]["batch_size"] == 20
    assert len(children) == 2
    assert all(
        len(child.parameters["parameters"]["ts_code"].split(",")) == 20
        for child in children
    )


def test_dc_index_uses_verified_upstream_enum_not_numeric_placeholders():
    repository = FanoutRepository([])
    FanoutPlanner(repository, TASKS).create_batch(
        {
            "api_name": "dc_index",
            "trade_date": date(2025, 1, 3),
            "offset": 0,
            "max_children": 1,
        },
        idempotency_key="dc-index-verified-enum",
    )

    _parameters, children, _options = repository.created
    assert children[0].parameters["parameters"] == {
        "trade_date": "20250103",
        "idx_type": "概念板块",
    }


@pytest.mark.parametrize(
    ("api_name", "source", "parameter_name"),
    [
        ("bc_otcqt", "bc_bond", "ts_code"),
        ("dc_concept_cons", "stock", "ts_code"),
        ("etf_sh_cons", "etf_sh", "ts_code"),
        ("etf_sz_cons", "etf_sz", "ts_code"),
        ("factor_value", "factor_name", "factor_name"),
        ("moneyflow_dc", "stock", "ts_code"),
        ("tdx_member", "tdx_index", "ts_code"),
    ],
)
def test_daily_capped_interfaces_have_bounded_fanout(
    api_name, source, parameter_name
):
    repository = FanoutRepository(["ENTITY001", "ENTITY002"])
    FanoutPlanner(repository, TASKS).create_batch(
        {
            "api_name": api_name,
            "trade_date": date(2026, 8, 31),
            "offset": 0,
            "max_children": 2,
        },
        idempotency_key=f"{api_name}-daily-bounded",
    )

    parameters, children, _options = repository.created
    assert parameters["plan"]["universe_source"] == source
    assert children[0].parameters["parameters"][parameter_name] == "ENTITY001"
    assert children[0].parameters["parameters"]["trade_date"] == "20260831"


@pytest.mark.parametrize("api_name", ["opt_daily", "fut_holding"])
def test_exchange_partitioned_daily_fanout_is_bounded(api_name):
    repository = FanoutRepository([])
    FanoutPlanner(repository, TASKS).create_batch(
        {
            "api_name": api_name,
            "trade_date": date(2026, 8, 31),
            "offset": 0,
            "max_children": 10,
        },
        idempotency_key=f"{api_name}-exchange-bounded",
    )

    _parameters, children, _options = repository.created
    assert len(children) == 6
    assert all(child.parameters["parameters"]["trade_date"] == "20260831" for child in children)
