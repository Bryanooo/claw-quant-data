from datetime import date

from service.data_health import DataHealthService


class FakeCoverage:
    def overview(self):
        return {"datasets": []}


class FakeData:
    def freshness(self):
        return []


class FakeInitialization:
    def overview(self):
        return {"status": "complete"}


class FakeOrchestration:
    def control_plane_summary(self):
        return {"executions": {"running": 2, "attention": 1, "succeeded": 8}}


def test_research_readiness_keeps_data_and_task_states_separate(monkeypatch):
    monkeypatch.setattr(
        "service.data_health.evaluate_research_readiness",
        lambda **values: {
            "status": "ready",
            "summary": {"capabilities": 20},
            "capabilities": [],
            "datasets": [],
            "semantics": {},
            "as_of": date(2026, 10, 1),
            "evidence": values,
        },
    )
    service = DataHealthService(
        coverage_service=FakeCoverage(),
        data_service=FakeData(),
        initialization_service=FakeInitialization(),
        orchestration_repository=FakeOrchestration(),
    )

    result = service.research_readiness()

    assert result["status"] == "ready"
    assert result["task_execution"]["status"] == "attention"
    assert result["task_execution"]["active_instances"] == 2
    assert result["task_execution"]["attention_instances"] == 1
    assert result["initialization"] == {"status": "complete"}


class FakeOverviewCoverage:
    def overview(self):
        return {
            "summary": {
                "datasets": 194,
                "with_gaps": 2,
                "missing_partitions": 0,
                "partial_partitions": 2,
                "audited": 194,
                "strictly_verified": 147,
            },
            "datasets": [],
        }

    def list_partitions(self, dataset_name, **_filters):
        expected = 3 if dataset_name == "margin" else 4481
        actual = 1 if dataset_name == "margin" else 2001
        return {
            "partitions": [{
                "entity_count": actual,
                "expected_entity_count": expected,
                "entity_coverage_ratio": actual / expected,
            }]
        }


class FakeOverviewOrchestration:
    def control_plane_summary(self):
        return {
            "executions": {"attention": 10, "superseded": 100},
            "current_executions": {"attention": 2, "success": 150},
        }

    def latest_dataset_states(self):
        return {
            "margin": {
                "dataset_name": "margin",
                "observation_key": "2026-09-30",
                "observation_start": date(2026, 9, 30),
                "data_status": "gaps",
                "ready": False,
                "source_execution_id": 12,
            },
            "margin_detail": {
                "dataset_name": "margin_detail",
                "observation_key": "2026-09-30",
                "observation_start": date(2026, 9, 30),
                "data_status": "gaps",
                "ready": False,
                "source_execution_id": 13,
            },
        }

    def attention_covered_by_active_execution_ids(self):
        return ()


def test_overview_deduplicates_attempts_and_classifies_upstream_waiting():
    service = DataHealthService(
        coverage_service=FakeOverviewCoverage(),
        data_service=FakeData(),
        initialization_service=FakeInitialization(),
        orchestration_repository=FakeOverviewOrchestration(),
    )

    result = service.overview()

    assert result["status"] == "warning"
    assert result["summary"]["attention_task_instances"] == 2
    assert result["summary"]["attention_attempts"] == 10
    assert result["summary"]["open_issues"] == 2
    assert result["summary"]["waiting_upstream"] == 2
    assert result["summary"]["operator_action_required"] == 0
    assert result["summary"]["repair_in_progress"] == 0
    assert {item["resolution_state"] for item in result["issues"]} == {
        "waiting_upstream"
    }
    assert result["issues"][0]["actual_count"] is not None
    assert result["issues"][0]["expected_count"] is not None


class FakeCoveredAttentionOrchestration(FakeOverviewOrchestration):
    def control_plane_summary(self):
        return {
            "executions": {"attention": 4},
            "current_executions": {"attention": 4, "retrying": 1},
        }

    def latest_dataset_states(self):
        return {}

    def attention_covered_by_active_execution_ids(self):
        return (1, 2, 3, 4)


def test_overview_does_not_report_old_failures_as_actions_during_recovery():
    service = DataHealthService(
        coverage_service=FakeOverviewCoverage(),
        data_service=FakeData(),
        initialization_service=FakeInitialization(),
        orchestration_repository=FakeCoveredAttentionOrchestration(),
    )

    result = service.overview()

    assert result["status"] == "warning"
    assert result["summary"]["operator_action_required"] == 0
    assert result["summary"]["repair_in_progress"] == 4
    assert result["summary"]["active_task_instances"] == 1
    assert result["summary"]["running_task_instances"] == 0
    assert result["summary"]["queued_task_instances"] == 0
    assert result["summary"]["retrying_task_instances"] == 1
    assert result["summary"]["waiting_dependency_task_instances"] == 0


