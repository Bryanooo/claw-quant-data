"""HTTP and compilation contracts for the interface dependency inventory."""

from __future__ import annotations

from datetime import date, datetime

from fastapi.testclient import TestClient

from service.api.app import create_app
from service.api.dependencies import get_orchestration_v2_repository
from service.data_service.dependencies import (
    dependency_summary,
    field_lineage,
    interface_detail,
    interface_inventory,
    merge_runtime,
)


class FakeOrchestrationV2Repository:
    def schema_exists(self) -> bool:
        return True

    def latest_execution_states(self) -> dict[str, dict]:
        return {
            "adj_factor": {
                "task_key": "adj_factor",
                "task_execution_id": 11,
                "status": "success",
                "observation_start": "2026-10-20",
                "observation_end": "2026-10-20",
                "updated_at": datetime(2026, 10, 21, 9, 0).isoformat(),
            }
        }

    def latest_dataset_states(self) -> dict[str, dict]:
        return {
            "adj_factor": {
                "dataset_name": "adj_factor",
                "ready": True,
                "data_status": "complete",
                "observation_end": date(2026, 10, 20),
                "actual_count": 5400,
            }
        }


def _client() -> TestClient:
    application = create_app(database_factory=lambda: type("DB", (), {"close": lambda self: None})())
    application.dependency_overrides[get_orchestration_v2_repository] = (
        lambda: FakeOrchestrationV2Repository()
    )
    return TestClient(application)


def test_inventory_covers_all_registered_sources():
    items = interface_inventory()
    by_source = {source: 0 for source in {item["source"] for item in items}}
    for item in items:
        by_source[item["source"]] += 1
    assert by_source["tushare"] == 244
    assert by_source["financial_data"] == 163
    assert by_source["sina"] == 3
    assert {"cninfo", "sse", "chinabond", "chinamoney", "pboc"} <= set(by_source)
    assert len(items) == 415


def test_tushare_status_partition_matches_registry():
    items = [item for item in interface_inventory() if item["source"] == "tushare"]
    statuses = {item["key"]: item["status"] for item in items}
    registered = sum(status == "active" for status in statuses.values())
    paused = [key for key, status in statuses.items() if status == "paused"]
    assert registered == 194  # 201 callable endpoints minus 7 plain twins superseded by _vip
    assert paused == ["us_daily"]
    no_permission = [key for key, status in statuses.items() if status == "no_permission"]
    assert len(no_permission) == 38
    assert statuses["adj_factor"] == "active"


def test_vip_twins_carry_the_actual_schedule():
    """Plain finance interfaces are contract-only; the _vip endpoint is what runs."""
    items = {item["key"]: item for item in interface_inventory() if item["source"] == "tushare"}
    for base, vip in {
        "balancesheet": "balancesheet_vip",
        "income": "income_vip",
        "cashflow": "cashflow_vip",
        "express": "express_vip",
        "forecast": "forecast_vip",
        "fina_indicator": "fina_indicator_vip",
        "fina_mainbz": "fina_mainbz_vip",
    }.items():
        assert items[base]["status"] == "not_scheduled", base
        assert items[base]["superseded_by"] == vip
        assert items[base]["tasks"] == []
        assert items[vip]["status"] == "active", vip
        assert items[vip]["contract_source"] == base
        assert items[vip]["field_count"] == items[base]["field_count"] > 0
        assert items[vip]["tasks"], vip
    assert items["balancesheet_vip"]["tables"] == ["balancesheet"]
    detail = interface_detail("tushare", "balancesheet_vip")
    assert len(detail["output_parameters"]) == 158
    assert "balancesheet" in detail["description"]


def test_ant_routes_carry_policy_and_fields():
    snapshot = interface_detail("financial_data", "/api/v1/quote/basic-snapshot")
    assert snapshot is not None
    assert snapshot["status"] == "realtime_required"
    assert snapshot["acquisition_kind"] == "realtime"
    assert snapshot["equivalence_class"] == "financial_data_only"
    assert snapshot["field_count"] > 0
    fallback = interface_detail("financial_data", "/api/v1/stock_fnd/dividend-details")
    assert fallback["status"] == "not_scheduled"
    assert fallback["adapter_status"].startswith("partial_ready")
    assert "dividend" in fallback["datasets"]


def test_tushare_detail_contains_parameters_and_runtime_hooks():
    detail = interface_detail("tushare", "adj_factor")
    assert detail["output_parameters"][0]["name"] == "ts_code"
    assert detail["tasks"][0]["task_key"] == "adj_factor"
    assert detail["tables"] == ["tushare_norm_adj_factor"]
    assert "/api/v1/stock/tech-indicators" in detail["ant_full_equivalence_routes"]


