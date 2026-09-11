from datetime import date

from fastapi.testclient import TestClient

from service.api.app import create_app
from service.api.dependencies import (
    get_collection_monitor_service,
    get_coverage_service,
    get_data_health_service,
    get_data_service,
    get_delivery_monitor_service,
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

    def list_sectors(self, **kwargs):
        self.query_args = kwargs
        return {
            "data": [
                {
                    "provider": "ths",
                    "sector_code": "885001.TI",
                    "name": "人工智能",
                    "category": "概念指数",
                    "market": "A",
                    "constituent_count": 88,
                    "trade_date": None,
                }
            ],
            "meta": {"returned": 1},
        }

    def sector_snapshot(self, provider, sector_code, **kwargs):
        self.query_args = {"provider": provider, "sector_code": sector_code, **kwargs}
        return {"data": {"profile": {"name": "人工智能"}}, "meta": {}}

    def sector_members(self, provider, sector_code, **kwargs):
        self.query_args = {"provider": provider, "sector_code": sector_code, **kwargs}
        return {"data": [{"ts_code": "300750.SZ"}], "meta": {}}

    def sector_research_pack(self, provider, sector_code, **kwargs):
        self.query_args = {"provider": provider, "sector_code": sector_code, **kwargs}
        return {"data": {"profile": {"name": "人工智能"}}, "meta": {}}

    def stock_sectors(self, ts_code, **kwargs):
        self.query_args = {"ts_code": ts_code, **kwargs}
        return {"data": [{"sector_code": "885001.TI"}], "meta": {}}

    def stock_peers(self, ts_code, **kwargs):
        self.query_args = {"ts_code": ts_code, **kwargs}
        return {"data": [{"ts_code": "000001.SZ"}], "meta": {}}


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


def test_dataset_query_forwards_as_of_without_treating_it_as_a_field_filter():
    client, service = make_client()
    with client:
        response = client.get(
            "/api/v1/datasets/income/records",
            params={
                "ts_code": "000001.SZ",
                "end_date": "2024-03-31",
                "as_of": "2024-04-30",
            },
        )

    assert response.status_code == 200
    assert service.query_args["exact_filters"] == {"ts_code": "000001.SZ"}
    assert service.query_args["as_of"] == "2024-04-30"


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


def test_sector_research_endpoints_are_namespaced_and_bounded():
    client, service = make_client()
    with client:
        listed = client.get(
            "/api/v1/sectors",
            params={"provider": "ths", "query": "人工", "limit": 20},
        )
        pack = client.get(
            "/api/v1/sectors/ths/885001.ti/research-pack",
            params={
                "lookback_days": 90,
                "member_limit": 200,
                "as_of": "2026-09-08",
            },
        )

    assert listed.status_code == 200
    assert listed.json()["data"][0]["sector_code"] == "885001.TI"
    assert pack.status_code == 200
    assert service.query_args == {
        "provider": "ths",
        "sector_code": "885001.TI",
        "lookback_days": 90,
        "member_limit": 200,
        "as_of": date(2026, 9, 8),
    }


def test_stock_sector_and_peer_endpoints_forward_point_in_time_scope():
    client, service = make_client()
    with client:
        sectors = client.get(
            "/api/v1/stocks/300750.sz/sectors",
            params={"provider": "ths", "as_of": "2026-09-08"},
        )
        peers = client.get(
            "/api/v1/stocks/300750.sz/peers",
            params={
                "provider": "ths", "as_of": "2026-09-08",
                "max_sectors": 3, "limit": 20,
            },
        )

    assert sectors.status_code == 200
    assert peers.status_code == 200
    assert service.query_args == {
        "ts_code": "300750.SZ",
        "provider": "ths",
        "as_of": date(2026, 9, 8),
        "max_sectors": 3,
        "limit": 20,
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
    assert 'id="sidebarToggle"' in page.text
    assert "sidebar-v3" in page.text
    assert "访问密钥" not in page.text
    assert overview.status_code == 200
    assert overview.json()["summary"]["interfaces"] == 244

    dashboard_script = (
        PROJECT_ROOT / "service" / "dashboard" / "dashboard.js"
    ).read_text(encoding="utf-8")
    assert dashboard_script.count("window.confirm(") == 7
    assert "/api/v1/collection-fanout-campaigns" in dashboard_script
    assert "/api/v1/data-health" in dashboard_script
    assert "data-health-coverage-detail" in dashboard_script
    assert "claw-quant:sidebar-collapsed" in dashboard_script
    assert "/api/v1/coverage/repairs" in dashboard_script
    assert "coverageRangeStart" in page.text
    assert "coverageDetailStatus" in page.text
    assert "今日任务交付" in page.text
    assert "数据日历" in page.text
    assert 'id="operationsBanner"' in page.text
    assert "正在核对服务、今日交付、历史失败与数据缺口" in page.text
    assert "异常与可信度中心" in page.text
    assert 'role="tablist"' in page.text
    assert 'data-view-panel="interfaces"' in page.text
    assert 'data-page-key="interfaces"' in page.text
    assert 'data-page-key="health"' in page.text
    assert 'data-page-key="fanout"' in page.text
    assert 'data-page-key="coverage"' in page.text
    assert "pageRows(rows, \"interfaces\")" in dashboard_script
    assert "pageRows(rows, \"health\")" in dashboard_script
    assert "data-health-retry" in dashboard_script
    assert "/api/v1/delivery/data-calendar" in dashboard_script
    assert 'data-page-key="calendarDetails"' in page.text
    assert "last-successful-dashboard-refresh" in dashboard_script
    assert "state.endpointErrors" in dashboard_script
    assert "sessionStorage" not in dashboard_script
    assert "API Key" not in dashboard_script


def test_today_delivery_endpoint_uses_business_date():
    client, _ = make_client()
    captured = {}
    fake = type(
        "FakeDeliveryMonitor",
        (),
        {
            "today": lambda self, business_date: captured.update(
                {"business_date": business_date}
            ) or {
                "generated_at": "2026-09-08T12:00:00+08:00",
                "business_date": business_date.isoformat(),
                "summary": {"due_now": 3, "completed_due": 2},
                "items": [],
                "issues": [],
            }
        },
    )()
    client.app.dependency_overrides[get_delivery_monitor_service] = lambda: fake

    with client:
        response = client.get(
            "/api/v1/delivery/today?business_date=2026-09-08"
        )

    assert response.status_code == 200
    assert captured["business_date"] == date(2026, 9, 8)
    assert response.json()["summary"]["completed_due"] == 2


def test_delivery_calendar_endpoint_uses_bounded_date_range():
    client, _ = make_client()
    captured = {}
    fake = type(
        "FakeDeliveryCalendar",
        (),
        {
            "calendar": lambda self, start_date, end_date: captured.update(
                {"start_date": start_date, "end_date": end_date}
            ) or {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "summary": {"days": 30, "issue_days": 1},
                "days": [],
            }
        },
    )()
    client.app.dependency_overrides[get_delivery_monitor_service] = lambda: fake

    with client:
        response = client.get(
            "/api/v1/delivery/calendar?start_date=2026-09-01&end_date=2026-09-30"
        )

    assert response.status_code == 200
    assert captured == {
        "start_date": date(2026, 9, 1),
        "end_date": date(2026, 9, 30),
    }
    assert response.json()["summary"]["issue_days"] == 1


def test_delivery_data_calendar_endpoints_use_data_date():
    client, _ = make_client()
    captured = {}
    fake = type(
        "FakeDataCalendar",
        (),
        {
            "data_calendar": lambda self, start_date, end_date: captured.update(
                {"range": (start_date, end_date)}
            ) or {
                "basis": "data_date",
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "summary": {"days": 2},
                "days": [],
            },
            "data_calendar_day": lambda self, data_date: captured.update(
                {"day": data_date}
            ) or {
                "basis": "data_date",
                "data_date": data_date.isoformat(),
                "summary": {"status": "complete"},
                "items": [],
            },
        },
    )()
    client.app.dependency_overrides[get_delivery_monitor_service] = lambda: fake

    with client:
        month = client.get(
            "/api/v1/delivery/data-calendar?start_date=2026-09-08&end_date=2026-09-09"
        )
        day = client.get("/api/v1/delivery/data-calendar/2026-09-08")

    assert month.status_code == 200
    assert day.status_code == 200
    assert captured["range"] == (date(2026, 9, 8), date(2026, 9, 9))
    assert captured["day"] == date(2026, 9, 8)
    assert month.json()["basis"] == "data_date"
    assert day.json()["data_date"] == "2026-09-08"


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
            },
            "summary": lambda self: {
                "generated_at": "2026-09-08T12:00:00+08:00",
                "status": "warning",
                "scope": "operational_preflight",
                "summary": {"pending_interfaces": 3},
                "history": None,
                "unhealthy_services": [],
                "full_health_url": "/api/v1/data-health",
            },
        },
    )()

    with client:
        response = client.get("/api/v1/data-health")
        summary = client.get("/api/v1/data-health/summary")

    assert response.status_code == 200
    assert summary.status_code == 200
    assert summary.json()["scope"] == "operational_preflight"
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
            "submit_repairs": lambda self, dataset_name, **kwargs: {
                "dataset": dataset_name,
                "eligible": 1,
                "created": 1,
                "job_ids": [9],
                **kwargs,
            },
        },
    )()
    client.app.dependency_overrides[get_coverage_service] = lambda: fake

    with client:
        overview = client.get("/api/v1/coverage")
        partitions = client.get(
            "/api/v1/coverage/datasets/stock_daily/partitions"
        )
        repairs = client.post(
            "/api/v1/coverage/repairs",
            json={
                "dataset": "stock_daily",
                "start_date": "2026-08-28",
                "end_date": "2026-08-29",
            },
        )
        old_route = client.get("/v1/datasets")

    assert overview.status_code == 200
    assert overview.json()["summary"]["datasets"] == 16
    assert partitions.status_code == 200
    assert repairs.status_code == 202
    assert repairs.json()["created"] == 1
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

        def preflight(self, **kwargs):
            return {"status": "ready", "profile": kwargs["profile"]}

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
        preflight = client.post(
            "/api/v1/initialization/preflight",
            json={"profile": "full", "history_end": "2026-08-28"},
        )
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
    assert preflight.json() == {"status": "ready", "profile": "full"}
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