class FakeHistoricalGapCoverage(FakeOverviewCoverage):
    def overview(self):
        result = super().overview()
        result["datasets"] = [{
            "dataset": "us_daily",
            "latest": {
                "status": "gaps",
                "start_date": date(1990, 1, 1),
                "end_date": date(2026, 10, 9),
                "expected_partitions": 9255,
                "present_partitions": 0,
                "missing_partitions": 9255,
                "partial_partitions": 0,
                "coverage_ratio": 0,
            },
        }]
        return result


class FakeHistoricalGapOrchestration(FakeOverviewOrchestration):
    def control_plane_summary(self):
        return {
            "executions": {"retrying": 101},
            "current_executions": {"retrying": 101},
            "current_active_tasks": {"us_daily": 101},
        }

    def latest_dataset_states(self):
        return {
            "us_daily": {
                "dataset_name": "us_daily",
                "observation_key": "2026-10-09",
                "data_status": "complete",
                "ready": True,
            }
        }


def test_overview_keeps_active_historical_gap_visible_without_false_operator_alarm():
    service = DataHealthService(
        coverage_service=FakeHistoricalGapCoverage(),
        data_service=FakeData(),
        initialization_service=FakeInitialization(),
        orchestration_repository=FakeHistoricalGapOrchestration(),
    )

    result = service.overview()

    assert result["summary"]["open_issues"] == 1
    assert result["summary"]["operator_action_required"] == 0
    assert result["summary"]["repair_in_progress"] == 1
    assert result["issues"] == [
        {
            "kind": "historical_coverage_gap",
            "severity": "warning",
            "confidence": "confirmed",
            "dataset": "us_daily",
            "observation_key": "1990-01-01..2026-10-09",
            "status": "gaps",
            "resolution_state": "repair_in_progress",
            "actual_count": 0,
            "expected_count": 9255,
            "completeness_ratio": 0,
            "action": "历史补采已在自动执行队列中；查看该任务的重试/限频状态和覆盖审计",
            "recovery_policy": "active_history_repair",
            "next_automatic_repair_at": None,
            "source_execution_id": None,
            "task_key": "us_daily",
            "missing_partitions": 9255,
            "partial_partitions": 0,
        }
    ]


class FakeExecutionAttentionOrchestration(FakeOverviewOrchestration):
    def control_plane_summary(self):
        return {
            "executions": {"attention": 2},
            "current_executions": {"attention": 2},
        }

    def latest_dataset_states(self):
        return {}

    def list_executions(self, **_filters):
        return [
            {
                "task_execution_id": 41,
                "task_key": "cyq_perf",
                "observation_key": "2026-10-10",
                "is_current_scope_execution": True,
                "final_error_category": "network",
                "final_error_message": "timeout",
            },
            {
                "task_execution_id": 40,
                "task_key": "cyq_perf",
                "observation_key": "2026-10-09",
                "is_current_scope_execution": True,
                "final_error_category": "network",
                "final_error_message": "timeout",
            },
        ]


def test_overview_lists_current_execution_incidents_not_linked_to_dataset_state():
    service = DataHealthService(
        coverage_service=FakeOverviewCoverage(),
        data_service=FakeData(),
        initialization_service=FakeInitialization(),
        orchestration_repository=FakeExecutionAttentionOrchestration(),
    )

    result = service.overview()

    assert result["status"] == "critical"
    assert result["summary"]["open_issues"] == 2
    assert result["summary"]["operator_action_required"] == 2
    assert {item["source_execution_id"] for item in result["issues"]} == {40, 41}
    assert all(item["error_category"] == "network" for item in result["issues"])
    assert all("可重试" in item["action"] for item in result["issues"])


class FakeNotExpectedOrchestration(FakeOverviewOrchestration):
    def control_plane_summary(self):
        return {"executions": {}, "current_executions": {"success": 2}}

    def latest_dataset_states(self):
        return {
            "stock_daily": {
                "dataset_name": "stock_daily",
                "expectation_status": "expected",
                "data_status": "complete",
                "ready": True,
            },
            "weekend_only": {
                "dataset_name": "weekend_only",
                "expectation_status": "not_expected",
                "data_status": "pending",
                "ready": False,
            },
        }


def test_overview_excludes_not_expected_states_from_readiness_denominator():
    service = DataHealthService(
        coverage_service=FakeOverviewCoverage(),
        data_service=FakeData(),
        initialization_service=FakeInitialization(),
        orchestration_repository=FakeNotExpectedOrchestration(),
    )

    result = service.overview()

    assert result["summary"]["observed_dataset_states"] == 2
    assert result["summary"]["latest_dataset_states"] == 1
    assert result["summary"]["ready_dataset_states"] == 1
    assert result["summary"]["not_expected_dataset_states"] == 1
    assert result["summary"]["not_ready_dataset_states"] == 0
