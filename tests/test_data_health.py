from datetime import datetime
from zoneinfo import ZoneInfo

import service.data_health as data_health_module
from service.data_health import DataHealthService


class Stub:
    def __init__(self, value, method="overview"):
        setattr(self, method, lambda: value)


def test_operational_summary_avoids_full_freshness_and_delivery_scans():
    collection = {
        "summary": {
            "interfaces": 244,
            "collectable": 200,
            "complete": 140,
            "pending": 3,
            "running": 1,
            "attention": 0,
            "unresolved_failures": 0,
        },
        "services": [{"component": "worker", "status": "healthy"}],
    }
    coverage = {
        "summary": {
            "datasets": 193,
            "with_gaps": 0,
            "missing_partitions": 0,
            "partial_partitions": 0,
        }
    }
    service = DataHealthService(
        collection_service=Stub(collection),
        coverage_service=Stub(coverage),
        data_service=object(),
        initialization_service=Stub(
            {
                "active": {"initialization_id": 66, "status": "running"},
                "latest": None,
            }
        ),
        delivery_service=None,
    )

    result = service.summary()

    assert result["status"] == "warning"
    assert result["summary"]["pending_interfaces"] == 3
    assert result["history"]["initialization_id"] == 66
    assert result["unhealthy_services"] == []


def test_operational_summary_keeps_intraday_gap_warning_until_deadline():
    collection = {
        "summary": {
            "interfaces": 1,
            "collectable": 1,
            "complete": 0,
            "pending": 0,
            "running": 0,
            "attention": 1,
            "unverified": 0,
            "unresolved_failures": 0,
        },
        "services": [{"component": "worker", "status": "healthy"}],
    }
    coverage = {
        "summary": {
            "datasets": 1,
            "with_gaps": 1,
            "missing_partitions": 0,
            "partial_partitions": 1,
        },
        "datasets": [
            {
                "dataset": "index_daily",
                "latest": {
                    "status": "gaps",
                    "start_date": "2026-09-09",
                    "end_date": "2026-09-09",
                    "missing_partitions": 0,
                    "partial_partitions": 1,
                },
                "recent_missing": ["2026-09-09"],
            }
        ],
    }
    delivery = {
        "items": [
            {
                "api_name": "index_daily",
                "expected_for": "2026-09-09",
                "due_at": "2026-09-09T23:59:00+08:00",
                "delivery_status": "waiting",
                "attention": False,
            }
        ]
    }
    service = DataHealthService(
        collection_service=Stub(collection),
        coverage_service=Stub(coverage),
        data_service=object(),
        initialization_service=Stub({"active": None, "latest": None}),
        delivery_service=Stub(delivery, "today"),
    )

    assert service.summary()["status"] == "warning"


def test_intraday_coverage_gap_is_informational_until_delivery_deadline():
    service = DataHealthService(
        collection_service=Stub(
            {
                "summary": {
                    "interfaces": 1,
                    "collectable": 1,
                    "complete": 0,
                    "pending": 0,
                    "unverified": 1,
                    "unresolved_failures": 0,
                },
                "interfaces": [
                    {
                        "api_name": "index_daily",
                        "collectable": True,
                        "automatic_safe": True,
                        "latest": {
                            "source": "queue",
                            "id": 19,
                            "completion_status": "unverified",
                            "period_key": "20260908T1505+0800",
                        },
                        "unresolved_failure": None,
                    }
                ],
            }
        ),
        coverage_service=Stub(
            {
                "summary": {
                    "datasets": 1,
                    "auditable": 1,
                    "audited": 1,
                    "with_gaps": 1,
                    "missing_partitions": 0,
                    "partial_partitions": 1,
                },
                "datasets": [
                    {
                        "dataset": "index_daily",
                        "auditable": True,
                        "scheduled": True,
                        "latest": {
                            "status": "gaps",
                            "start_date": "2026-05-11",
                            "end_date": "2026-09-08",
                            "missing_partitions": 0,
                            "partial_partitions": 1,
                        },
                        "recent_missing": ["2026-09-08", "1993-01-29"],
                    }
                ],
            }
        ),
        data_service=Stub([], "freshness"),
        initialization_service=Stub({"active": None, "latest": None}),
        delivery_service=Stub(
            {
                "items": [
                    {
                        "api_name": "index_daily",
                        "work_id": 19,
                        "expected_for": "2026-09-08",
                        "due_at": "2026-09-08T21:05:00+08:00",
                        "delivery_status": "waiting",
                        "attention": False,
                    }
                ]
            },
            "today",
        ),
    )

    result = service.overview()

    assert result["summary"]["critical_issue_count"] == 0
    assert result["summary"]["confirmed_data_issue_count"] == 0
    issue = next(
        item for item in result["issues"]
        if item.get("dataset") == "index_daily"
    )
    assert issue["kind"] == "coverage_pending"
    assert issue["severity"] == "info"
    assert "21:05" in issue["detail"]
    collection_issue = next(
        item for item in result["issues"]
        if item.get("resource_type") == "interface"
    )
    assert collection_issue["kind"] == "collection_verification_pending"
    assert collection_issue["severity"] == "info"


