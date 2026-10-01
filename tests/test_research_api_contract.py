from fastapi.testclient import TestClient

from service.api.app import create_app
from service.api.dependencies import get_data_health_service
from service.research.catalog import DERIVED_ENDPOINTS


class FakeDatabase:
    def close(self):
        pass


class FakeDataHealthService:
    def research_readiness(self):
        return {
            "status": "degraded",
            "summary": {"capabilities": 1},
            "capabilities": [],
            "datasets": [],
            "semantics": {
                "task_state": "transport state",
                "data_state": "persisted data evidence",
                "ready": "strictly verified",
                "degraded": "not fully verified",
                "unavailable": "absent or stale",
            },
            "task_execution": {
                "engine": "orchestration_v2",
                "status": "idle",
                "active_instances": 0,
                "attention_instances": 0,
                "executions": {},
            },
            "initialization": {},
            "generated_at": "2026-10-01T10:00:00+08:00",
        }


def test_research_readiness_route_calls_a_real_service_contract():
    app = create_app(database_factory=FakeDatabase)
    app.dependency_overrides[get_data_health_service] = FakeDataHealthService

    with TestClient(app) as client:
        response = client.get("/api/v1/research/readiness")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "degraded"
    assert payload["task_execution"]["engine"] == "orchestration_v2"
    assert payload["semantics"]["data_state"] == "persisted data evidence"


def test_every_advertised_research_endpoint_exists_in_openapi():
    paths = create_app(database_factory=FakeDatabase).openapi()["paths"]

    for endpoint in DERIVED_ENDPOINTS:
        assert endpoint["path"] in paths, endpoint["path"]
        assert endpoint["method"].lower() in paths[endpoint["path"]]
