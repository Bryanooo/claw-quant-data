from datetime import date

from fastapi.testclient import TestClient

from service.api.app import create_app
from service.api.dependencies import (
    get_collection_monitor_service,
    get_coverage_service,
    get_data_health_service,
    get_data_service,
    get_fanout_campaign_service,
    get_initialization_service,
    get_interface_data_service,
    get_normalization_monitor,
)
from service.config import PROJECT_ROOT


class DummyDatabase:
    def fetch_one(self, statement, params=()):
        return {"ok": 1}

    def close(self):
        pass


class FakeDataService:
    def __init__(self):
        self.query_args = None

    def list_datasets(self):
        return [
            {
                "name": "stock_daily",
                "description": "A股日线行情",
                "category": "market",
                "source": "Tushare Pro",
                "date_column": "trade_date",
            }
        ]

    def describe_dataset(self, name):
        return {
            **self.list_datasets()[0],
            "table": "daily",
            "primary_keys": ["ts_code", "trade_date"],
            "allowed_filters": ["ts_code"],
            "max_page_size": 1000,
            "columns": [],
        }

    def query_dataset(self, name, **kwargs):
        self.query_args = {"name": name, **kwargs}
        return {
            "data": [{"ts_code": "000001.SZ"}],
            "meta": {
                "dataset": name,
                "source": "Tushare Pro",
                "returned": 1,
            },
            "page": {
                "limit": kwargs["limit"],
                "offset": kwargs["offset"],
                "total": None,
                "has_more": False,
            },
        }

    def freshness(self, name=None):
        return [
            {
                "dataset": name or "stock_daily",
                "latest_date": None,
                "status": "empty",
                "freshness_sla_hours": 72,
                "estimated_rows": 0,
            }
        ]

    def stock_snapshot(self, ts_code):
        return {
            "data": {"basic": {"ts_code": ts_code}},
            "meta": {
                "ts_code": ts_code,
                "generated_at": "2026-07-26T00:00:00Z",
            },
        }

    def stock_research_pack(self, ts_code, **kwargs):
        self.query_args = {"ts_code": ts_code, **kwargs}
        return {
            "data": {"profile": {"basic": {"ts_code": ts_code}}},
            "meta": {
                "ts_code": ts_code,
                "benchmark": kwargs["benchmark"],
                "external_data_needed": [],
            },
        }


class FakeInterfaceDataService:
    def __init__(self):
        self.query_args = None

    def list_interfaces(self):
        return [
            {
                "api_name": "adj_factor",
                "title": "复权因子",
                "category": "股票数据",
                "permission_status": "有权限",
                "implementation_mode": "generic_raw",
                "storage_mode": "typed_standard_and_raw",
                "datasets": ["tushare_raw"],
                "records_url": "/api/v1/interfaces/adj_factor/records",
            }
        ]

    def describe_interface(self, api_name):
        return {
            **self.list_interfaces()[0],
            "description": "复权因子",
            "document_urls": ["https://tushare.pro/document/2?doc_id=28"],
            "input_parameters": [],
            "output_parameters": [],
            "allowed_filters": ["trade_date", "ts_code"],
            "date_fields": ["trade_date"],
        }

    def query_records(self, api_name, **kwargs):
        self.query_args = {"api_name": api_name, **kwargs}
        return {
            "data": [{"ts_code": "000001.SZ", "trade_date": "20260828"}],
            "meta": {
                "interface": api_name,
                "storage": "tushare_raw_record.payload",
                "returned": 1,
                "date_field": "trade_date",
            },
            "page": {
                "limit": kwargs["limit"],
                "offset": kwargs["offset"],
                "total": None,
                "has_more": False,
            },
        }

def make_client():
    app = create_app(database_factory=DummyDatabase)
    service = FakeDataService()
    app.dependency_overrides[get_data_service] = lambda: service
    app.dependency_overrides[get_interface_data_service] = FakeInterfaceDataService
    return TestClient(app), service