def test_data_health_keeps_confirmed_gaps_separate_from_unknown_coverage():
    collection = {
        "summary": {
            "interfaces": 3,
            "collectable": 3,
            "complete": 1,
            "pending": 1,
            "unverified": 1,
            "unresolved_failures": 1,
        },
        "interfaces": [
            {
                "api_name": "daily",
                "collectable": True,
                "automatic_safe": True,
                "cadence": "daily",
                "latest": {"completion_status": "complete"},
                "unresolved_failure": {
                    "job_id": 9001,
                    "failure_type": "coverage_incomplete",
                    "period_key": "2026-09-04",
                    "error_message": "截面不完整",
                },
            },
            {
                "api_name": "fund_nav",
                "collectable": True,
                "automatic_safe": False,
                "cadence": "manual",
                "latest": None,
                "unresolved_failure": None,
            },
            {
                "api_name": "index_daily",
                "collectable": True,
                "automatic_safe": True,
                "cadence": "daily",
                "latest": {
                    "completion_status": "unverified",
                    "period_key": "2026-09-04",
                },
                "unresolved_failure": None,
            },
        ],
    }
    coverage = {
        "summary": {
            "datasets": 3,
            "auditable": 2,
            "audited": 1,
            "with_gaps": 1,
            "missing_partitions": 1,
            "partial_partitions": 0,
        },
        "datasets": [
            {
                "dataset": "stock_daily",
                "auditable": True,
                "strategy": "trading_daily",
                "latest": {
                    "status": "gaps",
                    "start_date": "2026-09-01",
                    "end_date": "2026-09-04",
                    "missing_partitions": 1,
                    "partial_partitions": 0,
                },
            },
            {
                "dataset": "index_daily",
                "auditable": True,
                "scheduled": True,
                "strategy": "trading_daily",
                "latest": None,
            },
            {
                "dataset": "stock_basic",
                "auditable": False,
                "strategy": "non_temporal",
                "latest": None,
            },
        ],
    }
    freshness = [
        {"dataset": "stock_daily", "status": "fresh", "latest_date": "2026-09-04"},
        {"dataset": "fund_nav", "status": "empty", "latest_date": None},
        {
            "dataset": "index_daily",
            "status": "not_configured",
            "latest_date": "2026-09-04",
        },
    ]
    initialization = {
        "runtime": {"mode": "daily"},
        "active": {
            "initialization_id": 66,
            "profile": "full",
            "history_start": "1990-12-19",
            "history_end": "2026-09-05",
            "status": "attention",
            "phase_name": "core_history",
            "phase_index": 2,
            "phase_total": 7,
            "planned_steps": 100,
            "completed_steps": 90,
            "failed_steps": 10,
            "error_message": "10 steps need attention",
        },
        "latest": None,
    }
    service = DataHealthService(
        collection_service=Stub(collection),
        coverage_service=Stub(coverage),
        data_service=Stub(freshness, "freshness"),
        initialization_service=Stub(initialization),
    )

    result = service.overview()
    kinds = {item["kind"] for item in result["issues"]}

    assert result["status"] == "critical"
    assert result["summary"]["critical_issue_count"] == 2
    assert result["summary"]["confirmed_issue_count"] == 2
    assert result["summary"]["never_collected_interfaces"] == 0
    assert result["summary"]["backfill_pending_interfaces"] == 1
    assert result["summary"]["scope_required_interfaces"] == 0
    assert result["summary"]["unaudited_datasets"] == 1
    assert result["history"]["complete"] is False
    assert "initialization_blocked" in kinds
    # The interface failure and its aliased stock_daily audit are one incident.
    assert "coverage_gap" not in kinds
    assert "coverage_not_audited" in kinds
    # fund_nav's missing first collection already explains its empty table.
    assert "dataset_empty" not in kinds
    assert "freshness_not_configured" in kinds
    assert "collection_unverified" in kinds
    failed_issue = next(
        item for item in result["issues"]
        if item.get("resource") == "daily"
    )
    assert failed_issue["job_id"] == 9001


