from datetime import datetime, timezone

from service.collection_monitor import CollectionMonitorService


class FakeMonitorRepository:
    def service_health(self):
        return []

    def queue_by_resource(self):
        return []

    def fanout_workloads(self):
        return []

    def latest_interface_jobs(self):
        now = datetime.now(timezone.utc)
        return {
            "cn_cpi": {
                "job_id": 9,
                "task_name": "tushare_interface",
                "parameters": {"api_name": "cn_cpi", "complete": True},
                "status": "success",
                "attempt": 1,
                "rows_inserted": 3,
                "rows_fetched": 3,
                "cadence": "monthly",
                "period_key": "2026-08",
                "completion_status": "complete",
                "completion_evidence": {"verified": True},
                "error_message": None,
                "started_at": now,
                "finished_at": now,
            }
        }

    def latest_dedicated_runs(self):
        now = datetime.now(timezone.utc)
        return {
            "daily_daily": {
                "run_id": 3,
                "task_id": "daily_daily",
                "trade_date": "2026-08-28",
                "status": "success",
                "rows_inserted": 5000,
                "retry_count": 0,
                "error_message": None,
                "started_at": now,
                "finished_at": now,
            }
        }

    def latest_fanout_campaigns(self):
        return {}

    def unresolved_partition_failures(self):
        return {}


def test_collection_monitor_unifies_policy_and_dedicated_completion():
    payload = CollectionMonitorService(FakeMonitorRepository()).overview()
    items = {item["api_name"]: item for item in payload["interfaces"]}

    assert len(items) >= 244
    assert items["cn_cpi"]["latest"]["completion_status"] == "complete"
    assert items["daily"]["automation_mode"] == "dedicated"
    assert items["daily"]["latest"]["completion_status"] == "unverified"
    assert items["fut_basic"]["automation_mode"] == "fanout"
    assert items["fut_basic"]["cadence"] == "weekly"
    assert items["fut_basic"]["automatic_safe"] is True
    assert items["stk_mins"]["automation_mode"] == "manual"
    assert payload["summary"]["automated"] == 183


def test_dedicated_monitor_prefers_durable_verified_queue_evidence():
    repository = FakeMonitorRepository()
    now = datetime.now(timezone.utc)
    jobs = repository.latest_interface_jobs()
    jobs["daily"] = {
        "job_id": 12,
        "task_name": "scheduled_collector",
        "parameters": {"schedule_id": "daily_daily"},
        "status": "success",
        "attempt": 1,
        "rows_inserted": 5000,
        "rows_fetched": 5000,
        "cadence": "scheduled",
        "period_key": "2026-08-28",
        "completion_status": "complete",
        "completion_evidence": {
            "verified": False,
            "verification": {"verified": True},
        },
        "error_message": None,
        "created_at": now,
        "started_at": now,
        "finished_at": now,
    }
    repository.latest_interface_jobs = lambda: jobs

    payload = CollectionMonitorService(repository).overview()
    item = next(row for row in payload["interfaces"] if row["api_name"] == "daily")

    assert item["latest"]["source"] == "queue"
    assert item["latest"]["completion_status"] == "complete"


def test_collection_monitor_uses_whole_fanout_campaign_not_last_partial_page():
    repository = FakeMonitorRepository()
    repository.latest_fanout_campaigns = lambda: {
        "pledge_stat": {
            "campaign_id": 12,
            "api_name": "pledge_stat",
            "request": {},
            "status": "success",
            "completion_status": "complete",
            "universe_source": "stock",
            "universe_total": 5000,
            "universe_digest": "digest",
            "completed_offset": 5000,
            "pages_created": 25,
            "pages_completed": 25,
            "rows_fetched": 9000,
            "rows_inserted": 8000,
            "error_message": None,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
            "finished_at": datetime.now(timezone.utc),
        }
    }

    payload = CollectionMonitorService(repository).overview()
    item = next(row for row in payload["interfaces"] if row["api_name"] == "pledge_stat")

    assert item["automation_mode"] == "fanout"
    assert item["latest"]["source"] == "fanout_campaign"
    assert item["latest"]["completion_status"] == "complete"
    assert item["latest"]["campaign"]["pages_completed"] == 25


def test_ad_hoc_fanout_campaign_does_not_claim_periodic_automation():
    repository = FakeMonitorRepository()
    repository.latest_fanout_campaigns = lambda: {
        "fund_nav": {
            "campaign_id": 13,
            "api_name": "fund_nav",
            "request": {"start_date": "2026-08-01", "end_date": "2026-08-28"},
            "status": "running",
            "completion_status": "running",
            "universe_source": "fund",
            "universe_total": 100,
            "completed_offset": 10,
            "pages_created": 1,
            "pages_completed": 0,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }
    }

    payload = CollectionMonitorService(repository).overview()
    item = next(row for row in payload["interfaces"] if row["api_name"] == "fund_nav")

    assert item["automation_mode"] == "manual"
    assert item["latest"]["source"] == "fanout_campaign"
    assert payload["summary"]["automated"] == 183