def test_health_endpoints():
    client, _ = make_client()
    with client:
        assert client.get("/api/health/live").json()["status"] == "ok"
        assert client.get("/api/health/ready").json() == {
            "status": "ready",
            "database": "ok",
        }


def test_dataset_query_passes_only_whitelisted_query_shape():
    client, service = make_client()
    with client:
        response = client.get(
            "/api/v1/datasets/stock_daily/records",
            params={
                "ts_code": "000001.SZ",
                "start_date": "2026-01-01",
                "limit": 20,
            },
        )

    assert response.status_code == 200
    assert response.json()["data"][0]["ts_code"] == "000001.SZ"
    assert service.query_args["exact_filters"] == {"ts_code": "000001.SZ"}
    assert service.query_args["limit"] == 20


def test_stock_research_pack_endpoint_passes_bounded_parameters():
    client, service = make_client()
    with client:
        response = client.get(
            "/api/v1/stocks/300750.sz/research-pack",
            params={
                "lookback_days": 90,
                "benchmark": "399006.sz",
                "financial_periods": 4,
                "as_of": "2026-09-08",
            },
        )

    assert response.status_code == 200
    assert response.json()["data"]["profile"]["basic"]["ts_code"] == "300750.SZ"
    assert service.query_args == {
        "ts_code": "300750.SZ",
        "lookback_days": 90,
        "benchmark": "399006.SZ",
        "financial_periods": 4,
        "as_of": date(2026, 9, 8),
    }


def test_interface_discovery_and_raw_query_are_under_api_namespace():
    client, _ = make_client()
    interface_service = client.app.dependency_overrides[
        get_interface_data_service
    ]()
    client.app.dependency_overrides[get_interface_data_service] = lambda: interface_service

    with client:
        interfaces = client.get("/api/v1/interfaces")
        description = client.get("/api/v1/interfaces/adj_factor")
        records = client.get(
            "/api/v1/interfaces/adj_factor/records",
            params={"ts_code": "000001.SZ", "start_date": "2026-08-01"},
        )

    assert interfaces.status_code == 200
    assert description.json()["allowed_filters"] == ["trade_date", "ts_code"]
    assert records.status_code == 200
    assert interface_service.query_args["filters"] == {"ts_code": "000001.SZ"}


def test_unknown_interface_returns_not_found():
    client, _ = make_client()
    client.app.dependency_overrides.pop(get_interface_data_service)

    with client:
        response = client.get("/api/v1/interfaces/not_an_interface")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "interface_not_found"


def test_normalization_health_endpoints_are_read_only_and_namespaced():
    client, _ = make_client()
    fake = type(
        "FakeNormalizationMonitor",
        (),
        {
            "overview": lambda self: {
                "generated_at": "2026-08-30T00:00:00Z",
                "summary": {
                    "interfaces": 94,
                    "raw_rows": 10,
                    "estimated_normalized_rows": 9,
                    "unresolved_errors": 1,
                    "unresolved_drift": 0,
                    "statuses": {"quarantined": 1},
                },
                "interfaces": [],
            },
            "drift": lambda self, **kwargs: [],
            "errors": lambda self, **kwargs: [],
        },
    )()
    client.app.dependency_overrides[get_normalization_monitor] = lambda: fake

    with client:
        overview = client.get("/api/v1/normalization")
        drift = client.get("/api/v1/normalization/drift")
        errors = client.get("/api/v1/normalization/errors")

    assert overview.status_code == 200
    assert overview.json()["summary"]["interfaces"] == 94
    assert drift.status_code == 200
    assert errors.status_code == 200


def test_read_endpoints_remain_open_when_legacy_key_exists(monkeypatch):
    monkeypatch.setenv("DATA_API_KEY", "reader-secret")
    client, _ = make_client()
    with client:
        datasets = client.get("/api/v1/datasets")
        health = client.get("/api/health/live")

    assert datasets.status_code == 200
    assert health.status_code == 200