def test_data_health_does_not_call_current_phase_ratio_overall_progress():
    service = DataHealthService(
        collection_service=Stub(
            {
                "summary": {
                    "interfaces": 0,
                    "collectable": 0,
                    "complete": 0,
                    "pending": 0,
                    "unverified": 0,
                    "unresolved_failures": 0,
                },
                "interfaces": [],
            }
        ),
        coverage_service=Stub(
            {
                "summary": {
                    "datasets": 0,
                    "auditable": 0,
                    "audited": 0,
                    "with_gaps": 0,
                    "missing_partitions": 0,
                    "partial_partitions": 0,
                },
                "datasets": [],
            }
        ),
        data_service=Stub([], "freshness"),
        initialization_service=Stub(
            {
                "runtime": {"mode": "daily"},
                "active": {
                    "initialization_id": 7,
                    "status": "running",
                    "planned_steps": 10,
                    "materialized_steps": 10,
                    "logical_total_steps": 40,
                    "remaining_steps": 31,
                    "progress_ratio": 9 / 40,
                    "completed_steps": 9,
                    "failed_steps": 0,
                    "phase_index": 2,
                    "phase_total": 7,
                },
                "latest": None,
            }
        ),
    )

    history = service.overview()["history"]

    assert history["phase_completed_steps"] == 9
    assert history["phase_materialized_steps"] == 10
    assert history["phase_logical_total_steps"] == 40
    assert history["phase_remaining_steps"] == 31
    assert history["phase_progress_ratio"] == 9 / 40
    assert "progress_ratio" not in history
    assert "当前阶段" in history["message"]


def test_data_health_does_not_duplicate_collection_and_coverage_incident():
    collection = {
        "summary": {
            "interfaces": 1,
            "collectable": 1,
            "complete": 0,
            "pending": 0,
            "unverified": 0,
            "unresolved_failures": 1,
        },
        "interfaces": [
            {
                "api_name": "margin",
                "collectable": True,
                "automatic_safe": True,
                "latest": {},
                "unresolved_failure": {
                    "failure_type": "coverage_incomplete",
                    "period_key": "2026-09-04",
                    "error_message": "截面不完整",
                },
            }
        ],
    }
    coverage = {
        "summary": {
            "datasets": 1,
            "auditable": 1,
            "audited": 1,
            "with_gaps": 1,
            "missing_partitions": 0,
            "partial_partitions": 1,
        },
        "datasets": [
            {
                "dataset": "margin",
                "auditable": True,
                "latest": {
                    "status": "gaps",
                    "start_date": "2026-05-09",
                    "end_date": "2026-09-06",
                    "missing_partitions": 0,
                    "partial_partitions": 1,
                },
            }
        ],
    }
    service = DataHealthService(
        collection_service=Stub(collection),
        coverage_service=Stub(coverage),
        data_service=Stub([], "freshness"),
        initialization_service=Stub({"active": None, "latest": None}),
    )

    result = service.overview()

    assert result["summary"]["critical_issue_count"] == 1
    assert [item["resource"] for item in result["issues"]] == ["margin"]
    assert result["issues"][0]["automatic_repair"] is True
    assert "幂等重采" in result["issues"][0]["action"]


def test_data_health_explains_empty_dataset_with_interface_failure_only_once():
    collection = {
        "summary": {
            "interfaces": 1,
            "collectable": 1,
            "complete": 0,
            "pending": 0,
            "unverified": 0,
            "unresolved_failures": 0,
        },
        "interfaces": [
            {
                "api_name": "fund_nav",
                "collectable": True,
                "automatic_safe": False,
                "latest": {
                    "completion_status": "failed",
                    "period_key": "手工探测",
                    "error_message": "缺少 ts_code",
                },
                "unresolved_failure": None,
            }
        ],
    }
    coverage = {
        "summary": {
            "datasets": 1,
            "auditable": 0,
            "audited": 0,
            "with_gaps": 0,
            "missing_partitions": 0,
            "partial_partitions": 0,
        },
        "datasets": [
            {"dataset": "fund_nav", "auditable": False, "latest": None}
        ],
    }
    service = DataHealthService(
        collection_service=Stub(collection),
        coverage_service=Stub(coverage),
        data_service=Stub(
            [{"dataset": "fund_nav", "status": "empty", "latest_date": None}],
            "freshness",
        ),
        initialization_service=Stub({"active": None, "latest": None}),
    )

    result = service.overview()

    assert [item["kind"] for item in result["issues"]] == [
        "manual_parameters_required"
    ]
    assert result["issues"][0]["severity"] == "info"
    assert result["issues"][0]["confidence"] == "configuration"


