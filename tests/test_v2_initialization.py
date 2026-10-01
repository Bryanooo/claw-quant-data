from datetime import date

from service.initialization.service import InitializationService


class InitRepository:
    def __init__(self):
        self.audits = []
        self.executions_ = []

    def audit_jobs(self, _id): return self.audits
    def executions(self, _id, limit=5000): return self.executions_[:limit]
    def find_latest_id(self): return 7 if self.audits else None
    def set_execution_status(self, *_args): return 0


class OrchestrationRepository:
    def control_plane_summary(self):
        return {"status":"installed","definitions":{"acquisition:active":191}}


class Coverage:
    def __init__(self, repository): self.repository=repository
    def submit_audits(self, datasets, **kwargs):
        self.repository.audits=[{"job_id":i+1,"dataset_name":name,"status":"queued","attempt":0,"max_attempts":3,"start_date":kwargs["start_date"],"end_date":kwargs["end_date"]} for i,name in enumerate(datasets)]
        return {"created":len(datasets),"total":len(datasets)}


def test_initialization_creates_strict_audits_not_v1_jobs(monkeypatch):
    repository=InitRepository()
    service=InitializationService(repository,OrchestrationRepository(),Coverage(repository))
    monkeypatch.setattr("service.initialization.service.COVERAGE_RULES.list",lambda:[type("Rule",(),{"dataset_name":"stock_daily","auditable":True,"strict_audit_mode":"expected_partition"})()])
    monkeypatch.setattr(
        "service.initialization.service.current_problem_partitions",
        lambda **_kwargs: {},
    )
    campaign,created=service.start(profile="full",history_start=date(2026,1,1),history_end=date(2026,1,2),idempotency_key="test-v2-init")
    assert created is True
    assert campaign["engine"] == "orchestration_v2"
    assert campaign["status"] == "auditing"
    assert repository.audits[0]["dataset_name"] == "stock_daily"


def test_preflight_explicitly_rejects_v1_dependency(monkeypatch):
    repository=InitRepository()
    service=InitializationService(repository,OrchestrationRepository(),Coverage(repository))
    monkeypatch.setattr("service.initialization.service.COVERAGE_RULES.list",lambda:[])
    result=service.preflight(profile="full",history_start=date(2026,1,1),history_end=date(2026,1,2))
    assert result["engine"] == "orchestration_v2"
    assert result["checks"]["v1_required"] is False


def test_successful_repair_round_requires_a_new_full_verification(monkeypatch):
    repository = InitRepository()
    repository.audits = [{
        "job_id": 1,
        "dataset_name": "stock_daily",
        "status": "success",
        "start_date": date(2026, 1, 1),
        "end_date": date(2026, 1, 2),
        "idempotency_key": "v2-init:7:audit:stock_daily",
    }]
    repository.executions_ = [{
        "task_execution_id": 19,
        "status": "success",
    }]
    monkeypatch.setattr(
        "service.initialization.service.current_problem_partitions",
        lambda **_kwargs: {},
    )
    service = InitializationService(
        repository, OrchestrationRepository(), Coverage(repository)
    )

    campaign = service.get(7)

    assert campaign["status"] == "verification_pending"
    assert campaign["phase_name"] == "strict_post_repair_verification"


def test_initialization_checks_problems_only_inside_its_frozen_history_bounds(
    monkeypatch,
):
    repository = InitRepository()
    repository.audits = [{
        "job_id": 1,
        "dataset_name": "stock_daily",
        "status": "success",
        "start_date": date(2026, 1, 1),
        "end_date": date(2026, 9, 28),
        "idempotency_key": "v2-init:7:audit:stock_daily",
    }]
    seen = {}

    def scoped_problems(**kwargs):
        seen.update(kwargs)
        return {}

    monkeypatch.setattr(
        "service.initialization.service.current_problem_partitions",
        scoped_problems,
    )
    service = InitializationService(
        repository, OrchestrationRepository(), Coverage(repository)
    )

    campaign = service.get(7)

    assert campaign["status"] == "ready"
    assert seen == {
        "start_date": date(2026, 1, 1),
        "end_date": date(2026, 9, 28),
    }


def test_superseded_out_of_scope_execution_does_not_require_verification(
    monkeypatch,
):
    repository = InitRepository()
    repository.audits = [{
        "job_id": 20,
        "dataset_name": "stock_daily",
        "status": "success",
        "start_date": date(2026, 1, 1),
        "end_date": date(2026, 9, 28),
        "idempotency_key": "v2-init:7:verify:19:stock_daily",
    }]
    repository.executions_ = [{
        "task_execution_id": 21,
        "status": "superseded",
    }]
    monkeypatch.setattr(
        "service.initialization.service.current_problem_partitions",
        lambda **_kwargs: {},
    )
    service = InitializationService(
        repository, OrchestrationRepository(), Coverage(repository)
    )

    campaign = service.get(7)
    assert campaign["status"] == "ready"
    assert campaign["completed_steps"] == campaign["planned_steps"] == 2
    assert campaign["current_phase"] == "complete"
    assert campaign["phase_name"] == "initialization_complete"
