"""HTTP contracts for the read-only V2 orchestration operations API."""

from fastapi.testclient import TestClient

from service.api.app import create_app
from service.api.dependencies import get_orchestration_v2_repository


class DummyDatabase:
    def close(self):
        pass


class FakeOrchestrationV2Repository:
    def __init__(self):
        self.calls: list[tuple[str, dict]] = []

    def control_plane_summary(self):
        return {
            "status": "installed",
            "missing_tables": [],
            "endpoints": {"active": 202},
            "definitions": {
                "acquisition:active": 191,
                "transformation:active": 1,
                "transformation:draft": 13,
            },
            "executions": {},
            "dataset_states": {},
        }

    def today_delivery(self, data_date):
        self.calls.append(("today", {"data_date": data_date.isoformat()}))
        return {
            "engine": "orchestration_v2",
            "data_date": data_date,
            "summary": {"expected": 1, "strictly_ready": 1},
            "items": [],
        }

    def data_calendar(self, start_date, end_date):
        self.calls.append(("calendar", {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
        }))
        return [{"data_date": start_date, "ready": 1, "problems": 0}]

    def list_definitions(self, **kwargs):
        self.calls.append(("definitions", kwargs))
        return [
            {
                "task_definition_id": value,
                "task_key": f"task_{value}",
                "version": 1,
                "lifecycle_status": "active",
                "workflow_kind": "acquisition",
            }
            for value in (9, 8, 7)
        ]

    def list_executions(self, **kwargs):
        self.calls.append(("executions", kwargs))
        return [
            {
                "task_execution_id": value,
                "task_key": "stock_daily",
                "status": "attention",
            }
            for value in (19, 18, 17)
        ]

    def get_execution(self, execution_id):
        self.calls.append(("execution", {"execution_id": execution_id}))
        if execution_id == 404:
            return None
        return {
            "task_execution_id": execution_id,
            "task_key": "stock_daily",
            "status": "success",
            "node_status": {"validate": "success"},
        }

    def list_execution_events(self, execution_id):
        self.calls.append(("events", {"execution_id": execution_id}))
        return [{"sequence_number": 1, "event_type": "execution.created"}]

    def list_dataset_states(self, **kwargs):
        self.calls.append(("dataset_states", kwargs))
        return [
            {
                "dataset_state_id": value,
                "dataset_name": "stock_daily",
                "data_status": "complete",
                "ready": True,
            }
            for value in (29, 28, 27)
        ]


def make_client():
    app = create_app(database_factory=DummyDatabase)
    repository = FakeOrchestrationV2Repository()
    app.dependency_overrides[get_orchestration_v2_repository] = lambda: repository
    return TestClient(app), repository


def test_summary_separates_baseline_observation_and_activation():
    client, _ = make_client()
    with client:
        response = client.get("/api/v1/ops/orchestration-v2/summary")
    assert response.status_code == 200
    payload = response.json()
    assert payload["baseline"] == {
        "acquisition": 191,
        "transformation": 14,
        "total": 205,
    }
    assert payload["control_plane"]["status"] == "installed"
    assert payload["activation"] == "active"


def test_today_and_calendar_are_v2_data_date_views():
    client, repository = make_client()
    with client:
        today = client.get(
            "/api/v1/ops/orchestration-v2/today",
            params={"data_date": "2026-09-29"},
        )
        calendar = client.get(
            "/api/v1/ops/orchestration-v2/data-calendar",
            params={"start_date": "2026-09-01", "end_date": "2026-09-29"},
        )

    assert today.status_code == 200
    assert today.json()["data_date"] == "2026-09-29"
    assert calendar.status_code == 200
    assert calendar.json()["days"][0]["data_date"] == "2026-09-01"
    assert repository.calls == [
        ("today", {"data_date": "2026-09-29"}),
        ("calendar", {
            "start_date": "2026-09-01",
            "end_date": "2026-09-29",
        }),
    ]


def test_definition_listing_uses_exact_filters_and_keyset_page():
    client, repository = make_client()
    with client:
        response = client.get(
            "/api/v1/ops/orchestration-v2/definitions",
            params={
                "lifecycle_status": "active",
                "workflow_kind": "acquisition",
                "before_id": 10,
                "limit": 2,
            },
        )
    assert response.status_code == 200
    assert [item["task_definition_id"] for item in response.json()["items"]] == [9, 8]
    assert response.json()["page"] == {
        "limit": 2,
        "has_more": True,
        "next_cursor": 8,
    }
    assert repository.calls == [
        (
            "definitions",
            {
                "limit": 3,
                "before_id": 10,
                "lifecycle_status": "active",
                "workflow_kind": "acquisition",
            },
        )
    ]


def test_execution_and_dataset_state_filters_are_forwarded():
    client, repository = make_client()
    with client:
        executions = client.get(
            "/api/v1/ops/orchestration-v2/executions",
            params={
                "status": "attention",
                "task_key": "stock_daily",
                "before_id": 20,
                "limit": 2,
            },
        )
        states = client.get(
            "/api/v1/ops/orchestration-v2/dataset-states",
            params={
                "status": "complete",
                "dataset_name": "stock_daily",
                "before_id": 30,
                "limit": 2,
            },
        )
    assert executions.status_code == 200
    assert states.status_code == 200
    assert executions.json()["page"]["next_cursor"] == 18
    assert states.json()["page"]["next_cursor"] == 28
    assert repository.calls == [
        (
            "executions",
            {
                "limit": 3,
                "before_id": 20,
                "status": "attention",
                "task_key": "stock_daily",
            },
        ),
        (
            "dataset_states",
            {
                "limit": 3,
                "before_id": 30,
                "data_status": "complete",
                "dataset_name": "stock_daily",
            },
        ),
    ]


def test_read_api_rejects_unknown_states_before_querying_repository():
    client, repository = make_client()
    with client:
        response = client.get(
            "/api/v1/ops/orchestration-v2/executions",
            params={"status": "failed"},
        )
    assert response.status_code == 422
    assert repository.calls == []


def test_execution_detail_contains_execution_and_append_only_events():
    client, repository = make_client()
    with client:
        response = client.get("/api/v1/ops/orchestration-v2/executions/19")
    assert response.status_code == 200
    assert response.json()["execution"]["task_execution_id"] == 19
    assert response.json()["events"] == [
        {"sequence_number": 1, "event_type": "execution.created"}
    ]
    assert repository.calls == [
        ("execution", {"execution_id": 19}),
        ("events", {"execution_id": 19}),
    ]


def test_execution_detail_returns_404_for_unknown_instance():
    client, repository = make_client()
    with client:
        response = client.get("/api/v1/ops/orchestration-v2/executions/404")
    assert response.status_code == 404
    assert repository.calls == [("execution", {"execution_id": 404})]