def test_optional_coverage_rule_is_classified_but_not_an_incident():
    collection = {
        "summary": {
            "interfaces": 0, "collectable": 0, "complete": 0,
            "pending": 0, "unverified": 0, "unresolved_failures": 0,
        },
        "interfaces": [],
    }
    coverage = {
        "summary": {
            "datasets": 1, "auditable": 1, "audited": 0,
            "with_gaps": 0, "missing_partitions": 0,
            "partial_partitions": 0,
        },
        "datasets": [{
            "dataset": "optional_events", "auditable": True,
            "scheduled": False, "latest": None,
        }],
    }
    service = DataHealthService(
        collection_service=Stub(collection),
        coverage_service=Stub(coverage),
        data_service=Stub([], "freshness"),
        initialization_service=Stub({"active": None, "latest": None}),
    )

    result = service.overview()

    assert result["issues"] == []
    assert result["summary"]["scheduled_unaudited_datasets"] == 0
    assert result["summary"]["optional_unaudited_datasets"] == 1


def test_manual_scope_requirement_suppresses_duplicate_empty_dataset():
    collection = {
        "summary": {
            "interfaces": 1, "collectable": 1, "complete": 0,
            "pending": 1, "unverified": 0, "unresolved_failures": 0,
        },
        "interfaces": [{
            "api_name": "daily", "collectable": True,
            "automatic_safe": False, "latest": None,
            "unresolved_failure": None,
        }],
    }
    coverage = {
        "summary": {
            "datasets": 1, "auditable": 0, "audited": 0,
            "with_gaps": 0, "missing_partitions": 0,
            "partial_partitions": 0,
        },
        "datasets": [{"dataset": "stock_daily", "auditable": False, "latest": None}],
    }
    service = DataHealthService(
        collection_service=Stub(collection),
        coverage_service=Stub(coverage),
        data_service=Stub(
            [{"dataset": "stock_daily", "status": "empty", "latest_date": None}],
            "freshness",
        ),
        initialization_service=Stub({"active": None, "latest": None}),
    )

    result = service.overview()

    assert [item["kind"] for item in result["issues"]] == [
        "manual_scope_required"
    ]
    assert result["issues"][0]["severity"] == "info"


def test_existing_shared_dataset_is_not_reported_as_never_collected():
    collection = {
        "summary": {
            "interfaces": 1, "collectable": 1, "complete": 0,
            "pending": 1, "unverified": 0, "unresolved_failures": 0,
        },
        "interfaces": [{
            "api_name": "express_vip", "collectable": True,
            "automatic_safe": False, "latest": None,
            "unresolved_failure": None,
        }],
    }
    coverage = {
        "summary": {
            "datasets": 1, "auditable": 0, "audited": 0,
            "with_gaps": 0, "missing_partitions": 0,
            "partial_partitions": 0,
        },
        "datasets": [{"dataset": "express", "auditable": False, "latest": None}],
    }
    service = DataHealthService(
        collection_service=Stub(collection),
        coverage_service=Stub(coverage),
        data_service=Stub(
            [{
                "dataset": "express", "status": "event_driven",
                "latest_date": "2026-06-30", "estimated_rows": 128,
            }],
            "freshness",
        ),
        initialization_service=Stub({"active": None, "latest": None}),
    )

    result = service.overview()

    assert result["summary"]["never_collected_interfaces"] == 0
    assert [item["kind"] for item in result["issues"]] == [
        "collection_lineage_missing"
    ]
    assert result["issues"][0]["severity"] == "info"


