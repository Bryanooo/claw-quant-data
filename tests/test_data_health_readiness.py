from datetime import date

from service.data_health import DataHealthService


def test_active_scope_cannot_cover_unrelated_or_larger_history():
    from service.data_health import _scope_covers
    execution = {'task_key': 'cyq_chips', 'observation_start': '2026-09-20',
                 'observation_end': '2026-10-20'}
    assert _scope_covers(execution, 'cyq_chips', '2026-10-01', '2026-10-10')
    assert not _scope_covers(execution, 'cyq_chips', '2018-01-02', '2026-10-20')
    assert not _scope_covers(execution, 'other', '2026-10-01', '2026-10-10')


def test_partial_history_recovery_is_visible_but_does_not_clear_gap(monkeypatch):
    monkeypatch.setattr('service.data_health.DEFERRED_RESEARCH_DATASETS', frozenset())
    repository = FakeHistoricalGapOrchestration()
    repository.active_recovery_scopes = lambda: [{
        'task_key': 'us_daily', 'task_execution_id': 99, 'status': 'running',
        'observation_start': '2026-10-01', 'observation_end': '2026-10-09',
    }]
    result = DataHealthService(
        coverage_service=FakeHistoricalGapCoverage(), data_service=FakeData(),
        initialization_service=FakeInitialization(), orchestration_repository=repository,
    ).overview()
    assert result['summary']['operator_action_required'] == 1
    assert result['issues'][0]['active_recovery_segments'][0]['task_execution_id'] == 99
    assert '部分历史区间正在补采' in result['issues'][0]['action']


def test_exhausted_network_recovery_requires_operator_action():
    from service.config import V2_TRANSIENT_RECOVERY_MAX_ROUNDS
    repository = FakeExecutionAttentionOrchestration()
    repository.transient_recovery_rounds = lambda: {41: V2_TRANSIENT_RECOVERY_MAX_ROUNDS}
    result = DataHealthService(
        coverage_service=FakeOverviewCoverage(), data_service=FakeData(),
        initialization_service=FakeInitialization(),
        orchestration_repository=repository,
    ).overview()
    assert result['summary']['operator_action_required'] == 1
    assert result['issues'][0]['automatic_recovery_exhausted'] is True


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


class FakeActiveDatasetRepairOrchestration(FakeOverviewOrchestration):
    def active_recovery_scopes(self):
        return [{'task_key': 'local_factor_snapshot', 'observation_key': '2026-10-29'}]
    def control_plane_summary(self):
        return {
            "executions": {"attention": 3, "running": 1},
            "current_executions": {"attention": 1, "running": 1},
            "current_active_tasks": {"local_factor_snapshot": 99},
        }

    def latest_dataset_states(self):
        return {
            "local_factor_snapshot": {
                "dataset_name": "local_factor_snapshot",
                "observation_key": "2026-10-29",
                "observation_start": date(2026, 10, 29),
                "data_status": "gaps",
                "ready": False,
                "source_execution_id": 99,
            },
        }


def test_overview_marks_not_ready_dataset_as_repairing_when_its_task_is_active():
    service = DataHealthService(
        coverage_service=FakeOverviewCoverage(),
        data_service=FakeData(),
        initialization_service=FakeInitialization(),
        orchestration_repository=FakeActiveDatasetRepairOrchestration(),
    )

    result = service.overview()

    issue = result["issues"][0]
    assert issue["dataset"] == "local_factor_snapshot"
    assert issue["severity"] == "warning"
    assert issue["resolution_state"] == "repair_in_progress"
    assert issue["recovery_policy"] == "active_covering_repair"
    assert result["summary"]["operator_action_required"] == 0
    assert result["summary"]["repair_in_progress"] == 1


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
    def active_recovery_scopes(self):
        return [{'task_key': 'us_daily', 'observation_start': date(1990, 1, 1),
                 'observation_end': date(2026, 10, 9)}]
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
            "active_recovery_segments": [{
                "task_execution_id": None, "status": None,
                "observation_start": date(1990, 1, 1),
                "observation_end": date(2026, 10, 9),
            }],
        }
    ]


class FakePausedHistoricalGapOrchestration(FakeHistoricalGapOrchestration):
    def active_recovery_scopes(self):
        return []
    def control_plane_summary(self):
        return {"executions": {}, "current_executions": {"success": 1}}


