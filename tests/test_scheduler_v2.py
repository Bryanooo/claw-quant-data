from datetime import datetime
from zoneinfo import ZoneInfo

import collectors.scheduler as scheduler_module
from collectors.scheduler import create_scheduler


def test_scheduler_contains_only_v2_control_jobs():
    scheduler = create_scheduler(set_active=False)
    ids = {job.id for job in scheduler.get_jobs()}
    assert ids == {
        "service_heartbeat",
        "v2_policy_dispatch",
        "v2_coverage_dispatch",
        "v2_coverage_rule_reconciler",
        "v2_late_repair_dispatch",
        "v2_initialization_reconciler",
    }


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
    }
    assert captured["create"]["proposals"] == (proposal,)
    assert captured["create"]["limit"] == 500
    assert captured["create"]["trigger_source"] == "schedule"
    assert captured["create"]["idempotency_prefix"].endswith(
        "2026-09-30T23:58"
    )


def test_late_repairs_run_at_multiple_post_close_windows():
    scheduler = create_scheduler(set_active=False)
    job = scheduler.get_job("v2_late_repair_dispatch")

    assert str(job.trigger) == (
        "cron[hour='15,18,21,23', minute='58']"
    )