def test_full_initialization_marks_safe_fanout_first_collection_as_planned():
    collection = {
        "summary": {
            "interfaces": 1, "collectable": 1, "complete": 0,
            "pending": 1, "unverified": 0, "unresolved_failures": 0,
        },
        "interfaces": [{
            "api_name": "fund_nav", "collectable": True,
            "automatic_safe": False, "latest": None,
            "unresolved_failure": None,
        }],
    }
    coverage = {
        "summary": {
            "datasets": 0, "auditable": 0, "audited": 0,
            "with_gaps": 0, "missing_partitions": 0,
            "partial_partitions": 0,
        },
        "datasets": [],
    }
    service = DataHealthService(
        collection_service=Stub(collection),
        coverage_service=Stub(coverage),
        data_service=Stub([], "freshness"),
        initialization_service=Stub({
            "active": {
                "initialization_id": 66, "status": "running",
                "phase_name": "core_history",
            },
            "latest": None,
        }),
    )

    issue = service.overview()["issues"][0]

    assert issue["kind"] == "initialization_pending"
    assert issue["confidence"] == "planned"
    assert issue["severity"] == "info"


def test_recent_verified_empty_event_keeps_dataset_fresh(monkeypatch):
    monkeypatch.setattr(
        data_health_module,
        "business_now",
        lambda: datetime(2026, 9, 6, tzinfo=ZoneInfo("Asia/Shanghai")),
    )
    collection = {
        "summary": {
            "interfaces": 1,
            "collectable": 1,
            "complete": 0,
            "pending": 0,
            "unverified": 0,
            "unresolved_failures": 0,
        },
        "interfaces": [
            {
                "api_name": "stk_high_shock",
                "collectable": True,
                "latest": {
                    "completion_status": "empty",
                    "period_key": "initial-2026-09-05",
                    "expected_for": "2026-09-04",
                    "evidence": {"verified": True, "bounded_partition": True},
                },
                "unresolved_failure": None,
            }
        ],
    }
    coverage = {
        "summary": {
            "datasets": 1,
            "auditable": 0,
            "audited": 0,
            "with_gaps": 0,
            "missing_partitions": 0,
            "partial_partitions": 0,
        },
        "datasets": [
            {"dataset": "stk_high_shock", "auditable": False, "latest": None}
        ],
    }
    service = DataHealthService(
        collection_service=Stub(collection),
        coverage_service=Stub(coverage),
        data_service=Stub(
            [
                {
                    "dataset": "stk_high_shock",
                    "status": "stale",
                    "latest_date": "2026-09-02",
                    "freshness_sla_hours": 72,
                }
            ],
            "freshness",
        ),
        initialization_service=Stub({"active": None, "latest": None}),
    )

    result = service.overview()

    assert result["summary"]["stale_datasets"] == 0
    assert result["summary"]["fresh_datasets"] == 1
    assert result["freshness"][0]["freshness_basis"] == (
        "verified_empty_collection"
    )
    assert not any(item["kind"] == "stale_dataset" for item in result["issues"])


def test_pending_first_collection_is_not_reported_as_confirmed_empty():
    collection = {
        "summary": {
            "interfaces": 1, "collectable": 1, "complete": 0,
            "pending": 1, "unverified": 0, "unresolved_failures": 0,
        },
        "interfaces": [{
            "api_name": "hk_daily", "collectable": True,
            "automatic_safe": True,
            "latest": {
                "status": "queued", "completion_status": "retrying",
                "period_key": "2026-09-07",
            },
            "unresolved_failure": None,
        }],
    }
    coverage = {
        "summary": {
            "datasets": 1, "auditable": 1, "audited": 0,
            "with_gaps": 0, "missing_partitions": 0,
            "partial_partitions": 0,
        },
        "datasets": [{
            "dataset": "hk_daily", "auditable": True,
            "scheduled": False, "latest": None,
        }],
    }
    service = DataHealthService(
        collection_service=Stub(collection),
        coverage_service=Stub(coverage),
        data_service=Stub(
            [{
                "dataset": "hk_daily", "status": "empty",
                "latest_date": None, "estimated_rows": 0,
            }],
            "freshness",
        ),
        initialization_service=Stub({"active": None, "latest": None}),
    )

    result = service.overview()

    assert result["summary"]["backfill_pending_interfaces"] == 1
    assert result["summary"]["confirmed_data_issue_count"] == 0
    assert [item["kind"] for item in result["issues"]] == [
        "collection_pending"
    ]
    assert result["issues"][0]["severity"] == "info"