def test_collection_dashboard_and_overview_endpoint():
    client, _ = make_client()
    client.app.dependency_overrides[get_collection_monitor_service] = lambda: type(
        "FakeMonitor",
        (),
        {
            "overview": lambda self: {
                "generated_at": "2026-08-29T00:00:00+08:00",
                "summary": {"interfaces": 244},
                "interfaces": [],
            }
        },
    )()

    with client:
        page = client.get("/dashboard")
        overview = client.get("/api/v1/collection-overview")

    assert page.status_code == 200
    assert "采集控制台" in page.text
    assert "访问密钥" not in page.text
    assert overview.status_code == 200
    assert overview.json()["summary"]["interfaces"] == 244

    dashboard_script = (
        PROJECT_ROOT / "service" / "dashboard" / "dashboard.js"
    ).read_text(encoding="utf-8")
    assert dashboard_script.count("window.confirm(") == 5
    assert "/api/v1/collection-fanout-campaigns" in dashboard_script
    assert "/api/v1/data-health" in dashboard_script
    assert "data-health-coverage-detail" in dashboard_script
    assert "数据缺失与可信度" in page.text
    assert 'role="tablist"' in page.text
    assert 'data-view-panel="interfaces"' in page.text
    assert 'data-page-key="interfaces"' in page.text
    assert 'data-page-key="health"' in page.text
    assert 'data-page-key="fanout"' in page.text
    assert 'data-page-key="coverage"' in page.text
    assert "pageRows(rows, \"interfaces\")" in dashboard_script
    assert "pageRows(rows, \"health\")" in dashboard_script
    assert "sessionStorage" not in dashboard_script
    assert "API Key" not in dashboard_script


def test_data_health_endpoint_is_under_api_namespace():
    client, _ = make_client()
    client.app.dependency_overrides[get_data_health_service] = lambda: type(
        "FakeDataHealth",
        (),
        {
            "overview": lambda self: {
                "generated_at": "2026-09-06T12:00:00+08:00",
                "status": "critical",
                "summary": {"confirmed_issue_count": 2},
                "history": {"status": "attention", "complete": False},
                "issues": [],
                "collection": {"summary": {}, "interfaces": [], "services": []},
                "coverage": {"summary": {}, "datasets": []},
                "freshness": [],
                "initialization": {
                    "runtime": {"mode": "daily"},
                    "active": None,
                    "latest": None,
                },
            }
        },
    )()

    with client:
        response = client.get("/api/v1/data-health")

    assert response.status_code == 200
    assert response.json()["summary"]["confirmed_issue_count"] == 2


def test_coverage_endpoints_use_api_namespace():
    client, _ = make_client()
    fake = type(
        "FakeCoverage",
        (),
        {
            "overview": lambda self: {
                "generated_at": "2026-08-29T00:00:00+08:00",
                "summary": {"datasets": 16, "audited": 1},
                "datasets": [],
            },
            "list_partitions": lambda self, dataset_name, **kwargs: {
                "dataset": dataset_name,
                "strategy": "trading_daily",
                "detects_missing_partitions": True,
                "partitions": [],
            },
        },
    )()
    client.app.dependency_overrides[get_coverage_service] = lambda: fake

    with client:
        overview = client.get("/api/v1/coverage")
        partitions = client.get(
            "/api/v1/coverage/datasets/stock_daily/partitions"
        )
        old_route = client.get("/v1/datasets")

    assert overview.status_code == 200
    assert overview.json()["summary"]["datasets"] == 16
    assert partitions.status_code == 200
    assert old_route.status_code == 404