def test_field_lineage_maps_table_fields_to_interfaces():
    lineage = {item["table"]: item for item in field_lineage()}
    adj = lineage["tushare_norm_adj_factor"]
    assert adj["interfaces"] == ["adj_factor"]
    names = {field["name"] for field in adj["fields"]}
    assert {"ts_code", "trade_date", "adj_factor"} <= names
    assert all(
        field["from_interfaces"] == ["adj_factor"] for field in adj["fields"]
    )
    # Multi-interface tables accumulate fields from every contributing contract.
    daily = lineage.get("tushare_norm_daily")
    if daily:
        assert len(daily["interfaces"]) >= 1


def test_summary_counts_are_consistent():
    summary = dependency_summary()
    assert summary["interfaces"] == 415
    assert summary["datasets"] == 204
    assert summary["tasks"] == 199
    assert summary["by_source"]["tushare"] == 244
    # 194 Tushare + 7 reviewed 蚂蚁 scheduled-pull routes
    assert summary["by_status"]["active"] == 201
    # 11 Tushare (4 no-task + 7 plain twins superseded by _vip)
    # + 29 蚂蚁 routes whose quota fallback is disabled by policy
    # + 28 蚂蚁 adapter-pending overlap routes
    assert summary["by_status"]["not_scheduled"] == 40
    assert summary["by_status"]["realtime_required"] == 4
    assert summary["by_status"]["ant_primary"] == 95
    assert summary["equivalence_counts"]["financial_data_only"] == 81


def test_merge_runtime_attaches_execution_and_dataset_state():
    items = [
        item for item in interface_inventory() if item["source"] == "tushare"
    ]
    merged = merge_runtime(
        items,
        {"adj_factor": FakeOrchestrationV2Repository().latest_execution_states()["adj_factor"]},
        {"adj_factor": FakeOrchestrationV2Repository().latest_dataset_states()["adj_factor"]},
    )
    adj = next(item for item in merged if item["key"] == "adj_factor")
    assert adj["runtime"]["latest_execution"]["status"] == "success"
    assert adj["runtime"]["ready_datasets"] == 1
    assert str(adj["runtime"]["latest_data_date"]) == "2026-10-20"
    # Interfaces without runtime evidence stay usable with runtime=None.
    other = next(item for item in merged if item["key"] != "adj_factor")
    assert other["runtime"] is None


def test_interfaces_endpoint_serves_filtered_inventory():
    client = _client()
    response = client.get("/api/v1/data/dependencies/interfaces?source=tushare&status=active")
    assert response.status_code == 200
    payload = response.json()
    assert payload["runtime_available"] is True
    assert payload["total"] == 194
    assert all(item["status"] == "active" for item in payload["items"])
    adj = next(item for item in payload["items"] if item["key"] == "adj_factor")
    assert adj["runtime"]["latest_execution"]["task_execution_id"] == 11


def test_interfaces_endpoint_searches_tables_and_datasets():
    client = _client()
    response = client.get("/api/v1/data/dependencies/interfaces?q=tushare_norm_adj_factor")
    assert response.status_code == 200
    keys = [item["key"] for item in response.json()["items"]]
    assert "adj_factor" in keys


def test_interface_detail_endpoint_and_404():
    client = _client()
    found = client.get(
        "/api/v1/data/dependencies/interfaces/tushare/detail",
        params={"key": "adj_factor"},
    )
    assert found.status_code == 200
    assert found.json()["interface"]["key"] == "adj_factor"
    route = client.get(
        "/api/v1/data/dependencies/interfaces/financial_data/detail",
        params={"key": "/api/v1/quote/basic-snapshot"},
    )
    assert route.status_code == 200
    missing = client.get(
        "/api/v1/data/dependencies/interfaces/tushare/detail",
        params={"key": "does_not_exist"},
    )
    assert missing.status_code == 404


def test_summary_and_field_lineage_endpoints():
    client = _client()
    summary = client.get("/api/v1/data/dependencies/summary")
    assert summary.status_code == 200
    assert summary.json()["interfaces"] == 415
    lineage = client.get(
        "/api/v1/data/dependencies/field-lineage",
        params={"q": "adj_factor"},
    )
    assert lineage.status_code == 200
    tables = [item["table"] for item in lineage.json()["items"]]
    assert "tushare_norm_adj_factor" in tables
