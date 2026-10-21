from datetime import datetime
from zoneinfo import ZoneInfo

import collectors.scheduler as scheduler_module
from collectors.scheduler import create_scheduler
from service.orchestration_v2.scheduling import dispatch_ready_transformations


def test_scheduler_contains_only_v2_control_jobs():
    scheduler = create_scheduler(set_active=False)
    ids = {job.id for job in scheduler.get_jobs()}
    assert ids == {
        "service_heartbeat",
        "v2_policy_dispatch",
        "v2_transformation_dispatch",
        "v2_coverage_dispatch",
        "v2_coverage_rule_reconciler",
        "v2_transient_failure_reconciler",
        "v2_late_repair_dispatch",
        "v2_initialization_reconciler",
    }


def test_ready_transformation_dispatch_freezes_exact_input_states():
    class Repository:
        def active_task_keys(self):
            return {"technical_factor_snapshot"}

        def latest_common_ready_input_states(self, names):
            assert names == ("stock_daily", "adj_factor", "stock_basic")
            return {
                "stock_daily": {
                    "dataset_state_id": 101,
                    "revision": 2,
                    "observation_key": "2026-10-09",
                    "observation_start": datetime(2026, 10, 9).date(),
                    "observation_end": datetime(2026, 10, 9).date(),
                },
                "adj_factor": {
                    "dataset_state_id": 102,
                    "revision": 3,
                    "observation_key": "2026-10-09",
                    "observation_start": datetime(2026, 10, 9).date(),
                    "observation_end": datetime(2026, 10, 9).date(),
                },
                "stock_basic": {
                    "dataset_state_id": 103,
                    "revision": 1,
                    "observation_key": "2026-10-09",
                    "observation_start": datetime(2026, 10, 9).date(),
                    "observation_end": datetime(2026, 10, 9).date(),
                },
            }

        def create_execution(self, request):
            self.request = request
            return ({"task_execution_id": 5}, True)

    repository = Repository()
    result = dispatch_ready_transformations(repository=repository)

    assert result == {
        "eligible": 1,
        "created": 1,
        "existing": 0,
        "waiting": {},
        "errors": {},
    }
    assert repository.request.task_key == "technical_factor_snapshot"
    assert repository.request.observation_key == "2026-10-09"
    assert repository.request.trigger_source.value == "dependency"
    assert "technical-factor-snapshot-v4" in repository.request.idempotency_key
    assert repository.request.frozen_scope["input_dataset_states"] == {
        "stock_daily": {"dataset_state_id": 101, "revision": 2},
        "adj_factor": {"dataset_state_id": 102, "revision": 3},
        "stock_basic": {"dataset_state_id": 103, "revision": 1},
    }


def test_transient_failure_reconciler_uses_bounded_policy(monkeypatch):
    captured = {}

    class Repository:
        def recover_transient_attention_executions(self, **kwargs):
            captured.update(kwargs)
            return [{"task_execution_id": 7}]

    monkeypatch.setattr(
        scheduler_module, "OrchestrationV2Repository", Repository
    )

    assert scheduler_module.run_transient_failure_reconciler() == 1
    assert captured == {
        "cooldown_seconds": scheduler_module.V2_TRANSIENT_RECOVERY_COOLDOWN_SECONDS,
        "max_recovery_rounds": scheduler_module.V2_TRANSIENT_RECOVERY_MAX_ROUNDS,
        "limit": scheduler_module.V2_TRANSIENT_RECOVERY_BATCH_LIMIT,
    }


def test_coverage_reconciler_sums_dataset_counts(monkeypatch):
    class RuleReconciler:
        def reconcile(self):
            return {"first": 2, "second": 3}

    class Repository:
        def reconcile_resolved_attention_executions(self):
            return 4

        def reconcile_duplicate_attention_executions(self):
            return 1

        def reconcile_redundant_pending_executions(self):
            return 2

        def reconcile_stale_audit_contract_executions(self):
            return 3

        def promote_quota_guarded_history_executions(self):
            return 4

    monkeypatch.setattr(
        scheduler_module, "CoverageRuleReconciler", RuleReconciler
    )
    monkeypatch.setattr(
        scheduler_module, "OrchestrationV2Repository", Repository
    )

    assert scheduler_module.run_coverage_rule_reconciler() == 19


def test_scheduler_never_registers_v1_fanout_or_leaf_jobs():
    scheduler = create_scheduler(set_active=False)
    ids = {job.id for job in scheduler.get_jobs()}
    assert not any("fanout" in item for item in ids)
    assert not any("collection_schedule" in item for item in ids)


def test_late_repair_dispatch_creates_fresh_bounded_v2_instances(monkeypatch):
    now = datetime(2026, 9, 30, 23, 58, tzinfo=ZoneInfo("Asia/Shanghai"))
    repository = object()
    proposal = object()
    captured = {}

    monkeypatch.setattr(scheduler_module, "business_now", lambda: now)
    monkeypatch.setattr(scheduler_module, "is_trade_day", lambda _value: True)
    monkeypatch.setattr(
        scheduler_module, "OrchestrationV2Repository", lambda: repository
    )

    def plan(store, **kwargs):
        assert store is repository
        captured["plan"] = kwargs
        return (proposal,)

    def create(store, **kwargs):
        assert store is repository
        captured["create"] = kwargs
        return {"created": 1, "existing": 0}

    monkeypatch.setattr(scheduler_module, "plan_current_repairs", plan)
    monkeypatch.setattr(scheduler_module, "create_repair_executions", create)

    assert scheduler_module.run_v2_late_repair_dispatch() == 1
    assert captured["plan"] == {
        "start_date": now.date().replace(day=23),
        "end_date": now.date(),
        "included_datasets": scheduler_module.LATE_PUBLISHED_DATASETS,
    }
    assert captured["create"]["proposals"] == (proposal,)
    assert captured["create"]["limit"] == 500
    assert captured["create"]["trigger_source"] == "schedule"
    assert captured["create"]["idempotency_prefix"].endswith(
        "2026-09-30"
    )


def test_late_repair_skips_non_trading_days(monkeypatch):
    now = datetime(2026, 10, 3, 15, 58, tzinfo=ZoneInfo("Asia/Shanghai"))
    monkeypatch.setattr(scheduler_module, "business_now", lambda: now)
    monkeypatch.setattr(scheduler_module, "is_trade_day", lambda _value: False)
    monkeypatch.setattr(
        scheduler_module,
        "plan_current_repairs",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("must not plan provider repairs on a closed day")
        ),
    )

    assert scheduler_module.run_v2_late_repair_dispatch() == 0


def test_late_repairs_run_at_multiple_post_close_windows():
    scheduler = create_scheduler(set_active=False)
    job = scheduler.get_job("v2_late_repair_dispatch")

    assert str(job.trigger) == (
        "cron[hour='15,18,21,23', minute='58']"
    )