def test_initialization_lifecycle_endpoints_are_under_api_namespace():
    client, _ = make_client()

    class FakeInitialization:
        def overview(self):
            return {
                "runtime": {"mode": "awaiting_initialization"},
                "active": None,
                "latest": None,
                "profiles": [{"name": "standard", "history_days": 365}],
            }

        def start(self, **kwargs):
            assert kwargs["auto_activate"] is False
            return ({"initialization_id": 7, "status": "running"}, True)

        def get(self, initialization_id):
            return {"initialization_id": initialization_id, "status": "running"}

        def list_steps(self, initialization_id, *, limit):
            return [{"initialization_id": initialization_id, "limit": limit}]

        def pause(self, initialization_id):
            return {"initialization_id": initialization_id, "status": "paused"}

        def resume(self, initialization_id):
            return {"initialization_id": initialization_id, "status": "running"}

        def activate(self, initialization_id):
            return {"initialization_id": initialization_id, "status": "completed"}

    client.app.dependency_overrides[get_initialization_service] = FakeInitialization

    with client:
        overview = client.get("/api/v1/initialization")
        created = client.post(
            "/api/v1/initialization",
            headers={"Idempotency-Key": "initialization-test-key"},
            json={"profile": "quick", "auto_activate": False},
        )
        steps = client.get("/api/v1/initialization/7/steps", params={"limit": 12})
        paused = client.post("/api/v1/initialization/7/pause")
        resumed = client.post("/api/v1/initialization/7/resume")
        activated = client.post("/api/v1/initialization/7/activate")
        full = client.post(
            "/api/v1/initialization",
            headers={"Idempotency-Key": "full-history-test-key"},
            json={"profile": "full", "auto_activate": False},
        )

    assert overview.status_code == 200
    assert overview.json()["runtime"]["mode"] == "awaiting_initialization"
    assert created.status_code == 202
    assert steps.json() == [{"initialization_id": 7, "limit": 12}]
    assert paused.json()["status"] == "paused"
    assert resumed.json()["status"] == "running"
    assert activated.json()["status"] == "completed"
    assert full.status_code == 202


def test_fanout_campaign_management_endpoints_are_under_api_namespace():
    client, _ = make_client()

    class FakeFanoutCampaigns:
        def list(self, *, status, limit):
            return [{"campaign_id": 8, "status": status or "running", "limit": limit}]

        def submit(self, request, *, idempotency_key):
            assert request["api_name"] == "pledge_stat"
            assert idempotency_key == "fanout-campaign-test-key"
            return {"campaign_id": 8, "status": "running"}, True

        def get(self, campaign_id):
            return {"campaign_id": campaign_id, "status": "running", "pages": []}

        def pause(self, campaign_id):
            return {"campaign_id": campaign_id, "status": "paused"}

        def resume(self, campaign_id):
            return {"campaign_id": campaign_id, "status": "running"}

        def reconcile(self, campaign_id):
            return {"campaign_id": campaign_id, "status": "running"}

    client.app.dependency_overrides[get_fanout_campaign_service] = FakeFanoutCampaigns

    with client:
        created = client.post(
            "/api/v1/collection-fanout-campaigns",
            headers={"Idempotency-Key": "fanout-campaign-test-key"},
            json={"api_name": "pledge_stat", "page_size": 200},
        )
        listed = client.get(
            "/api/v1/collection-fanout-campaigns",
            params={"status": "running", "limit": 12},
        )
        detail = client.get("/api/v1/collection-fanout-campaigns/8")
        paused = client.post("/api/v1/collection-fanout-campaigns/8/pause")
        resumed = client.post("/api/v1/collection-fanout-campaigns/8/resume")
        reconciled = client.post(
            "/api/v1/collection-fanout-campaigns/8/reconcile"
        )
        schedules = client.get("/api/v1/collection-fanout-schedules")

    assert created.status_code == 202
    assert listed.json()[0]["limit"] == 12
    assert detail.json()["campaign_id"] == 8
    assert paused.json()["status"] == "paused"
    assert resumed.json()["status"] == "running"
    assert reconciled.status_code == 200
    assert schedules.status_code == 200
    assert {item["api_name"] for item in schedules.json()} >= {
        "dc_index", "ci_index_member", "pledge_stat"
    }