def test_overview_does_not_treat_intentionally_deferred_dataset_as_incident():
    service = DataHealthService(
        coverage_service=FakeHistoricalGapCoverage(),
        data_service=FakeData(),
        initialization_service=FakeInitialization(),
        orchestration_repository=FakePausedHistoricalGapOrchestration(),
    )

    result = service.overview()

    assert result["summary"]["open_issues"] == 0
    assert result["summary"]["operator_action_required"] == 0
    assert result["summary"]["latest_dataset_states"] == 0
    assert result["summary"]["not_expected_dataset_states"] == 1
    assert result["summary"]["deferred_coverage_datasets"] == 1
    assert result["summary"]["datasets_with_gaps"] == 0
    assert result["summary"]["missing_partitions"] == 0
    # 运行范围之外的延后数据集仍保留全量口径，避免与 /api/v1/ops/coverage 打架
    assert result["summary"]["deferred_datasets_with_gaps"] == 1
    assert result["summary"]["deferred_missing_partitions"] == 9255
    assert result["summary"]["total_datasets_with_gaps"] == 1
    assert result["summary"]["total_missing_partitions"] == 9255
    assert result["summary"]["coverage_scope"] == {
        "total_datasets": 1,
        "audited_datasets": 1,
        "operational_datasets": 0,
        "deferred_datasets": ["us_daily"],
        "deferred_fields": [
            "datasets_with_gaps",
            "missing_partitions",
            "partial_partitions",
        ],
    }
    assert result["issues"] == []


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

    assert result["status"] == "warning"
    assert result["summary"]["open_issues"] == 1
    assert result["summary"]["operator_action_required"] == 0
    assert result["summary"]["waiting_upstream"] == 1
    assert {item["source_execution_id"] for item in result["issues"]} == {41}
    assert all(item["error_category"] == "network" for item in result["issues"])
    assert all("自动续跑" in item["action"] for item in result["issues"])
    assert all(
        item["recovery_policy"] == "automatic_transient_recovery"
        for item in result["issues"]
    )


class FakeRateLimitedExecutionOrchestration(FakeExecutionAttentionOrchestration):
    def list_executions(self, **_filters):
        return [{
            "task_execution_id": 51,
            "task_key": "ant_hot_stock_rank",
            "observation_key": "2026-10-29",
            "is_current_scope_execution": True,
            "final_error_category": "rate_limited",
            "final_error_message": "HTTP 429",
        }]


def test_rate_limited_execution_waits_for_upstream_instead_of_inviting_retry():
    service = DataHealthService(
        coverage_service=FakeOverviewCoverage(),
        data_service=FakeData(),
        initialization_service=FakeInitialization(),
        orchestration_repository=FakeRateLimitedExecutionOrchestration(),
    )

    result = service.overview()

    assert result["status"] == "warning"
    assert result["summary"]["operator_action_required"] == 0
    assert result["summary"]["waiting_upstream"] == 1
    assert result["issues"][0]["severity"] == "warning"
    assert result["issues"][0]["resolution_state"] == "waiting_upstream"
    assert "不要立即重复重试" in result["issues"][0]["action"]


class FakeRecoveredExecutionAttentionOrchestration(
    FakeExecutionAttentionOrchestration
):
    def latest_dataset_states(self):
        return {
            "cyq_perf": {
                "dataset_name": "cyq_perf",
                "observation_end": date(2026, 10, 11),
                "data_status": "complete",
                "ready": True,
            }
        }


def test_overview_keeps_recovered_execution_failures_only_in_history():
    service = DataHealthService(
        coverage_service=FakeOverviewCoverage(),
        data_service=FakeData(),
        initialization_service=FakeInitialization(),
        orchestration_repository=FakeRecoveredExecutionAttentionOrchestration(),
    )

    result = service.overview()

    assert result["summary"]["attention_attempts"] == 2
    assert result["summary"]["open_issues"] == 0
    assert result["summary"]["operator_action_required"] == 0
    assert result["issues"] == []


class FakeActivelyRecoveringExecutionOrchestration(
    FakeExecutionAttentionOrchestration
):
    def active_recovery_scopes(self):
        return [{'task_key': 'cyq_perf', 'observation_key': '2026-10-10'},
                {'task_key': 'cyq_perf', 'observation_key': '2026-10-09'}]
    def control_plane_summary(self):
        return {
            "executions": {"attention": 2, "retrying": 1},
            "current_executions": {"attention": 2, "retrying": 1},
            "current_active_tasks": {"cyq_perf": 1},
        }


def test_overview_hides_old_task_incident_while_same_task_is_recovering():
    service = DataHealthService(
        coverage_service=FakeOverviewCoverage(),
        data_service=FakeData(),
        initialization_service=FakeInitialization(),
        orchestration_repository=FakeActivelyRecoveringExecutionOrchestration(),
    )

    result = service.overview()

    assert result["summary"]["open_issues"] == 0
    assert result["summary"]["operator_action_required"] == 0
    assert result["issues"] == []


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
