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