def test_collection_monitor_exposes_worker_pool_backlog():
    repository = FakeMonitorRepository()
    now = datetime.now(timezone.utc)
    repository.service_health = lambda: [
        {
            "component": "worker-fanout",
            "instance_id": "fanout-1",
            "details": {"resource_classes": ["fanout"]},
            "last_seen_at": now,
            "age_seconds": 1,
        }
    ]
    repository.queue_by_resource = lambda: [
        {"resource_class": "fanout", "queued": 7, "running": 1, "failed_24h": 2}
    ]

    payload = CollectionMonitorService(repository).overview()

    assert payload["services"][0]["queue"] == {
        "queued": 7,
        "running": 1,
        "failed_24h": 2,
    }
    assert payload["queue_resources"][0]["resource_class"] == "fanout"


def test_older_unrecovered_partition_failure_is_not_hidden_by_latest_success():
    repository = FakeMonitorRepository()
    repository.unresolved_partition_failures = lambda: {
        "cn_cpi": {
            "api_name": "cn_cpi",
            "job_id": 7,
            "period_key": "2026-07",
            "expected_for": datetime(2026, 7, 31, tzinfo=timezone.utc),
            "error_message": "schema mismatch",
            "finished_at": datetime.now(timezone.utc),
        }
    }

    payload = CollectionMonitorService(repository).overview()
    item = next(row for row in payload["interfaces"] if row["api_name"] == "cn_cpi")

    assert item["latest"]["completion_status"] == "complete"
    assert item["unresolved_failure"]["period_key"] == "2026-07"
    assert item["unresolved_failure"]["failure_type"] == "execution_failure"
    assert payload["summary"]["unresolved_failures"] == 1
    assert payload["summary"]["attention"] >= 1


def test_verified_empty_is_counted_separately_from_real_attention():
    repository = FakeMonitorRepository()
    now = datetime.now(timezone.utc)
    jobs = repository.latest_interface_jobs()
    jobs["cn_ppi"] = {
        "job_id": 10,
        "task_name": "tushare_interface",
        "parameters": {"api_name": "cn_ppi", "complete": True},
        "status": "success",
        "attempt": 1,
        "rows_inserted": 0,
        "rows_fetched": 0,
        "cadence": "monthly",
        "period_key": "2026-08",
        "completion_status": "empty",
        "completion_evidence": {"verified": True, "exhausted": True},
        "error_message": None,
        "started_at": now,
        "finished_at": now,
    }
    repository.latest_interface_jobs = lambda: jobs

    payload = CollectionMonitorService(repository).overview()

    assert payload["summary"]["empty"] == 1
    assert payload["summary"]["unverified"] >= 1
    assert payload["summary"]["attention"] == 0


def test_coverage_incomplete_has_truthful_dashboard_reason():
    repository = FakeMonitorRepository()
    jobs = repository.latest_interface_jobs()
    jobs["cn_cpi"]["completion_status"] = "incomplete"
    jobs["cn_cpi"]["completion_evidence"] = {
        "verification": {"missing_partitions": 0, "partial_partitions": 1}
    }
    repository.latest_interface_jobs = lambda: jobs
    repository.unresolved_partition_failures = lambda: {
        "cn_cpi": {
            "api_name": "cn_cpi",
            "job_id": 11,
            "period_key": "2026-08",
            "expected_for": None,
            "status": "success",
            "completion_status": "incomplete",
            "completion_evidence": {"verification": {"partial_partitions": 1}},
            "error_message": None,
            "finished_at": datetime.now(timezone.utc),
        }
    }

    payload = CollectionMonitorService(repository).overview()
    item = next(row for row in payload["interfaces"] if row["api_name"] == "cn_cpi")

    assert item["unresolved_failure"]["failure_type"] == "coverage_incomplete"
    assert "1 个日期分区截面不完整" in item["unresolved_failure"]["error_message"]
    assert "1 个日期分区截面不完整" in item["latest"]["completion_reason"]


def test_collection_monitor_separates_historical_and_routine_fanout_workloads():
    repository = FakeMonitorRepository()
    repository.fanout_workloads = lambda: [
        {
            "workload": "historical",
            "active_campaigns": 1,
            "attention_campaigns": 0,
            "queued": 200,
            "running": 0,
        },
        {
            "workload": "routine",
            "active_campaigns": 2,
            "attention_campaigns": 1,
            "queued": 400,
            "running": 1,
        },
    ]

    payload = CollectionMonitorService(repository).overview()

    assert payload["fanout_workloads"][0]["workload"] == "historical"
    assert payload["fanout_workloads"][0]["queued"] == 200
    assert payload["fanout_workloads"][1]["workload"] == "routine"


def test_manual_probe_failure_is_not_counted_as_production_failure():
    repository = FakeMonitorRepository()
    jobs = repository.latest_interface_jobs()
    now = datetime.now(timezone.utc)
    jobs["fund_nav"] = {
        "job_id": 12,
        "task_name": "tushare_interface",
        "parameters": {"api_name": "fund_nav", "parameters": {}},
        "status": "failed",
        "attempt": 1,
        "rows_inserted": 0,
        "rows_fetched": 0,
        "cadence": "manual",
        "period_key": None,
        "completion_status": "failed",
        "completion_evidence": {
            "failure": {"category": "invalid_request", "retryable": False}
        },
        "error_message": "ts_code is required",
        "started_at": now,
        "finished_at": now,
    }
    repository.latest_interface_jobs = lambda: jobs

    payload = CollectionMonitorService(repository).overview()

    assert payload["summary"]["attention"] == 0
    assert payload["summary"]["manual_attention"] == 1
