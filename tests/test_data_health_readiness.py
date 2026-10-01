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
    assert {item["resolution_state"] for item in result["issues"]} == {
        "waiting_upstream"
    }
    assert result["issues"][0]["actual_count"] is not None
    assert result["issues"][0]["expected_count"] is not None
